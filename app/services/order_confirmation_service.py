import uuid
import logging
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.inventory import Inventory
from app.models.demand_gap import DemandGap
from app.models.product import Product

logger = logging.getLogger("uvicorn.error")


def check_credit_limit(db: Session, customer: Customer, order_total: float, exclude_order_id: uuid.UUID | None = None) -> float:
    """Computes the combined outstanding balance for a customer."""
    from sqlalchemy import select as sa_select, func, and_, or_, case
    from app.models.order import Order, OrderLineItem

    _effective_qty = case(
        (or_(OrderLineItem.allocated_quantity.is_(None), OrderLineItem.allocated_quantity == 0), OrderLineItem.quantity),
        else_=OrderLineItem.allocated_quantity
    )
    query = (
        sa_select(func.sum(_effective_qty * OrderLineItem.unit_price))
        .join(Order, OrderLineItem.order_id == Order.id)
        .where(and_(
            Order.customer_id == customer.id,
            Order.tenant_id == customer.tenant_id,
            Order.status.in_(["Confirmed", "Partially Confirmed", "Awaiting Stock"])
        ))
    )
    if exclude_order_id:
        query = query.where(Order.id != exclude_order_id)
    confirmed_outstanding = float(db.execute(query).scalar() or 0.0)
    return confirmed_outstanding + order_total


def _upsert_demand_gap(
    db: Session,
    order: Order,
    item: OrderLineItem,
    allocated: int,
    gap_qty: int,
    reason_code: str,
) -> None:
    """Record unmet original demand without duplicating a gap on retries."""
    if gap_qty <= 0:
        return
    existing = db.query(DemandGap).filter(
        DemandGap.order_id == order.id,
        DemandGap.product_id == item.product_id,
        DemandGap.reason_code == reason_code,
    ).first()
    if existing:
        existing.requested_qty = item.quantity
        existing.allocated_qty = allocated
        existing.gap_qty = gap_qty
        existing.revenue_at_risk = float(gap_qty * item.unit_price)
        return
    db.add(DemandGap(
        id=uuid.uuid4(), tenant_id=order.tenant_id, order_id=order.id,
        customer_id=order.customer_id, product_id=item.product_id,
        reason_code=reason_code, status="OPEN", resolved_at=None,
        requested_qty=item.quantity, allocated_qty=allocated, gap_qty=gap_qty,
        unit_price=float(item.unit_price),
        revenue_at_risk=float(gap_qty * item.unit_price),
        created_at=datetime.utcnow(),
    ))


def confirm_order(
    db: Session,
    order: Order,
    updated_by: str,
    bypass_credit_limit: bool = False,
    approved_quantities: dict[uuid.UUID, int] | None = None,
) -> Invoice | None:
    """
    Confirm an order while preserving original customer demand.

    `OrderLineItem.quantity` always remains the originally requested quantity.
    `approved_quantities`, when supplied, is the maximum quantity the customer
    agreed to accept for each line. Inventory allocation is capped by both that
    approval and current stock.

    Examples for requested=145, stock=142:
      - no override -> allocate 142; STOCK_SHORTAGE gap 3
      - approved=140 -> allocate 140; CUSTOMER_REDUCTION gap 5; leave stock 2

    Full cancellation is handled by the order API before this function is called,
    because cancellation must not reserve inventory or create an invoice.
    """
    customer = db.get(Customer, order.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    from_status = order.current_status
    items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    approved_quantities = approved_quantities or {}

    _product_ids = {item.product_id for item in items}
    _products_by_id = {
        p.id: p for p in db.query(Product).filter(Product.id.in_(_product_ids)).all()
    } if _product_ids else {}

    _unmatched_skus = {"UNMATCHED_SKU", "UNMATCHED_TRIAGE_SKU"}
    for item in items:
        prod_check = _products_by_id.get(item.product_id)
        if prod_check and prod_check.sku_id in _unmatched_skus:
            raise HTTPException(status_code=400, detail="Cannot confirm order with unmatched SKUs. Resolve all items in triage first.")

    for item in items:
        prod = _products_by_id.get(item.product_id)
        if prod:
            item.sku_code = prod.sku_id
            item.product_name = prod.sku_id
        else:
            item.sku_code = "UNKNOWN_SKU"
            item.product_name = "Unknown Product"

    _sku_ids = {item.product_id for item in items}
    _inventory_by_sku = {
        inv.sku_id: inv for inv in db.query(Inventory).filter(
            Inventory.tenant_id == order.tenant_id,
            Inventory.sku_id.in_(_sku_ids)
        ).all()
    } if _sku_ids else {}

    for item in items:
        inv_record = _inventory_by_sku.get(item.product_id)
        available = max(0, inv_record.quantity_on_hand) if inv_record else 0

        approved = approved_quantities.get(item.id, item.quantity)
        if approved < 0 or approved > item.quantity:
            raise HTTPException(
                status_code=422,
                detail=f"Approved quantity for line {item.id} must be between 0 and requested quantity {item.quantity}."
            )

        allocated = min(approved, available)
        item.allocated_quantity = allocated

        # Demand Gap is always measured against ORIGINAL customer demand.
        # If the customer deliberately accepts less than requested, distinguish
        # that negotiated reduction from stock still waiting to be allocated.
        total_gap = item.quantity - allocated
        reason_code = "CUSTOMER_REDUCTION" if approved < item.quantity else "STOCK_SHORTAGE"
        _upsert_demand_gap(db, order, item, allocated, total_gap, reason_code)

        if inv_record and allocated > 0:
            inv_record.quantity_on_hand -= allocated
            inv_record.quantity_committed = (inv_record.quantity_committed or 0) + allocated

    db.flush()

    billing_total = sum(float((item.allocated_quantity if item.allocated_quantity is not None else item.quantity) * item.unit_price) for item in items)

    if not bypass_credit_limit:
        combined = check_credit_limit(db, customer, billing_total, exclude_order_id=order.id)
        if combined > float(customer.credit_limit):
            db.add(DemandGap(
                id=uuid.uuid4(), tenant_id=order.tenant_id, order_id=order.id,
                customer_id=order.customer_id, product_id=None,
                reason_code="CREDIT_LIMIT", status="OPEN", resolved_at=None,
                requested_qty=None, allocated_qty=None, gap_qty=None, unit_price=None,
                revenue_at_risk=billing_total, created_at=datetime.utcnow(),
            ))
            db.commit()
            raise HTTPException(status_code=400, detail=f"Credit limit exceeded. Combined balance: ₹{combined:,.2f}, Limit: ₹{float(customer.credit_limit):,.2f}")

    from app.services.ledger_service import record_transaction
    if billing_total > 0:
        record_transaction(
            db=db, tenant_id=order.tenant_id, customer_id=order.customer_id,
            type="DEBIT", amount=billing_total, reference_id=order.internal_order_id,
            description=f"Order {order.internal_order_id} confirmed"
        )

    invoice = None
    if billing_total > 0:
        from app.services.invoice_gst_utils import compute_cgst_sgst, generate_invoice_number
        cgst_amount, sgst_amount = compute_cgst_sgst(items, _products_by_id)
        invoice_created_at = datetime.utcnow()
        invoice = Invoice(
            tenant_id=order.tenant_id, order_id=order.id,
            gstin=customer.gstin if customer.gstin else "PENDING",
            total_amount=billing_total, irn_status="NOT_APPLICABLE",
            qr_code_status="NOT_APPLICABLE", customer_id=order.customer_id,
            payment_status="UNPAID", amount_paid=0.0, created_at=invoice_created_at,
            cgst_amount=cgst_amount, sgst_amount=sgst_amount,
            invoice_number=generate_invoice_number(db, order.tenant_id, invoice_created_at),
        )
        db.add(invoice)
        db.flush()

    from app.api.v1.orders import process_order_self_learning
    process_order_self_learning(db, order.id, order.tenant_id)

    total_requested = sum(item.quantity for item in items)
    total_allocated = sum(item.allocated_quantity or 0 for item in items)
    if total_requested > 0 and total_allocated == 0:
        final_status = "Awaiting Stock"
    elif total_allocated < total_requested:
        final_status = "Partially Confirmed"
    else:
        final_status = "Confirmed"

    db.add(OrderStateLedger(
        tenant_id=order.tenant_id, order_id=order.id,
        from_status=from_status, to_status=final_status, updated_by=updated_by
    ))
    order.status = final_status
    return invoice
