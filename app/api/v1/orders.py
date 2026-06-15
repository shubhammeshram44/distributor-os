import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db, tenant_context
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.product import Product
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.ledger import CustomerLedger
from app.models.invoice import Invoice


from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.get("", status_code=status.HTTP_200_OK)
def list_orders(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Returns all orders for a tenant.
    """
    tenant_context.set(tenant_id)
    orders_invoices = (
        db.query(Order, Invoice)
        .outerjoin(Invoice, Invoice.order_id == Order.id)
        .filter(Order.tenant_id == tenant_id)
        .order_by(Order.created_at.desc())
        .all()
    )
    results = []
    
    for o, inv in orders_invoices:
        customer = db.get(Customer, o.customer_id)
        cust_name = customer.retailer_name if customer else "Unknown Retailer"

        # Calculate total amount
        amount_sum = sum(float(item.quantity * item.unit_price) for item in o.line_items)

        # Status badge conversion: Draft = "Pending", Confirmed = "Confirmed", Needs Review = "Needs Review"
        status_raw = o.current_status
        status_resolved = "Pending" if status_raw == "Draft" else status_raw

        # Payment status attributes
        payment_status = inv.payment_status if inv else "UNPAID"
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
            "amount_paid": amount_paid
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

            # 3. Aggregate Confirmed orders' outstanding balances
            total_confirmed_outstanding = 0.0
            confirmed_orders = db.query(Order).filter(Order.customer_id == order.customer_id).all()
            for co in confirmed_orders:
                if co.id != order.id and co.current_status == "Confirmed":
                    order_total = sum(float(line.quantity * line.unit_price) for line in co.line_items)
                    total_confirmed_outstanding += order_total

            # 4. Check Credit Limit
            combined_balance = total_confirmed_outstanding + current_order_total
            if combined_balance > float(customer.credit_limit):
                raise HTTPException(
                    status_code=400,
                    detail=f"Credit limit exceeded for customer '{customer.retailer_name}'. Combined balance: ₹{combined_balance:,.2f}, Credit Limit: ₹{customer.credit_limit:,.2f}"
                )

            # 5. Inventory Guardrail Validation Loop
            for item in items:
                # Resolve product variables dynamically
                prod_data = db.query(Product).filter(Product.id == item.product_id).first()
                if prod_data:
                    item.sku_code = prod_data.sku_id
                    item.product_name = prod_data.sku_id
                else:
                    item.sku_code = "UNKNOWN_SKU"
                    item.product_name = "Unknown Product"

                # Core inventory look up logic matching directives exactly
                product = db.query(Product).filter(Product.sku_id == item.sku_code).first()
                if product:
                    # Check if enough physical stock exists
                    if product.stock_quantity < item.quantity:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Insufficient stock for {item.product_name}. Requested: {item.quantity}, Available: {product.stock_quantity}"
                        )

            # Atomic Decrements: If all items pass, safely decrement stock counts
            for item in items:
                product = db.query(Product).filter(Product.sku_id == item.sku_code).first()
                if product:
                    product.stock_quantity -= item.quantity

            # Update Customer outstanding balance
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
        if prod and prod.sku_id == "UNMATCHED_SKU":
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

    # 3. Retrieve Tenant Info
    tenant = db.get(DistributorTenant, order.tenant_id)
    tenant_name = tenant.name if tenant else "S.V. Distributors"

    # 4. Retrieve Customer Info
    customer = db.get(Customer, order.customer_id)
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found associated with this order"
        )

    # 5. Fetch order line items
    items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order_id).all()

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

    # Header section (Tenant & Invoice ID/Date)
    invoice_id = f"INV-{order.internal_order_id}"
    order_date = order.created_at.strftime("%Y-%m-%d")
    
    header_left = f"<b>{tenant_name}</b><br/>B2B Distributor Services<br/>Email: billing@{tenant_name.lower().replace(' ', '').replace('.', '')}.com"
    header_right = f"<b>TAX INVOICE</b><br/>Invoice ID: {invoice_id}<br/>Date: {order_date}<br/>Status: <b>Confirmed</b>"

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

    # Customer Profile Section
    cust_left = f"<b>BILL TO:</b><br/>{customer.retailer_name}<br/>{customer.address_text}<br/>GSTIN: {customer.gstin}"
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

    # Tax Summary Block
    gst_rate = 0.18
    gst = subtotal * gst_rate
    grand_total = subtotal + gst

    summary_left = "<b>Declaration:</b><br/>We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct."
    summary_right_data = [
        [Paragraph("Subtotal:", body_style), Paragraph(f"₹ {subtotal:,.2f}", ParagraphStyle('RightAlign', parent=body_style, alignment=2))],
        [Paragraph("GST (18%):", body_style), Paragraph(f"₹ {gst:,.2f}", ParagraphStyle('RightAlign', parent=body_style, alignment=2))],
        [Paragraph("<b>Total Payable:</b>", body_bold), Paragraph(f"<b>₹ {grand_total:,.2f}</b>", ParagraphStyle('RightAlignBold', parent=body_bold, alignment=2))]
    ]
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
    
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice_{order_id}.pdf"
        }
    )


@router.get("/{order_id}", status_code=status.HTTP_200_OK)
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
        "payment_status": invoice.payment_status if invoice else "UNPAID",
        "amount_paid": float(invoice.amount_paid) if invoice else 0.0,
        "payments_allocated": payments_allocated
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

    db.commit()
    return {
        "status": "success",
        "order_id": str(new_order.id),
        "internal_order_id": generated_order_id,
        "new_status": payload.status
    }

