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
from app.models.demand_gap import DemandGap
from app.services.tenant_service import resolve_tenant_id
from app.services.demo_service import ensure_demo_data
from app.services.payment_service import reconcile_payments_and_invoices

logger = logging.getLogger(__name__)

# Dynamically override Order.total_amount property to support setter operations in API
original_total_amount_getter = Order.total_amount.fget
def get_total_amount(self):
    if hasattr(self, "_total_amount") and self._total_amount is not None:
        return self._total_amount
    return original_total_amount_getter(self)
def set_total_amount(self, value):
    self._total_amount = value
Order.total_amount = property(get_total_amount, set_total_amount)



class OrderLineItemResponse(BaseModel):
    id: str
    product_id: str | None = None
    sku_code: str | None = None
    product_name: str | None = None
    quantity: int
    allocated_quantity: int | None = None
    unit_price: float

    class Config:
        from_attributes = True


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
    raw_source_text: str | None = None
    line_items: list[OrderLineItemResponse] = []
    invoice_id: str | None = None


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
    raw_source_text: str | None = None
    invoice_id: str | None = None


from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.get("", status_code=status.HTTP_200_OK)
def list_orders(
    tenant_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    status_filter: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns paginated orders for a tenant with optional search and sorting.
    """
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    if str(resolved_tenant_id) == "d3b07384-d113-4956-a5d2-64be7357c11d":
        ensure_demo_data(db, resolved_tenant_id)
    tenant_context.set(resolved_tenant_id)

    # Base filter
    filters = [Order.tenant_id == resolved_tenant_id]

    # Server-side search: filter by customer name or order ID prefix
    if search:
        search_term = f"%{search.lower()}%"
        customer_ids_matching = db.execute(
            sa_select(Customer.id).where(
                and_(
                    Customer.tenant_id == resolved_tenant_id,
                    func.lower(Customer.retailer_name).like(search_term)
                )
            )
        ).scalars().all()
        filters.append(
            (func.lower(Order.internal_order_id).like(search_term)) |
            (Order.customer_id.in_(customer_ids_matching))
        )

    # Sorting
    _sort_col = {
        "created_at": Order.created_at,
        "amount": None,  # computed, handled below
    }.get(sort_by, Order.created_at)

    order_clause = _sort_col.desc() if sort_order == "desc" else _sort_col.asc()

    # Count total before pagination
    total_count = db.execute(
        sa_select(func.count(Order.id)).where(and_(*filters))
    ).scalar() or 0

    query = (
        sa_select(Order, Invoice)
        .outerjoin(Invoice, Invoice.order_id == Order.id)
        .options(
            joinedload(Order.customer),
            joinedload(Order.line_items).joinedload(OrderLineItem.product)
        )
        .where(and_(*filters))
        .order_by(order_clause)
        .offset(skip)
        .limit(limit)
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
        amount_sum = sum(
            float((item.allocated_quantity if item.allocated_quantity is not None else item.quantity) * item.unit_price)
            for item in o.line_items
        )

        # Status badge conversion: Draft = "Pending", Confirmed = "Confirmed", Needs Review = "Needs Review"
        status_raw = o.current_status
        has_triage_sku = any(
            item.product_id is None or (item.product is not None and item.product.sku_id in ("UNMATCHED_SKU", "UNMATCHED_TRIAGE_SKU"))
            for item in o.line_items
        )
        if has_triage_sku or status_raw == "pending_review":
            status_raw = "pending_review"
        status_resolved = "Pending" if status_raw == "Draft" else ("Needs Review" if status_raw in ["NEEDS_REVIEW", "pending_review"] else status_raw)

        # Payment status attributes
        payment_status = inv.payment_status if inv else "UNPAID"
        amount_paid = float(inv.amount_paid) if inv else 0.0

        line_items_data = []
        for item in o.line_items:
            sku = item.product.sku_id if item.product else "UNMATCHED_SKU"
            p_name = f"{item.product.brand} {item.product.category}" if item.product else (item.unmatched_raw_text or "Unknown Product")
            line_items_data.append({
                "id": str(item.id),
                "product_id": str(item.product_id) if item.product_id else None,
                "sku_code": sku,
                "product_name": p_name,
                "quantity": item.quantity,
                "allocated_quantity": item.allocated_quantity,
                "unit_price": float(item.unit_price)
            })

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
            "invoice_type": o.invoice_type,
            "raw_source_text": o.raw_source_text,
            "line_items": line_items_data,
            "invoice_id": str(inv.id) if inv else None
        })

    return {"items": results, "total": total_count, "skip": skip, "limit": limit}


def process_order_self_learning(db: Session, order_id: uuid.UUID, tenant_id: uuid.UUID):
    """
    Isolated database sub-transaction to process self-learning safely, registering
    unique permanent product aliases, then clearing unmatched_raw_text on line items.
    """
    from app.models.order import OrderLineItem
    from app.models.product import ProductAlias
    import logging
    logger = logging.getLogger("uvicorn.error")

    try:
        with db.begin_nested():
            items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order_id).all()
            for item in items:
                if item.unmatched_raw_text and item.product_id is not None:
                    clean_alias = item.unmatched_raw_text.lower().strip()
                    existing = db.query(ProductAlias).filter(
                        ProductAlias.tenant_id == tenant_id,
                        ProductAlias.alias_name.ilike(clean_alias)
                    ).first()
                    if not existing:
                        new_alias = ProductAlias(
                            id=uuid.uuid4(),
                            tenant_id=tenant_id,
                            product_id=item.product_id,
                            alias_name=item.unmatched_raw_text.strip()
                        )
                        db.add(new_alias)
                    item.unmatched_raw_text = None
            db.flush()
    except Exception as e:
        logger.error("Self-learning sub-transaction failed: %s", str(e))


class StatusUpdatePayload(BaseModel):
    to_status: str


@router.post("/{order_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Cancels a Draft or Confirmed order. Reverses inventory reservation and
    customer outstanding balance if cancelling from Confirmed.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    tenant_context.set(order.tenant_id)
    current = order.current_status

    if current not in ("Draft", "Pending", "Confirmed", "Needs Review"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status '{current}'. Only Draft/Confirmed orders can be cancelled."
        )

    try:
        items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order_id).all()

        # If Confirmed, reverse inventory and customer balance
        if current == "Confirmed":
            customer = db.get(Customer, order.customer_id)
            order_total = sum(float(i.quantity * i.unit_price) for i in items)

            # Restore inventory
            for item in items:
                db.execute(
                    sa_update(Inventory)
                    .where(
                        and_(
                            Inventory.tenant_id == order.tenant_id,
                            Inventory.sku_id == item.product_id
                        )
                    )
                    .values(quantity_on_hand=Inventory.quantity_on_hand + item.quantity)
                )

            # Reverse customer outstanding balance
            if customer:
                customer.outstanding_balance = max(
                    0.0, float(customer.outstanding_balance) - order_total
                )

            # Mark invoice as cancelled if it exists
            invoice = db.query(Invoice).filter(Invoice.order_id == order.id).first()
            if invoice:
                invoice.payment_status = "CANCELLED"

        db.add(OrderStateLedger(
            tenant_id=order.tenant_id,
            order_id=order.id,
            from_status=current,
            to_status="Cancelled",
            updated_by="system_cancel_request"
        ))

        db.commit()
        return {"status": "success", "order_id": str(order.id), "new_status": "Cancelled"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Cancellation failed: {str(e)}")


import csv as csv_module


@router.get("/export", status_code=status.HTTP_200_OK)
def export_orders_csv(
    tenant_id: uuid.UUID | None = None,
    search: str | None = None,
    status_filter: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Streams all orders as a CSV file for the active tenant.
    """
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    tenant_context.set(resolved_tenant_id)

    filters = [Order.tenant_id == resolved_tenant_id]
    if search:
        search_term = f"%{search.lower()}%"
        customer_ids = db.execute(
            sa_select(Customer.id).where(
                and_(
                    Customer.tenant_id == resolved_tenant_id,
                    func.lower(Customer.retailer_name).like(search_term)
                )
            )
        ).scalars().all()
        filters.append(
            (func.lower(Order.internal_order_id).like(search_term)) |
            (Order.customer_id.in_(customer_ids))
        )

    orders = (
        db.execute(
            sa_select(Order)
            .options(joinedload(Order.line_items).joinedload(OrderLineItem.product))
            .where(and_(*filters))
            .order_by(Order.created_at.desc())
        )
        .unique()
        .scalars()
        .all()
    )

    cust_ids = list({o.customer_id for o in orders})
    custs = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(cust_ids)).all()} if cust_ids else {}

    output = io.StringIO()
    writer = csv_module.writer(output)
    writer.writerow([
        "Order ID", "Customer", "Channel", "Amount (₹)", "Status",
        "Payment Status", "Amount Paid (₹)", "Invoice Type", "Created At"
    ])
    for o in orders:
        cust = custs.get(o.customer_id)
        amount = sum(float(i.quantity * i.unit_price) for i in o.line_items)
        writer.writerow([
            o.internal_order_id,
            cust.retailer_name if cust else "Unknown",
            o.source,
            f"{amount:.2f}",
            o.current_status,
            o.payment_status,
            "",
            o.invoice_type,
            o.created_at.strftime("%Y-%m-%d %H:%M")
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders_export.csv"}
    )

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

    _VALID_TRANSITIONS: dict[str, set[str]] = {
        "Draft": {"Confirmed"},
        "NEEDS_REVIEW": set(),  # Must resolve via triage first
        "Confirmed": {"Dispatched"},
        "Dispatched": {"Delivered"},
        "Delivered": set(),
    }
    current_from_status = order.current_status
    allowed = _VALID_TRANSITIONS.get(current_from_status, set())
    if payload.to_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition '{current_from_status}' → '{payload.to_status}'. Allowed: {sorted(allowed) or 'none (terminal or triage state)'}"
        )

    try:
        # Fetch Child Line Items
        items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order_id).all()

        if payload.to_status == "Confirmed":
            from app.services.order_confirmation_service import confirm_order
            confirm_order(db, order, updated_by="system_orders_agent")
        else:
            # Record state transition to OrderStateLedger
            current_status = order.current_status
            db.add(OrderStateLedger(
                tenant_id=order.tenant_id,
                order_id=order.id,
                from_status=current_status,
                to_status=payload.to_status,
                updated_by="system_orders_agent"
            ))
            order.status = payload.to_status

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

# ─────────────────────────────────────────────────────────────────
# FUTURE USE: Call restore_inventory_for_order(db, order) from any
# cancel or reject endpoint when order.status == "Confirmed".
# Do not call this function from anywhere until cancel/reject
# order UI and endpoint is built.
# ─────────────────────────────────────────────────────────────────

# INVENTORY_DEDUCTION_TRIGGER = "on_confirmation"  # Options: "on_confirmation" | "on_dispatch"
# Change this flag when business logic changes. Currently: inventory deducted on confirmation.

def restore_inventory_for_order(db: Session, order: Order) -> None:
    """
    Restores inventory when a confirmed order is cancelled or rejected.
    Call this from any cancel/reject endpoint ONLY if order.status == "Confirmed".
    
    If INVENTORY_DEDUCTION_TRIGGER changes to "on_dispatch" in future,
    this function should only be called if order.status == "Dispatched".
    """
    for item in order.line_items:
        inv_record = db.query(Inventory).filter(
            Inventory.tenant_id == order.tenant_id,
            Inventory.sku_id == item.product_id
        ).first()
        if inv_record:
            restored_qty = item.allocated_quantity if item.allocated_quantity is not None else item.quantity
            inv_record.quantity_committed = max(0, (inv_record.quantity_committed or 0) - restored_qty)
            logger.info(
                "Inventory restored (committed pool decremented): product=%s qty=%s for order=%s",
                item.product_id, restored_qty, order.id
            )


class ItemResolvePayload(BaseModel):
    sku_code: str
    quantity: int
    save_as_permanent_alias: bool | None = False

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

    # 3. Overwrite the order item's fields (preserving unmatched_raw_text for global order confirmation)
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
        if i.product_id is None or (prod and prod.sku_id in ("UNMATCHED_SKU", "UNMATCHED_TRIAGE_SKU")):
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
        order.status = new_status

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
    is_gst = order.invoice_type != "RETAIL_INVOICE"

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
        qty = item.allocated_quantity if item.allocated_quantity is not None else item.quantity
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
        "invoice_type": order.invoice_type,
        "raw_source_text": order.raw_source_text,
        "invoice_id": str(invoice.id) if invoice else None
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

            # Without a matching Inventory row, order_confirmation_service
            # treats this SKU as having 0 stock and zeroes the line item
            # out entirely. Seed it with the ordered quantity so this
            # ad-hoc/fallback product is immediately billable.
            db.add(Inventory(
                id=uuid.uuid4(),
                tenant_id=payload.tenant_id,
                sku_id=product.id,
                location="Aisle-A1",
                quantity_on_hand=item.quantity,
                quantity_committed=0,
                low_stock_threshold=10
            ))
            db.flush()

        db.add(OrderLineItem(
            id=uuid.uuid4(),
            tenant_id=payload.tenant_id,
            order_id=new_order.id,
            product_id=product.id,
            quantity=item.quantity,
            unit_price=item.unit_price
        ))

    db.flush()
    db.refresh(new_order)

    if payload.status == "Confirmed":
        from app.services.order_confirmation_service import confirm_order
        confirm_order(db, new_order, updated_by="operator")
    else:
        # Add ledger transition entry
        db.add(OrderStateLedger(
            tenant_id=payload.tenant_id,
            order_id=new_order.id,
            from_status=None,
            to_status=payload.status,
            updated_by="operator"
        ))
        new_order.status = payload.status

    db.commit()
    return {
        "status": "success",
        "order_id": str(new_order.id),
        "internal_order_id": generated_order_id,
        "new_status": payload.status
    }


class OrderPatchPayload(BaseModel):
    invoice_type: typing.Literal["GST_TAX_INVOICE", "RETAIL_INVOICE", "UNSPECIFIED"]


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
            # NOTE: id must be a real UUID (Product.id is a UUID column).
            # Using item.sku_id (a business SKU string) directly here
            # crashes with a Postgres DataError on any non-UUID SKU.
            product = Product(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                sku_id=item.sku_id,
                brand="Generic",
                category="Grocery",
                pack_size="1 unit",
                base_price=item.price
            )
            db.add(product)
            db.flush()

            # Without a matching Inventory row, order_confirmation_service
            # treats this SKU as having 0 stock and zeroes the line item
            # out entirely. Seed it with the ordered quantity so this
            # ad-hoc/fallback product is immediately billable.
            db.add(Inventory(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                sku_id=product.id,
                location="Aisle-A1",
                quantity_on_hand=item.quantity,
                quantity_committed=0,
                low_stock_threshold=10
            ))
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
    new_order.status = "Draft"
    db.commit()

    return {"status": "success", "order_id": str(order_id)}


@router.post("/{order_id}/confirm", status_code=200)
def confirm_order_post(order_id: uuid.UUID, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    tenant_context.set(order.tenant_id)

    from app.services.order_confirmation_service import confirm_order
    confirm_order(db, order, updated_by="API")
    db.commit()

    # Fire order_confirmed notification (non-blocking)
    try:
        customer = db.get(Customer, order.customer_id)
        if customer:
            # Eagerly load relationships so they are in-memory before background task starts
            for item in order.line_items:
                if item.product:
                    _ = item.product.brand

            import asyncio
            from app.services.notification_service import NotificationService
            import os

            tenant_obj = db.get(DistributorTenant, order.tenant_id)

            async def fire_notifications(tenant_val, customer_val, order_val):
                try:
                    notification_service = NotificationService(
                        evolution_base_url=os.getenv("EVOLUTION_API_URL", "http://34.158.60.42:8080"),
                        api_key=os.getenv("EVOLUTION_API_KEY", "distributorbotkey2026")
                    )
                    await notification_service.notify(
                        event="order_confirmed",
                        tenant=tenant_val,
                        customer=customer_val,
                        order=order_val,
                        db=db
                    )
                except Exception as inner_ex:
                    logger.warning("Notification fire failed silently: %s", str(inner_ex))

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(fire_notifications(tenant_obj, customer, order))
            else:
                asyncio.run(fire_notifications(tenant_obj, customer, order))
    except Exception as e:
        logger.warning("Notification fire setup failed silently: %s", str(e))

    return {"status": "success", "order_id": str(order.id), "new_status": "Confirmed"}


# ---------------------------------------------------------------------------
# Batch-Confirm: atomic resolve + self-learning + order confirmation in one shot
# ---------------------------------------------------------------------------

class BatchLineItemChange(BaseModel):
    """Represents a single staged line-item resolution from the frontend."""
    item_id: str
    product_id: str


class BatchConfirmOrderPayload(BaseModel):
    """
    Payload for the atomic batch-confirm route.
    `resolved_items` contains staged resolutions mapped directly by product_id.
    """
    invoice_type: str | None = None
    resolved_items: list[BatchLineItemChange] = []


@router.post("/{order_id}/batch-confirm", status_code=200)
def batch_confirm_order(
    order_id: uuid.UUID,
    payload: BatchConfirmOrderPayload,
    db: Session = Depends(get_db),
):
    """
    Atomic batch-confirm endpoint.

    1. Validates the order exists and is in a confirmable state.
    2. Applies invoice type update if provided.
    3. Applies every staged line-item resolution (product_id) in a single savepoint block.
    4. Runs the self-learning alias engine to register new ProductAliases and
       clear unmatched_raw_text fields.
    5. Transitions the order to "Confirmed", debits the customer ledger, and
       generates the invoice — all within a single atomic session commit.
    """
    from app.models.product import ProductAlias

    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    tenant_context.set(order.tenant_id)

    current_status = order.current_status
    if current_status == "Confirmed":
        raise HTTPException(
            status_code=409,
            detail="Order is already confirmed.",
        )

    try:
        # Save invoice preference if supplied
        if payload.invoice_type:
            order.invoice_type = payload.invoice_type

        # ── PHASE 1: Apply staged line-item resolutions ─────────────────────
        if payload.resolved_items:
            with db.begin_nested():
                for change in payload.resolved_items:
                    try:
                        item_uuid = uuid.UUID(change.item_id)
                    except ValueError:
                        raise HTTPException(
                            status_code=422,
                            detail=f"Invalid item_id format: {change.item_id}",
                        )

                    item = db.get(OrderLineItem, item_uuid)
                    if not item or item.order_id != order_id:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Line item {change.item_id} not found on this order.",
                        )

                    try:
                        prod_uuid = uuid.UUID(change.product_id)
                    except ValueError:
                        raise HTTPException(
                            status_code=422,
                            detail=f"Invalid product_id format: {change.product_id}",
                        )

                    # Resolve product by ID
                    product = db.get(Product, prod_uuid)
                    if not product:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Product with ID '{change.product_id}' not found.",
                        )

                    item.product_id = product.id
                    item.unit_price = product.base_price

                db.flush()

        # ── PHASE 2: Self-learning alias engine ─────────────────────────────
        process_order_self_learning(db, order.id, order.tenant_id)

        db.refresh(order)  # ensure line_items reflect Phase 1 changes
        from app.services.order_confirmation_service import confirm_order
        confirm_order(db, order, updated_by="API")

        # Create PaymentSession eagerly on confirmation
        try:
            from app.services.payment_session_service import get_or_create_payment_session
            from app.models.payment_session import PaymentSession
            from app.models.invoice import Invoice
            from app.models.customer import Customer
            
            customer = db.get(Customer, order.customer_id)
            new_invoice = db.query(Invoice).filter(Invoice.order_id == order.id).first()
            if customer and new_invoice:
                payment_session = get_or_create_payment_session(
                    db=db,
                    invoice=new_invoice,
                    customer=customer,
                    order_id=order.id,
                    tenant_id=order.tenant_id
                )
                if payment_session:
                    logger.info("PaymentSession created: %s link=%s", payment_session.id, payment_session.payment_link_url)
                else:
                    logger.info("PaymentSession skipped for order %s (zero amount or limit exceeded)", order.id)
        except Exception as e:
            logger.warning("PaymentSession creation failed silently: %s", str(e))

        db.commit()

        # Fire order_confirmed notification (non-blocking)
        try:
            customer = db.get(Customer, order.customer_id)
            if customer:
                # Eagerly load relationships so they are in-memory before background task starts
                for item in order.line_items:
                    if item.product:
                        _ = item.product.brand

                import asyncio
                from app.services.notification_service import NotificationService
                import os

                tenant_obj = db.get(DistributorTenant, order.tenant_id)

                async def fire_notifications(tenant_val, customer_val, order_val):
                    try:
                        notification_service = NotificationService(
                            evolution_base_url=os.getenv("EVOLUTION_API_URL", "http://34.158.60.42:8080"),
                            api_key=os.getenv("EVOLUTION_API_KEY", "distributorbotkey2026")
                        )
                        await notification_service.notify(
                            event="order_confirmed",
                            tenant=tenant_val,
                            customer=customer_val,
                            order=order_val,
                            db=db
                        )
                    except Exception as inner_ex:
                        logger.warning("Notification fire failed silently: %s", str(inner_ex))

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    loop.create_task(fire_notifications(tenant_obj, customer, order))
                else:
                    asyncio.run(fire_notifications(tenant_obj, customer, order))
        except Exception as e:
            logger.warning("Notification fire setup failed silently: %s", str(e))

        logger.info(
            "batch_confirm_order: Order %s confirmed with %d staged change(s).",
            order_id,
            len(payload.resolved_items),
        )
        return {
            "status": "success",
            "order_id": str(order.id),
            "new_status": "Confirmed",
            "changes_applied": len(payload.resolved_items),
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("batch_confirm_order crash for order %s: %s", order_id, str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Batch-confirm transaction failed: {str(exc)}",
        )


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
    from app.models.customer import Customer
    customer = db.query(Customer).filter(
        Customer.id == order.customer_id,
        Customer.tenant_id == order.tenant_id
    ).first()
    dest = customer.address_text if customer else "Unknown Address"

    if not shipment:
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

    # Check if OrderStateLedger model exists
    has_ledger = False
    try:
        from app.models.order import OrderStateLedger
        has_ledger = True
    except ImportError:
        pass

    if has_ledger:
        db.add(OrderStateLedger(
            tenant_id=order.tenant_id,
            order_id=order.id,
            from_status=order.current_status,
            to_status="Dispatched",
            updated_by="operator"
        ))
        order.status = "Dispatched"
    else:
        if hasattr(order, "status"):
            setattr(order, "status", "Dispatched")
        
    db.commit()

    # Fire order_dispatched notification (non-blocking)
    try:
        if customer:
            # Eagerly load relationships so they are in-memory before background task starts
            for item in order.line_items:
                if item.product:
                    _ = item.product.brand

            import asyncio
            from app.services.notification_service import NotificationService
            import os

            tenant_obj = db.get(DistributorTenant, order.tenant_id)

            async def fire_notifications(tenant_val, customer_val, order_val):
                try:
                    notification_service = NotificationService(
                        evolution_base_url=os.getenv("EVOLUTION_API_URL", "http://34.158.60.42:8080"),
                        api_key=os.getenv("EVOLUTION_API_KEY", "distributorbotkey2026")
                    )
                    await notification_service.notify(
                        event="order_dispatched",
                        tenant=tenant_val,
                        customer=customer_val,
                        order=order_val,
                        db=db
                    )
                except Exception as inner_ex:
                    logger.warning("Notification fire failed silently: %s", str(inner_ex))

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(fire_notifications(tenant_obj, customer, order))
            else:
                asyncio.run(fire_notifications(tenant_obj, customer, order))
    except Exception as e:
        logger.warning("Notification fire setup failed silently: %s", str(e))

    return {"status": "success", "order_id": str(order_id)}


class DeliveryEventRequest(BaseModel):
    status: str = "delivered"
    source: str = "manual"  # manual | shiprocket | dunzo | porter | custom
    delivery_timestamp: typing.Optional[datetime] = None
    proof: typing.Optional[str] = None
    tenant_id: str

@router.post("/{order_id}/delivery-event", status_code=200)
def record_delivery_event(
    order_id: uuid.UUID,
    payload: DeliveryEventRequest,
    db: Session = Depends(get_db)
):
    # 1. Fetch order by order_id and tenant_id
    order = db.query(Order).filter(Order.id == order_id, Order.tenant_id == payload.tenant_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    tenant_context.set(order.tenant_id)

    # Check if OrderStateLedger model exists
    has_ledger = False
    try:
        from app.models.order import OrderStateLedger
        has_ledger = True
    except ImportError:
        pass

    # 2. Update order status to Delivered
    if has_ledger:
        current_status = order.current_status
        db.add(OrderStateLedger(
            tenant_id=order.tenant_id,
            order_id=order.id,
            from_status=current_status,
            to_status="Delivered",
            updated_by=payload.source
        ))
        order.status = "Delivered"
    else:
        if hasattr(order, "status"):
            setattr(order, "status", "Delivered")

    # 3. Update order.delivered_at = delivery_timestamp or datetime.utcnow()
    order.delivered_at = payload.delivery_timestamp or datetime.utcnow()

    # 4. Store source in order.delivery_source
    order.delivery_source = payload.source

    # 5. Commit
    db.commit()
    db.refresh(order)

    # 6. Fire order_delivered notification via NotificationService (non-blocking)
    try:
        customer = db.get(Customer, order.customer_id)
        if customer:
            for item in order.line_items:
                if item.product:
                    _ = item.product.brand

            import asyncio
            from app.services.notification_service import NotificationService
            import os

            tenant_obj = db.get(DistributorTenant, order.tenant_id)

            async def fire_notifications(tenant_val, customer_val, order_val):
                try:
                    notification_service = NotificationService(
                        evolution_base_url=os.getenv("EVOLUTION_API_URL", "http://34.158.60.42:8080"),
                        api_key=os.getenv("EVOLUTION_API_KEY", "distributorbotkey2026")
                    )
                    await notification_service.notify(
                        event="order_delivered",
                        tenant=tenant_val,
                        customer=customer_val,
                        order=order_val,
                        db=db
                    )
                except Exception as inner_ex:
                    logger.warning("Notification fire failed silently: %s", str(inner_ex))

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(fire_notifications(tenant_obj, customer, order))
            else:
                asyncio.run(fire_notifications(tenant_obj, customer, order))
    except Exception as e:
        logger.warning("Notification fire setup failed silently: %s", str(e))

    # 7. Return updated order details
    return {
        "id": str(order.id),
        "order_id": order.internal_order_id,
        "status": "Delivered",
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "delivery_source": order.delivery_source
    }


@router.get("/{order_id}/risk-assessment")
def get_order_risk_assessment(
    order_id: uuid.UUID,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from app.models.payment import Payment
    from app.models.invoice import Invoice

    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # Set tenant context
    tenant_context.set(order.tenant_id)

    customer = db.get(Customer, order.customer_id)
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    tenant = db.get(DistributorTenant, order.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail="Tenant not found"
        )

    current_order_total = sum(
        float((item.allocated_quantity if item.allocated_quantity is not None else item.quantity) * item.unit_price)
        for item in order.line_items
    )

    # Outstanding and credit
    outstanding = float(customer.outstanding_balance)
    credit_limit = float(customer.credit_limit)
    credit_utilisation = (outstanding / credit_limit * 100) if credit_limit > 0 else 0

    # Overdue days — days since oldest unpaid invoice
    oldest_unpaid = db.query(func.min(Invoice.created_at))\
        .filter(Invoice.customer_id == customer.id, Invoice.payment_status != "PAID")\
        .scalar()
    overdue_days = (datetime.utcnow() - oldest_unpaid).days if oldest_unpaid else 0

    # Average days to pay — from payment history
    payments = db.query(Payment)\
        .filter(Payment.customer_id == customer.id)\
        .order_by(Payment.created_at.desc())\
        .limit(10).all()
    avg_days_to_pay = 0.0  # compute from payment vs invoice dates if available, else 0
    diffs = []
    for p in payments:
        for link in p.invoice_links:
            inv = db.get(Invoice, link.invoice_id)
            if inv and inv.created_at and p.created_at:
                diffs.append((p.created_at - inv.created_at).days)
    if diffs:
        avg_days_to_pay = float(sum(diffs) / len(diffs))

    # Order frequency drop — compare last 30 days vs prior 30 days
    now = datetime.utcnow()
    recent_orders = db.query(func.count(Order.id))\
        .filter(Order.customer_id == customer.id,
                Order.created_at >= now - timedelta(days=30)).scalar() or 0
    prior_orders = db.query(func.count(Order.id))\
        .filter(Order.customer_id == customer.id,
                Order.created_at >= now - timedelta(days=60),
                Order.created_at < now - timedelta(days=30)).scalar() or 0
    frequency_drop_pct = ((prior_orders - recent_orders) / prior_orders * 100) if prior_orders > 0 else 0

    # Last payment date
    last_payment = db.query(Payment)\
        .filter(Payment.customer_id == customer.id)\
        .order_by(Payment.created_at.desc()).first()
    last_payment_date = last_payment.created_at.date() if last_payment else None
    days_since_last_payment = (datetime.utcnow().date() - last_payment_date).days if last_payment_date else None

    score = 0
    signals = []

    if credit_limit > 0:
        if credit_utilisation > 90:
            score += 40
            signals.append(f"Credit {credit_utilisation:.0f}% utilised (₹{outstanding:,.0f} of ₹{credit_limit:,.0f})")
        elif credit_utilisation > 70:
            score += 25
            signals.append(f"Credit {credit_utilisation:.0f}% utilised")
        elif credit_utilisation > 50:
            score += 10
            signals.append(f"Credit {credit_utilisation:.0f}% utilised")

    if overdue_days > 30:
        score += 30
        signals.append(f"Overdue {overdue_days} days")
    elif overdue_days > 15:
        score += 20
        signals.append(f"Overdue {overdue_days} days")
    elif overdue_days > 7:
        score += 10
        signals.append(f"Overdue {overdue_days} days")

    if frequency_drop_pct > 40:
        score += 10
        signals.append(f"Orders dropped {frequency_drop_pct:.0f}% this month")

    if days_since_last_payment and days_since_last_payment > 45:
        score += 10
        signals.append(f"No payment in {days_since_last_payment} days")

    if score >= 70:
        level = "high_risk"
    elif score >= 40:
        level = "caution"
    else:
        level = "clear"

    if level == "high_risk" and overdue_days > 30:
        recommendation = f"Collect ₹{min(current_order_total, outstanding * 0.5):,.0f} advance before confirming this order."
    elif level == "high_risk" and credit_utilisation > 90:
        recommendation = f"Credit limit nearly exhausted. Request partial payment of ₹{outstanding * 0.3:,.0f} before confirming."
    elif level == "high_risk":
        recommendation = "High risk customer. Consider requesting advance payment before confirming."
    elif level == "caution" and overdue_days > 7:
        recommendation = f"Payment overdue {overdue_days} days. Follow up on outstanding ₹{outstanding:,.0f} before confirming."
    elif level == "caution":
        recommendation = "Monitor this customer. Consider requesting UPI payment before dispatch."
    else:
        recommendation = "Customer is in good standing. Safe to confirm."

    return {
        "order_id": str(order_id),
        "customer_id": str(customer.id),
        "customer_name": customer.retailer_name,
        "score": score,
        "level": level,
        "signals": signals,
        "recommendation": recommendation,
        "outstanding_balance": outstanding,
        "credit_limit": credit_limit,
        "credit_utilisation_pct": round(credit_utilisation, 1),
        "overdue_days": overdue_days,
        "last_payment_date": str(last_payment_date) if last_payment_date else None,
        "days_since_last_payment": days_since_last_payment,
        "current_order_total": current_order_total,
        "order_frequency_drop_pct": round(frequency_drop_pct, 1)
    }


