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


def confirm_order(db: Session, order: Order, updated_by: str) -> Invoice:
    """
    Consolidated order confirmation logic.
    Steps:
    1. Fetch customer
    2. Allocate inventory (partial fill allowed)
    3. Compute billing total from allocated quantities
    4. Check credit limit against billing total
    5. Create invoice, ledger entry, state transition
    Returns the created Invoice.
    """

    # ── 1. Fetch customer ──────────────────────────────────────────────────────
    customer = db.get(Customer, order.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    from_status = order.current_status

    # ── 2. Fetch fresh line items ──────────────────────────────────────────────
    items = db.query(OrderLineItem).filter(
        OrderLineItem.order_id == order.id
    ).all()

    # Batch-fetch every product referenced by this order's line items in a single
    # query (previously N+1: one SELECT per item, run twice over the same items).
    _product_ids = {item.product_id for item in items}
    _products_by_id = {
        p.id: p for p in db.query(Product).filter(Product.id.in_(_product_ids)).all()
    } if _product_ids else {}

    # Reject if any line item is still unmatched (must go through triage first)
    _unmatched_skus = {"UNMATCHED_SKU", "UNMATCHED_TRIAGE_SKU"}
    for item in items:
        prod_check = _products_by_id.get(item.product_id)
        if prod_check and prod_check.sku_id in _unmatched_skus:
            raise HTTPException(
                status_code=400,
                detail="Cannot confirm order with unmatched SKUs. Resolve all items in triage first."
            )

    # Resolve product metadata (uses the batch-fetched map above, no extra queries)
    for item in items:
        prod = _products_by_id.get(item.product_id)
        if prod:
            item.sku_code = prod.sku_id
            item.product_name = prod.sku_id
        else:
            item.sku_code = "UNKNOWN_SKU"
            item.product_name = "Unknown Product"

    # ── 3. Inventory allocation (single pass, partial fill) ────────────────────
    # Batch-fetch all inventory rows for this order's SKUs in one query instead of
    # one SELECT per line item.
    _sku_ids = {item.product_id for item in items}
    _inventory_by_sku = {
        inv.sku_id: inv
        for inv in db.query(Inventory).filter(
            Inventory.tenant_id == order.tenant_id,
            Inventory.sku_id.in_(_sku_ids)
        ).all()
    } if _sku_ids else {}

    for item in items:
        inv_record = _inventory_by_sku.get(item.product_id)

        available = max(0, inv_record.quantity_on_hand) if inv_record else 0
        allocated = min(item.quantity, available)
        item.allocated_quantity = allocated
        gap_qty = item.quantity - allocated

        # Create DemandGap for shortfall if not already exists
        if gap_qty > 0:
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

        # Deduct inventory for allocated units
        if inv_record and allocated > 0:
            inv_record.quantity_on_hand -= allocated
            inv_record.quantity_committed = (inv_record.quantity_committed or 0) + allocated

    db.flush()

    # ── 4. Billing total from allocated quantities ─────────────────────────────
    billing_total = sum(
        float(
            (item.allocated_quantity if item.allocated_quantity is not None else item.quantity)
            * item.unit_price
        )
        for item in items
    )

    # ── 5. Credit limit check against billing total ────────────────────────────
    # Single aggregate query instead of loading every other Confirmed order + its
    # line_items in Python (each of which lazy-loaded the line_items relationship
    # per order — an O(orders) fan-out). `current_status` is a plain property over
    # `Order.status` (see Order.current_status), so we filter on that column
    # directly rather than re-deriving it.
    from sqlalchemy import select as sa_select, func, and_, or_, case

    # Matches the original Python `li.allocated_quantity or li.quantity` semantics:
    # falls back to `quantity` when allocated_quantity is NULL *or* 0.
    _effective_qty = case(
        (or_(OrderLineItem.allocated_quantity.is_(None), OrderLineItem.allocated_quantity == 0), OrderLineItem.quantity),
        else_=OrderLineItem.allocated_quantity
    )
    confirmed_outstanding = float(db.execute(
        sa_select(func.sum(_effective_qty * OrderLineItem.unit_price))
        .join(Order, OrderLineItem.order_id == Order.id)
        .where(
            and_(
                Order.customer_id == order.customer_id,
                Order.tenant_id == order.tenant_id,
                Order.id != order.id,
                Order.status == "Confirmed"
            )
        )
    ).scalar() or 0.0)

    combined = confirmed_outstanding + billing_total
    if combined > float(customer.credit_limit):
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
            revenue_at_risk=billing_total,
            created_at=datetime.utcnow(),
        ))
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Credit limit exceeded. Combined balance: ₹{combined:,.2f}, Limit: ₹{float(customer.credit_limit):,.2f}"
        )

    # ── 6. Record DEBIT transaction via ledger service ─────────────────────────
    # This atomically writes the ledger entry AND recomputes outstanding_balance
    # from the full ledger — preventing balance/ledger sync drift.
    from app.services.ledger_service import record_transaction
    record_transaction(
        db=db,
        tenant_id=order.tenant_id,
        customer_id=order.customer_id,
        type="DEBIT",
        amount=billing_total,
        reference_id=order.internal_order_id,
        description=f"Order {order.internal_order_id} confirmed"
    )

    # ── 8. Create Invoice ──────────────────────────────────────────────────────
    invoice = Invoice(
        tenant_id=order.tenant_id,
        order_id=order.id,
        gstin=customer.gstin if customer.gstin else "PENDING",
        total_amount=billing_total,
        # No real IRP (Invoice Registration Portal) integration exists yet —
        # these must NOT claim a government e-invoice was actually cleared/generated.
        irn_status="NOT_APPLICABLE",
        qr_code_status="NOT_APPLICABLE",
        customer_id=order.customer_id,
        payment_status="UNPAID",
        amount_paid=0.0,
        created_at=datetime.utcnow()
    )
    db.add(invoice)
    db.flush()

    # ── 9. Reconcile any existing customer credits against new invoice ──────────


    # ── 10. Self-learning for product alias updates ────────────────────────────
    from app.api.v1.orders import process_order_self_learning
    process_order_self_learning(db, order.id, order.tenant_id)

    # ── 11. State transition ───────────────────────────────────────────────────
    db.add(OrderStateLedger(
        tenant_id=order.tenant_id,
        order_id=order.id,
        from_status=from_status,
        to_status="Confirmed",
        updated_by=updated_by
    ))
    order.status = "Confirmed"

    return invoice
