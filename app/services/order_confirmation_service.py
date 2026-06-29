import uuid
import logging
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.customer import Customer
from app.models.ledger import CustomerLedger
from app.models.invoice import Invoice
from app.models.inventory import Inventory
from app.models.demand_gap import DemandGap
from app.models.product import Product

logger = logging.getLogger("uvicorn.error")

def confirm_order(db: Session, order: Order, updated_by: str) -> None:
    """
    Consolidated order confirmation and billing logic.
    Refactored to be reusable across all entry points in the system.
    """
    # 1. Resolve from_status
    from_status = order.current_status

    # 2. Fetch Customer
    customer = db.get(Customer, order.customer_id)
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    # 3. Calculate current order total (requested total)
    # Fetch Child Line Items to make sure they are fresh/loaded
    items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    current_order_total = sum(float(item.quantity * item.unit_price) for item in items)

    # 4. Check Credit Limit — uses original requested total
    total_confirmed_outstanding = 0.0
    confirmed_orders = db.query(Order).filter(Order.customer_id == order.customer_id).all()
    for co in confirmed_orders:
        if co.id != order.id and co.current_status == "Confirmed":
            order_total = sum(float(line.quantity * line.unit_price) for line in co.line_items)
            total_confirmed_outstanding += order_total

    combined_balance = total_confirmed_outstanding + current_order_total
    if combined_balance > float(customer.credit_limit):
        try:
            db.add(DemandGap(
                id=uuid.uuid4(),
                tenant_id=order.tenant_id,
                order_id=order.id,
                customer_id=order.customer_id,
                product_id=None,
                reason_code="CREDIT_LIMIT",
                status="OPEN",
                resolved_at=None,
                requested_qty=None,
                allocated_qty=None,
                gap_qty=None,
                unit_price=None,
                revenue_at_risk=current_order_total,
                created_at=datetime.utcnow(),
            ))
            db.commit()
        except Exception as _gap_err:
            logger.warning("Failed to persist CREDIT_LIMIT DemandGap: %s", _gap_err)
            db.rollback()
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

    # 5. Single-pass inventory allocation — partial allocation replaces hard reject.
    for item in items:
        inv_record = db.query(Inventory).filter(
            Inventory.tenant_id == order.tenant_id,
            Inventory.sku_id == item.product_id,
        ).first()

        available = inv_record.quantity_on_hand if inv_record else 0
        allocated = min(item.quantity, available)
        item.allocated_quantity = allocated
        gap_qty = item.quantity - allocated

        if gap_qty > 0:
            # Check if DemandGap already exists for this order+product to avoid duplicates
            existing_gap = db.query(DemandGap).filter(
                DemandGap.order_id == order.id,
                DemandGap.product_id == item.product_id,
                DemandGap.reason_code == "STOCK_SHORTAGE"
            ).first()
            if not existing_gap:
                db.add(DemandGap(
                    id=uuid.uuid4(),
                    tenant_id=order.tenant_id,
                    order_id=order.id,
                    customer_id=order.customer_id,
                    product_id=item.product_id,
                    reason_code="STOCK_SHORTAGE",
                    status="OPEN",
                    resolved_at=None,
                    requested_qty=item.quantity,
                    allocated_qty=allocated,
                    gap_qty=gap_qty,
                    unit_price=float(item.unit_price),
                    revenue_at_risk=float(gap_qty * item.unit_price),
                    created_at=datetime.utcnow(),
                ))

        if inv_record and allocated > 0:
            inv_record.quantity_on_hand -= allocated

    db.flush()

    # 6. Recompute billing total using allocated quantities (not original quantities).
    billing_total = sum(
        float(
            (item.allocated_quantity if item.allocated_quantity is not None else item.quantity)
            * item.unit_price
        )
        for item in items
    )

    # Update Customer outstanding balance
    customer.outstanding_balance = float(customer.outstanding_balance) + billing_total

    # Record a DEBIT transaction in the customer ledger
    db.add(CustomerLedger(
        id=uuid.uuid4(),
        tenant_id=order.tenant_id,
        customer_id=order.customer_id,
        type="DEBIT",
        amount=billing_total,
        reference_id=order.internal_order_id
    ))

    # Create Invoice directly
    invoice = Invoice(
        tenant_id=order.tenant_id,
        order_id=order.id,
        gstin=customer.gstin if customer.gstin else "29AAAAA1111A1Z1",
        total_amount=billing_total,
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
    from app.services.payment_service import reconcile_payments_and_invoices
    reconcile_payments_and_invoices(db, order.tenant_id, order.customer_id)

    # Process bulk self-learning
    from app.api.v1.orders import process_order_self_learning
    process_order_self_learning(db, order.id, order.tenant_id)

    # Record state transition to OrderStateLedger
    db.add(OrderStateLedger(
        tenant_id=order.tenant_id,
        order_id=order.id,
        from_status=from_status,
        to_status="Confirmed",
        updated_by=updated_by
    ))
    order.status = "Confirmed"
