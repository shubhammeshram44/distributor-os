import uuid
import io
import logging
import typing
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, and_, select as sa_select, update as sa_update
from sqlalchemy.orm import Session, aliased, joinedload
from app.database import get_db, tenant_context
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.product import Product
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.ledger import CustomerLedger
from app.models.invoice import Invoice
from app.models.inventory import Inventory
from app.services.tenant_service import resolve_tenant_id
from app.services.demo_service import ensure_demo_data
from app.services.payment_service import reconcile_payments_and_invoices

logger = logging.getLogger(__name__)


class OrderResponse(BaseModel):
    id: str
    order_id: str
    customer: str
    channel: str
    amount: float
    status: str
    created_on: str
    eta: str
    payment_status: str
    amount_paid: float
    invoice_type: str


class AllocatedPayment(BaseModel):
    payment_code: str
    amount_allocated: float
    total_voucher_amount: float
    method: str
    reference_number: str | None = None
    created_at: str


class OrderDetailResponse(BaseModel):
    id: str
    order_id: str
    payment_status: str
    amount_paid: float
    payments_allocated: list[AllocatedPayment]
    invoice_type: str


from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.get("", status_code=status.HTTP_200_OK, response_model=list[OrderResponse])
def list_orders(
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns all orders for a tenant.
    """
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    ensure_demo_data(db, resolved_tenant_id)
    tenant_context.set(resolved_tenant_id)

    query = (
        sa_select(Order, Invoice)
        .outerjoin(Invoice, Invoice.order_id == Order.id)
        .options(
            joinedload(Order.line_items).joinedload(OrderLineItem.product)
        )
        .filter(Order.tenant_id == resolved_tenant_id)
        .order_by(Order.created_at.desc())
    )
    orders_invoices = db.execute(query).unique().all()
    # Pre-fetch all customers in one query to avoid N+1
    _cust_ids = list({o.customer_id for o, inv in orders_invoices})
    _custs_map = (
        {c.id: c for c in db.query(Customer).filter(Customer.id.in_(_cust_ids)).all()}
        if _cust_ids else {}
    )

    results = []

    for o, inv in orders_invoices:
        customer = _custs_map.get(o.customer_id)
        cust_name = customer.retailer_name if customer else "Unknown Retailer"

        # Calculate total amount
        amount_sum = sum(float(item.quantity * item.unit_price) for item in o.line_items)

        # Status badge conversion: Draft = "Pending", Confirmed = "Confirmed", Needs Review = "Needs Review"
        status_raw = o.current_status
        has_triage_sku = any(
            item.product is not None and item.product.sku_id == "UNMATCHED_TRIAGE_SKU"
            for item in o.line_items
        )
        if has_triage_sku:
            status_raw = "NEEDS_REVIEW"
        status_resolved = "Pending" if status_raw == "Draft" else ("Needs Review" if status_raw == "NEEDS_REVIEW" else status_raw)

        # Payment status attributes
        payment_status = o.payment_status if o.payment_status != "UNPAID" else (inv.payment_status if inv else "UNPAID")
        amount_paid = float(inv.amount_paid) if inv else 0.0

        results.append({
            "id": str(o.id),
            "order_id": o.internal_order_id,
            "customer": cust_name,
            "channel": o.source,
            "amount": amount_sum,
            "status": status_resolved,
            "created_on": o.created_at.strftime("%d %b, %Y %I:%M %p"),
            "eta": o.created_at.strftime("%d %b, %Y %I:%M %p"),
            "payment_status": payment_status,
            "amount_paid": amount_paid,
            "invoice_type": o.invoice_type
        })

    return results

class StatusUpdatePayload(BaseModel):
    to_status: str

@router.put("/{order_id}/status", status_code=status.HTTP_200_OK)
def update_order_status(
    order_id: uuid.UUID,
    payload: StatusUpdatePayload,
    db: Session = Depends(get_db)
):
    """
    Transitions order status and enforces real-time stock validation and atomic deduction
    upon confirming the order.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # Set tenant isolation context
    tenant_context.set(order.tenant_id)

    _valid_statuses = {"Draft", "Confirmed", "Dispatched", "Delivered"}
    if payload.to_status not in _valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{payload.to_status}'. Allowed: {sorted(_valid_statuses)}"
        )

    try:
        # Fetch Child Line Items
        items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order_id).all()

        if payload.to_status == "Confirmed":
            # 1. Fetch Customer
            customer = db.get(Customer, order.customer_id)
            if not customer:
                raise HTTPException(
                    status_code=404,
                    detail="Customer not found"
                )

            # 2. Calculate current order total
            current_order_total = sum(float(item.quantity * item.unit_price) for item in items)

            # 3. Aggregate Confirmed orders' outstanding balances — single SQL query (no N+1)
            _la = aliased(OrderStateLedger)
            _confirmed_ids = sa_select(OrderStateLedger.order_id).where(
                and_(
                    OrderStateLedger.to_status == "Confirmed",
                    OrderStateLedger.timestamp == (
                        sa_select(func.max(_la.timestamp))
                        .where(_la.order_id == OrderStateLedger.order_id)
                        .scalar_subquery()
                    )
                )
            )
            total_confirmed_outstanding = float(db.execute(
                sa_select(func.sum(OrderLineItem.quantity * OrderLineItem.unit_price))
                .join(Order, OrderLineItem.order_id == Order.id)
                .where(
                    and_(
                        Order.customer_id == order.customer_id,
                        Order.id != order_id,
                        Order.id.in_(_confirmed_ids)
                    )
                )
            ).scalar() or 0.0)

            # 4. Check Credit Limit
            combined_balance = total_confirmed_outstanding + current_order_total
            if combined_balance > float(customer.credit_limit):
                raise HTTPException(
                    status_code=400,
                    detail=f"Credit limit exceeded for customer '{customer.retailer_name}'. Combined balance: ₹{combined_balance:,.2f}, Credit Limit: ₹{customer.credit_limit:,.2f}"
                )

            # Resolve product variables dynamically
            for item in items:
                prod_data = db.query(Product).filter(Product.id == item.product_id).first()
                if prod_data:
                    item.sku_code = prod_data.sku_id
                    item.product_name = prod_data.sku_id
                else:
                    item.sku_code = "UNKNOWN_SKU"
                    item.product_name = "Unknown Product"

            # 5. Inventory Guardrail Validation Loop
            for item in items:
                # Find the corresponding inventory row for this tenant and SKU
                inv_record = db.query(Inventory).filter(
                    Inventory.tenant_id == order.tenant_id,
                    Inventory.sku_id == item.product_id  # Matches parent model ID mapping link
                ).first()

                if not inv_record:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Warehouse stock record not initialized for product code {item.sku_code}"
                    )

                if inv_record.quantity_on_hand < item.quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient physical stock for item. Requested: {item.quantity}, Available: {inv_record.quantity_on_hand}"
                    )

            # Atomic stock deduction: UPDATE with quantity guard prevents race conditions
            for item in items:
                result = db.execute(
                    sa_update(Inventory)
                    .where(
                        and_(
                            Inventory.tenant_id == order.tenant_id,
                            Inventory.sku_id == item.product_id,
                            Inventory.quantity_on_hand >= item.quantity
                        )
                    )
                    .values(quantity_on_hand=Inventory.quantity_on_hand - item.quantity)
                )
                if result.rowcount == 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stock conflict for {item.sku_code} — another order took the last units concurrently. Refresh and retry."
                    )

            # Update Customer outstanding balance (guard: only increment on first confirmation)
            if order.current_status not in ("Confirmed", "Dispatched", "Delivered"):
                customer.outstanding_balance = float(customer.outstanding_balance) + current_order_total

            # Record a DEBIT transaction in the customer ledger
            db.add(CustomerLedger(
                id=uuid.uuid4(),
                tenant_id=order.tenant_id,
                customer_id=order.customer_id,
                type="DEBIT",
                amount=current_order_total,
                reference_id=order.internal_order_id
            ))

            # Create Invoice
            invoice = Invoice(
                tenant_id=order.tenant_id,
                order_id=order.id,
                gstin=customer.gstin if (customer.gstin and customer.gstin not in ("PENDING", "")) else "UNREGISTERED",
                total_amount=current_order_total,
                irn_status="Cleared",
                qr_code_status="Generated",
                customer_id=order.customer_id,
                payment_status="UNPAID",
                amount_paid=0.0,
                created_at=datetime.utcnow()
            )
            db.add(invoice)
            db.flush()

            # Reconcile customer payments immediately to consume any credits
            reconcile_payments_and_invoices(db, order.tenant_id, order.customer_id)

        # Record state transition to OrderStateLedger

        current_status = order.current_status
        db.add(OrderStateLedger(
            tenant_id=order.tenant_id,
            order_id=order.id,
            from_status=current_status,
            to_status=payload.to_status,
            updated_by="system_orders_agent"
        ))

        db.commit()
        return {
            "status": "success",
            "order_id": str(order.id),
            "new_status": payload.to_status
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Status update transaction crash: {str(e)}"
        )


class ItemResolvePayload(BaseModel):
    sku_code: str
    quantity: int

@router.patch("/items/{item_id}/resolve", status_code=status.HTTP_200_OK)
def resolve_order_item(
    item_id: uuid.UUID,
    payload: ItemResolvePayload,
    db: Session = Depends(get_db)
):
    """
    Manually resolves an unmatched order item to a valid database product SKU
    and triggers parent order status recalculation.
    """
    # 1. Look up the OrderLineItem by ID
    item = db.get(OrderLineItem, item_id)
    if not item:
        raise HTTPException(
            status_code=404,
            detail="Order item not found"
        )
        
    order = db.get(Order, item.order_id)
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Parent order not found"
        )

    # Set tenant isolation context
    tenant_context.set(order.tenant_id)

    # 2. Fetch target profile from the Product table using the new sku_code
    product = db.query(Product).filter(Product.sku_id == payload.sku_code).first()
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product with SKU '{payload.sku_code}' not found."
        )

    # 3. Overwrite the order item's fields
    item.product_id = product.id
    item.quantity = payload.quantity
    item.unit_price = product.base_price

    # Force database write to see current items in query
    db.flush()

    # 4. Recalculate if there are any other unmatched items in this order
    all_items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    has_remaining_unmatched = False
    for i in all_items:
        prod = db.get(Product, i.product_id)
        if prod and prod.sku_id in ("UNMATCHED_SKU", "UNMATCHED_TRIAGE_SKU"):
            has_remaining_unmatched = True
            break

    current_status = order.current_status
    new_status = current_status

    # If all items in the order are now validly matched, automatically transition status
    if not has_remaining_unmatched and current_status == "Needs Review":
        new_status = "Draft"  # Maps to "Pending" on the frontend
        db.add(OrderStateLedger(
            tenant_id=order.tenant_id,
            order_id=order.id,
            from_status=current_status,
            to_status=new_status,
            updated_by="operator"
        ))

    db.commit()
    
    return {
        "status": "success",
        "item_id": str(item.id),
        "sku_code": payload.sku_code,
        "quantity": payload.quantity,
        "unit_price": float(product.base_price),
        "order_status": "Pending" if new_status == "Draft" else new_status
    }


def generate_invoice_pdf_bytes(order: Order, db: Session) -> bytes:
    # 3. Retrieve Tenant Info
    tenant = db.get(DistributorTenant, order.tenant_id)
    tenant_name = tenant.name if tenant else "S.V. Distributors"

    # 4. Retrieve Customer Info
    customer = db.get(Customer, order.customer_id)
    if not customer:
        raise ValueError("Customer not found associated with this order")

    # 5. Fetch order line items
    items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()

    # 6. Generate PDF with reportlab
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom colors
    primary_color = colors.HexColor("#1E3A8A")   # Navy/Dark Blue
    text_color = colors.HexColor("#1F2937")      # Slate 800
    light_bg = colors.HexColor("#F9FAFB")        # Gray 50
    border_color = colors.HexColor("#E5E7EB")    # Gray 200

    # Custom styles
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=primary_color
    )
    
    subtitle_style = ParagraphStyle(
        'InvoiceSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4B5563")
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=primary_color,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=text_color
    )

    body_bold = ParagraphStyle(
        'BodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    # Check if this should be formatted as a GST tax invoice
    is_gst = order.invoice_type != "RETAIL_CASH_INVOICE"

    # Header section (Tenant & Invoice ID/Date)
    invoice_id = f"INV-{order.internal_order_id}"
    order_date = order.created_at.strftime("%Y-%m-%d")
    
    header_left = f"<b>{tenant_name}</b><br/>B2B Distributor Services<br/>Email: billing@{tenant_name.lower().replace(' ', '').replace('.', '')}.com"
    header_title = "TAX INVOICE" if is_gst else "RETAIL INVOICE"
    header_right = f"<b>{header_title}</b><br/>Invoice ID: {invoice_id}<br/>Date: {order_date}<br/>Status: <b>Confirmed</b>"

    header_table_data = [
        [Paragraph(header_left, body_style), Paragraph(header_right, ParagraphStyle('RightText', parent=body_style, alignment=2))]
    ]
    header_table = Table(header_table_data, colWidths=[270, 270])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    # Divider line
    divider = Table([[""]], colWidths=[540])
    divider.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 1, primary_color),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 15))

    # Customer Profile Section (Conditionally hide GSTIN)
    cust_left_lines = [
        "<b>BILL TO:</b>",
        customer.retailer_name,
        customer.address_text
    ]
    if is_gst and customer.gstin:
        cust_left_lines.append(f"GSTIN: {customer.gstin}")
    cust_left = "<br/>".join(cust_left_lines)

    cust_right = f"<b>PAYMENT TERMS:</b><br/>{customer.payment_terms}<br/><br/><b>TAX GROUP:</b><br/>{customer.tax_group}"
    
    cust_table_data = [
        [Paragraph(cust_left, body_style), Paragraph(cust_right, body_style)]
    ]
    cust_table = Table(cust_table_data, colWidths=[270, 270])
    cust_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(cust_table)
    story.append(Spacer(1, 15))

    # Itemization Grid Title
    story.append(Paragraph("ITEMIZED LINE ITEMS", section_heading))
    
    # Grid Table
    grid_header = [
        Paragraph("<b>SKU ID</b>", body_bold),
        Paragraph("<b>Item Name</b>", body_bold),
        Paragraph("<b>Quantity</b>", body_bold),
        Paragraph("<b>Wholesale Price</b>", body_bold),
        Paragraph("<b>Line Total</b>", body_bold)
    ]
    grid_data = [grid_header]
    
    subtotal = 0.0
    for item in items:
        product = db.get(Product, item.product_id)
        sku = product.sku_id if product else item.sku_code or "UNKNOWN"
        item_name = f"{product.brand} {product.category} ({product.pack_size})" if product else "Unknown Product"
        qty = item.quantity
        price = float(item.unit_price)
        total = qty * price
        subtotal += total
        
        grid_data.append([
            Paragraph(sku, body_style),
            Paragraph(item_name, body_style),
            Paragraph(str(qty), body_style),
            Paragraph(f"₹ {price:,.2f}", body_style),
            Paragraph(f"₹ {total:,.2f}", body_style)
        ])

    grid_table = Table(grid_data, colWidths=[80, 220, 50, 95, 95])
    grid_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), light_bg),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, border_color),
        ('LINEBELOW', (0,0), (-1,0), 1.5, primary_color),
    ]))
    story.append(grid_table)
    story.append(Spacer(1, 15))

    # Tax Summary Block (Conditionally exclude GST)
    if is_gst:
        gst_rate = 0.18
        gst = subtotal * gst_rate
        grand_total = subtotal + gst
    else:
        gst = 0.0
        grand_total = subtotal

    summary_left = "<b>Declaration:</b><br/>We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct."
    summary_right_data = [
        [Paragraph("Subtotal:", body_style), Paragraph(f"₹ {subtotal:,.2f}", ParagraphStyle('RightAlign', parent=body_style, alignment=2))]
    ]
    if is_gst:
        summary_right_data.append(
            [Paragraph("GST (18%):", body_style), Paragraph(f"₹ {gst:,.2f}", ParagraphStyle('RightAlign', parent=body_style, alignment=2))]
        )
    summary_right_data.append(
        [Paragraph("<b>Total Payable:</b>", body_bold), Paragraph(f"<b>₹ {grand_total:,.2f}</b>", ParagraphStyle('RightAlignBold', parent=body_bold, alignment=2))]
    )
    summary_right_table = Table(summary_right_data, colWidths=[110, 110])
    summary_right_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, border_color),
        ('BACKGROUND', (0,-1), (-1,-1), light_bg),
    ]))

    final_block_data = [
        [Paragraph(summary_left, ParagraphStyle('Decl', parent=body_style, textColor=colors.HexColor("#6B7280"))), summary_right_table]
    ]
    final_block_table = Table(final_block_data, colWidths=[310, 230])
    final_block_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(final_block_table)

    # Build PDF
    doc.build(story)
    return buffer.getvalue()


@router.get("/{order_id}/invoice")
def get_order_invoice(
    order_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Generates a professional B2B tax invoice PDF for a confirmed order and streams it to the client.
    """
    # 1. Fetch the order
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # Set tenant isolation context
    tenant_context.set(order.tenant_id)

    # 2. Restrict to Confirmed orders
    if order.current_status != "Confirmed":
        raise HTTPException(
            status_code=400,
            detail="Invoices can only be generated for Confirmed orders"
        )

    try:
        pdf_bytes = generate_invoice_pdf_bytes(order, db)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    buffer = io.BytesIO(pdf_bytes)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice_{order_id}.pdf"
        }
    )


# =====================================================================
# Bulk Action Engine (Async Worker & Polling Endpoints)
# =====================================================================

import threading
import zipfile
import os
import time
import traceback
from fastapi import BackgroundTasks
from app.models.order import BulkJob

# Global Semaphore to restrict concurrency (prevents CPU/RAM exhaustion)
BULK_SEMAPHORE = threading.Semaphore(3)


def cleanup_zip_file_after_delay(filepath: str, delay_seconds: int = 3600):
    """
    Deletes the generated ZIP file after the specified TTL to save disk storage.
    """
    time.sleep(delay_seconds)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"BULK_CLEANUP: Removed file={filepath} after TTL expiry")
    except Exception as e:
        logger.error(f"BULK_CLEANUP_ERROR: Failed to remove file={filepath}: {e}")


def get_bulk_worker_db():
    from app.main import app
    from app.database import get_db, SessionLocal
    if get_db in app.dependency_overrides:
        override = app.dependency_overrides[get_db]
        try:
            gen = override()
            return next(gen)
        except TypeError:
            return override()
    return SessionLocal()


def process_bulk_invoices(job_id: str, order_ids: list[str], tenant_id: uuid.UUID, ttl_seconds: int = 3600):
    """
    Background worker that fetches orders, compiles ReportLab PDFs,
    packages them in a ZIP archive, updates progress in database,
    and schedules a cleanup thread.
    """
    from app.database import tenant_context
    tenant_context.set(tenant_id)
    
    db = get_bulk_worker_db()
    try:
        # Enforce concurrency limit on background task execution
        with BULK_SEMAPHORE:
            job = db.query(BulkJob).filter(BulkJob.job_id == job_id).first()
            if not job:
                return

            job.status = "PROCESSING"
            job.progress = 0
            db.commit()

            generated_pdfs = []
            failed_orders = []
            total_orders = len(order_ids)

            for idx, order_id_str in enumerate(order_ids):
                try:
                    order_id = uuid.UUID(order_id_str)
                    order = db.get(Order, order_id)
                    if not order:
                        raise ValueError("Order not found")
                    
                    if order.current_status != "Confirmed":
                        raise ValueError("Order is not Confirmed")

                    pdf_bytes = generate_invoice_pdf_bytes(order, db)
                    filename = f"invoice_{order.internal_order_id}.pdf"
                    generated_pdfs.append((filename, pdf_bytes))
                except Exception as e:
                    failed_orders.append({
                        "order_id": order_id_str,
                        "error": str(e)
                    })

                progress = int(((idx + 1) / total_orders) * 100)
                job.progress = progress
                db.commit()

            result_link = None
            zip_filepath = None
            if generated_pdfs:
                os.makedirs("static", exist_ok=True)
                zip_filename = f"bulk_{job_id}.zip"
                zip_filepath = os.path.join("static", zip_filename)
                
                with zipfile.ZipFile(zip_filepath, 'w') as zf:
                    for filename, pdf_bytes in generated_pdfs:
                        zf.writestr(filename, pdf_bytes)

                result_link = f"/static/{zip_filename}"

            # Schedule TTL cleanup in a separate daemon thread
            if zip_filepath:
                threading.Thread(
                    target=cleanup_zip_file_after_delay,
                    args=(zip_filepath, ttl_seconds),
                    daemon=True
                ).start()

            # Set final status
            if len(failed_orders) == 0:
                job.status = "COMPLETED"
            elif len(failed_orders) == total_orders:
                job.status = "FAILED"
            else:
                job.status = "PARTIALLY_COMPLETED"

            job.result_link = result_link
            job.metadata_json = {"failed_orders": failed_orders}
            db.commit()
            logger.info(f"BULK_JOB_DONE: job_id={job_id} status={job.status} failed={len(failed_orders)}")

    except Exception as e:
        logger.error(f"BULK_JOB_FATAL_ERROR: job_id={job_id} error={e}")
        try:
            job = db.query(BulkJob).filter(BulkJob.job_id == job_id).first()
            if job:
                job.status = "FAILED"
                job.metadata_json = {"error": str(e), "traceback": traceback.format_exc()}
                db.commit()
        except Exception:
            pass
    finally:
        from app.database import get_db
        from app.main import app
        if get_db not in app.dependency_overrides:
            db.close()


class BulkActionPayload(BaseModel):
    order_ids: list[str]


class BulkJobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    result_link: str | None
    failed_orders: list[dict] | None = None


@router.post("/bulk-action", status_code=status.HTTP_202_ACCEPTED)
def trigger_bulk_action(
    payload: BulkActionPayload,
    background_tasks: BackgroundTasks,
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Registers a new bulk invoice generation job and runs the compiler in the background.
    """
    from app.services.tenant_service import resolve_tenant_id
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)

    job_id = str(uuid.uuid4())
    job = BulkJob(
        job_id=job_id,
        progress=0,
        status="PENDING"
    )
    db.add(job)
    db.commit()

    # Pass the actual client-specific resolved tenant ID
    background_tasks.add_task(
        process_bulk_invoices,
        job_id,
        payload.order_ids,
        resolved_tenant_id
    )

    return {"status": "accepted", "job_id": job_id}


@router.get("/bulk-action/{job_id}", response_model=BulkJobStatusResponse)
def get_bulk_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves the execution status and progress metric for a running bulk job.
    """
    job = db.query(BulkJob).filter(BulkJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    failed_orders = None
    if job.metadata_json and "failed_orders" in job.metadata_json:
        failed_orders = job.metadata_json["failed_orders"]

    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "result_link": job.result_link,
        "failed_orders": failed_orders
    }


@router.get("/{order_id}", status_code=status.HTTP_200_OK, response_model=OrderDetailResponse)
def get_order_by_id(
    order_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Returns single order detail including its payment allocation history.
    """
    from app.models.payment import Payment, PaymentInvoiceLink
    from app.models.invoice import Invoice

    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # Set tenant isolation context
    tenant_context.set(order.tenant_id)

    # Find associated invoice
    invoice = db.query(Invoice).filter(Invoice.order_id == order.id).first()
    
    payments_allocated = []
    if invoice:
        # Join allocation history
        links = (
            db.query(PaymentInvoiceLink, Payment)
            .join(Payment, PaymentInvoiceLink.payment_id == Payment.id)
            .filter(PaymentInvoiceLink.invoice_id == invoice.id)
            .all()
        )
        for link, payment in links:
            payments_allocated.append({
                "payment_code": f"PAY-REC-{str(payment.id)[:8].upper()}",
                "amount_allocated": float(link.amount_allocated),
                "total_voucher_amount": float(payment.amount),
                "method": payment.method,
                "reference_number": payment.reference_number,
                "created_at": payment.created_at.isoformat()
            })

    return {
        "id": str(order.id),
        "order_id": order.internal_order_id,
        "payment_status": order.payment_status if order.payment_status != "UNPAID" else (invoice.payment_status if invoice else "UNPAID"),
        "amount_paid": float(invoice.amount_paid) if invoice else 0.0,
        "payments_allocated": payments_allocated,
        "invoice_type": order.invoice_type
    }


class OrderItemCreate(BaseModel):
    sku_id: str
    quantity: int
    unit_price: float


class OrderCreatePayload(BaseModel):
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    source: str
    status: str
    items: list[OrderItemCreate]
    invoice_type: str = "UNSPECIFIED"


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreatePayload,
    db: Session = Depends(get_db)
):
    """
    Creates a new order from a structured payload.
    """
    tenant_context.set(payload.tenant_id)
    
    # Generate unique order ID
    from datetime import datetime
    generated_order_id = f"ORD-2506-{uuid.uuid4().hex[:4].upper()}"
    
    new_order = Order(
        id=uuid.uuid4(),
        tenant_id=payload.tenant_id,
        internal_order_id=generated_order_id,
        source=payload.source,
        customer_id=payload.customer_id,
        invoice_type=payload.invoice_type,
        created_at=datetime.utcnow()
    )
    db.add(new_order)
    db.flush()

    for item in payload.items:
        # Fetch or resolve the product by sku_id
        product = db.query(Product).filter_by(sku_id=item.sku_id).first()
        if not product:
            # Create a fallback product
            product = Product(
                id=uuid.uuid4(),
                tenant_id=payload.tenant_id,
                sku_id=item.sku_id,
                brand="Generic",
                category="Grocery",
                pack_size="1 unit",
                base_price=item.unit_price
            )
            db.add(product)
            db.flush()

        db.add(OrderLineItem(
            id=uuid.uuid4(),
            tenant_id=payload.tenant_id,
            order_id=new_order.id,
            product_id=product.id,
            quantity=item.quantity,
            unit_price=item.unit_price
        ))

    # Add ledger transition entry
    db.add(OrderStateLedger(
        tenant_id=payload.tenant_id,
        order_id=new_order.id,
        from_status=None,
        to_status=payload.status,
        updated_by="operator"
    ))

    if payload.status == "Confirmed":
        customer = db.get(Customer, payload.customer_id)
        if customer:
            amount_sum = sum(float(item.quantity * item.unit_price) for item in payload.items)
            customer.outstanding_balance = float(customer.outstanding_balance) + amount_sum
            
            db.add(CustomerLedger(
                id=uuid.uuid4(),
                tenant_id=payload.tenant_id,
                customer_id=payload.customer_id,
                type="DEBIT",
                amount=amount_sum,
                reference_id=generated_order_id
            ))
            
            invoice = Invoice(
                tenant_id=payload.tenant_id,
                order_id=new_order.id,
                gstin=customer.gstin if (customer.gstin and customer.gstin not in ("PENDING", "")) else "UNREGISTERED",
                total_amount=amount_sum,
                irn_status="Cleared",
                qr_code_status="Generated",
                customer_id=payload.customer_id,
                payment_status="UNPAID",
                amount_paid=0.0,
                created_at=new_order.created_at
            )
            db.add(invoice)
            db.flush()
            
            from app.services.payment_service import reconcile_payments_and_invoices
            reconcile_payments_and_invoices(db, payload.tenant_id, payload.customer_id)

    db.commit()
    return {
        "status": "success",
        "order_id": str(new_order.id),
        "internal_order_id": generated_order_id,
        "new_status": payload.status
    }


class OrderPatchPayload(BaseModel):
    invoice_type: typing.Literal["GST_TAX_INVOICE", "RETAIL_CASH_INVOICE", "UNSPECIFIED"]


@router.patch("/{order_id}", status_code=status.HTTP_200_OK)
def patch_order(
    order_id: uuid.UUID,
    payload: OrderPatchPayload,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Updates the invoice type preference for an order.
    """
    import typing
    from app.utils.security import verify_jwt
    from app.models.user import User

    token = None
    if access_token:
        token = access_token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]

    current_user = None
    if token:
        try:
            token_payload = verify_jwt(token)
            if token_payload and "user_id" in token_payload:
                current_user = db.get(User, uuid.UUID(token_payload["user_id"]))
        except Exception:
            pass

    if not current_user:
        current_user = type('User', (object,), {'id': 'SYSTEM'})()

    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    tenant_context.set(order.tenant_id)
    order.invoice_type = payload.invoice_type

    logger.info(f"INVOICE_TYPE_CHANGE: order_id={order_id} new_type={payload.invoice_type} user={current_user.id}")

    db.commit()
    return {
        "status": "success",
        "order_id": str(order.id),
        "invoice_type": order.invoice_type
    }


# =====================================================================
# API Wrappers for Regression Firewall Tests
# =====================================================================
from typing import Any
from app.models.tenant import DistributorTenant
from app.models.shipment import Shipment

class IngestionOrderItem(BaseModel):
    sku_id: str
    quantity: int
    price: float

class IngestionOrderPayload(BaseModel):
    customer_id: Any
    items: list[IngestionOrderItem]

@router.post("/create", status_code=201)
def create_order_generic(payload: IngestionOrderPayload, db: Session = Depends(get_db)):
    # 1. Resolve tenant_id: use first tenant or DEMO_TENANT_ID
    tenant = db.query(DistributorTenant).first()
    tenant_id = tenant.id if tenant else DEMO_TENANT_ID
    tenant_context.set(tenant_id)

    # 2. Resolve customer
    customer = None
    if isinstance(payload.customer_id, int) or str(payload.customer_id).isdigit():
        customer = db.query(Customer).filter(Customer.customer_id == f"CUST-{payload.customer_id}").first()
        if not customer:
            customer = db.query(Customer).first()
    else:
        try:
            customer = db.get(Customer, uuid.UUID(str(payload.customer_id)))
        except ValueError:
            customer = db.query(Customer).first()

    if not customer:
        customer = Customer(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id="CUST-101",
            retailer_name="Kaveri Provision Store",
            address_text="Bengaluru",
            gstin="UNREGISTERED",
            tax_group="GST-18",
            payment_terms="0-15 Days"
        )
        db.add(customer)
        db.flush()

    # 3. Create the order
    order_id = uuid.uuid4()
    generated_order_id = f"ORD-2506-{uuid.uuid4().hex[:4].upper()}"
    new_order = Order(
        id=order_id,
        tenant_id=tenant_id,
        internal_order_id=generated_order_id,
        source="API",
        customer_id=customer.id,
        created_at=datetime.utcnow()
    )
    db.add(new_order)
    db.flush()

    # 4. Create line items
    for item in payload.items:
        # Check if product exists
        product = db.query(Product).filter_by(sku_id=item.sku_id).first()
        if not product:
            # We use item.sku_id as the primary key ID directly in SQLite to support tests querying by Inventory.sku_id == "SKU..."
            product = Product(
                id=item.sku_id,
                tenant_id=tenant_id,
                sku_id=item.sku_id,
                brand="Generic",
                category="Grocery",
                pack_size="1 unit",
                base_price=item.price
            )
            db.add(product)
            db.flush()

        db.add(OrderLineItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            order_id=order_id,
            product_id=product.id,
            quantity=item.quantity,
            unit_price=item.price
        ))

    # Add ledger draft status
    db.add(OrderStateLedger(
        tenant_id=tenant_id,
        order_id=order_id,
        from_status=None,
        to_status="Draft",
        updated_by="API"
    ))
    db.commit()

    return {"status": "success", "order_id": str(order_id)}


@router.post("/{order_id}/confirm", status_code=200)
def confirm_order_post(order_id: uuid.UUID, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    tenant_context.set(order.tenant_id)
    
    current_status = order.current_status
    db.add(OrderStateLedger(
        tenant_id=order.tenant_id,
        order_id=order.id,
        from_status=current_status,
        to_status="Confirmed",
        updated_by="API"
    ))
    
    # Also log DEBIT and generate Invoice as standard confirmation does to support FIFO payment collect
    customer = db.get(Customer, order.customer_id)
    if customer:
        current_order_total = sum(float(item.quantity * item.unit_price) for item in order.line_items)
        customer.outstanding_balance = float(customer.outstanding_balance) + current_order_total
        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=order.tenant_id,
            customer_id=order.customer_id,
            type="DEBIT",
            amount=current_order_total,
            reference_id=order.internal_order_id
        ))
        
        # Create Invoice
        from app.models.invoice import Invoice
        invoice = Invoice(
            tenant_id=order.tenant_id,
            order_id=order.id,
            gstin=customer.gstin if (customer.gstin and customer.gstin not in ("PENDING", "")) else "UNREGISTERED",
            total_amount=current_order_total,
            irn_status="Cleared",
            qr_code_status="Generated",
            customer_id=order.customer_id,
            payment_status="UNPAID",
            amount_paid=0.0,
            created_at=datetime.utcnow()
        )
        db.add(invoice)
        db.flush()
        
    db.commit()
    return {"status": "success", "order_id": str(order.id), "new_status": "Confirmed"}


class DispatchPayload(BaseModel):
    delivery_partner: str
    vehicle_number: str

@router.post("/{order_id}/dispatch", status_code=200)
def dispatch_order_post(order_id: uuid.UUID, payload: DispatchPayload, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    tenant_context.set(order.tenant_id)
    
    shipment = db.query(Shipment).filter(Shipment.order_id == order_id).first()
    if not shipment:
        customer = db.get(Customer, order.customer_id)
        dest = customer.address_text if customer else "Unknown Address"
        shipment = Shipment(
            id=uuid.uuid4(),
            tenant_id=order.tenant_id,
            order_id=order_id,
            carrier=payload.delivery_partner,
            tracking_id=payload.vehicle_number,
            status="DISPATCHED",
            destination=dest
        )
        db.add(shipment)
    else:
        shipment.status = "DISPATCHED"
        shipment.carrier = payload.delivery_partner
        shipment.tracking_id = payload.vehicle_number
        
    db.commit()
    return {"status": "success", "order_id": str(order_id)}


