"""
Pending allocations queue: surfaces open STOCK_SHORTAGE DemandGap rows so a
distributor can approve fulfilling them once stock arrives, instead of the
shortfall sitting silently forever.

Ordering is intentionally simple FIFO (oldest gap first) for this iteration —
a smarter customer-priority ranking is a separate, standalone workstream
(see app/services/customer_scoring_service.py) and is NOT wired in here to
avoid coupling two independently-shipped features together.

Known limitation (documented, not silently swallowed): approving an
allocation only adjusts inventory + the DemandGap + the order's fulfillment
status. It does NOT amend the original invoice/customer ledger entry for the
newly-allocated units — that already happened at original confirm-time using
the then-current allocated quantity. Correctly amending a live invoice/ledger
entry is a separate, higher-risk piece of work (partial invoice amendment)
intentionally left out of this change to avoid revenue-figure regressions.
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.demand_gap import DemandGap
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.customer import Customer

logger = logging.getLogger("uvicorn.error")


def list_pending_allocations(db: Session, tenant_id) -> list[dict]:
    """Open STOCK_SHORTAGE gaps for a tenant, oldest first."""
    gaps = (
        db.query(DemandGap)
        .filter(
            DemandGap.tenant_id == tenant_id,
            DemandGap.reason_code == "STOCK_SHORTAGE",
            DemandGap.status == "OPEN",
        )
        .order_by(DemandGap.created_at.asc())
        .all()
    )

    results = []
    for gap in gaps:
        product = db.get(Product, gap.product_id) if gap.product_id else None
        customer = db.get(Customer, gap.customer_id) if gap.customer_id else None
        order = db.get(Order, gap.order_id) if gap.order_id else None

        inv_record = None
        if gap.product_id:
            inv_record = (
                db.query(Inventory)
                .filter(Inventory.tenant_id == tenant_id, Inventory.sku_id == gap.product_id)
                .first()
            )
        available_now = max(0, inv_record.quantity_on_hand) if inv_record else 0

        results.append({
            "demand_gap_id": str(gap.id),
            "order_id": str(gap.order_id) if gap.order_id else None,
            "internal_order_id": order.internal_order_id if order else None,
            "customer_id": str(gap.customer_id),
            "customer_name": customer.retailer_name if customer else "Unknown",
            "product_id": str(gap.product_id) if gap.product_id else None,
            "sku_id": product.sku_id if product else None,
            "brand": product.brand if product else None,
            "requested_qty": gap.requested_qty,
            "allocated_qty": gap.allocated_qty,
            "gap_qty": gap.gap_qty,
            "available_now": available_now,
            "can_fulfil_now": available_now > 0,
            "revenue_at_risk": float(gap.revenue_at_risk),
            "created_at": gap.created_at.isoformat() if gap.created_at else None,
        })
    return results


def _recompute_order_status(db: Session, order: Order) -> str:
    """Re-derive Confirmed / Partially Confirmed / Awaiting Stock from current
    line-item allocation totals and write a ledger transition if it changed."""
    items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    total_requested = sum(item.quantity for item in items)
    total_allocated = sum(item.allocated_quantity or 0 for item in items)

    if total_requested > 0 and total_allocated == 0:
        new_status = "Awaiting Stock"
    elif total_allocated < total_requested:
        new_status = "Partially Confirmed"
    else:
        new_status = "Confirmed"

    if new_status != order.status:
        db.add(OrderStateLedger(
            tenant_id=order.tenant_id,
            order_id=order.id,
            from_status=order.status,
            to_status=new_status,
            updated_by="system_allocation_queue",
        ))
        order.status = new_status
    return new_status


def approve_pending_allocation(db: Session, tenant_id, demand_gap_id) -> dict:
    """
    Allocate as much of the open gap as current stock allows. Safe to call
    repeatedly / with insufficient stock — allocates whatever is available
    (possibly still leaving a smaller gap) and never raises for "not enough
    stock", only for a missing/already-resolved gap.
    """
    gap = db.query(DemandGap).filter(
        DemandGap.id == demand_gap_id,
        DemandGap.tenant_id == tenant_id,
    ).first()
    if not gap:
        raise ValueError("Demand gap not found")
    if gap.reason_code != "STOCK_SHORTAGE":
        raise ValueError("Only STOCK_SHORTAGE gaps can be approved from the allocation queue")
    if gap.status != "OPEN":
        raise ValueError(f"Demand gap is already {gap.status}, nothing to approve")
    if not gap.order_id or not gap.product_id:
        raise ValueError("Demand gap is missing order/product reference")

    line_item = db.query(OrderLineItem).filter(
        OrderLineItem.order_id == gap.order_id,
        OrderLineItem.product_id == gap.product_id,
    ).first()
    if not line_item:
        raise ValueError("Matching order line item not found")

    inv_record = db.query(Inventory).filter(
        Inventory.tenant_id == tenant_id,
        Inventory.sku_id == gap.product_id,
    ).first()
    available = max(0, inv_record.quantity_on_hand) if inv_record else 0
    remaining_gap = gap.gap_qty or 0
    newly_allocated = min(remaining_gap, available)

    if newly_allocated <= 0:
        return {
            "status": "no_stock_available",
            "message": "No additional stock available yet for this SKU.",
            "demand_gap_id": str(gap.id),
        }

    # Move units: on-hand -> committed, mirroring confirm_order's original allocation logic.
    inv_record.quantity_on_hand -= newly_allocated
    inv_record.quantity_committed = (inv_record.quantity_committed or 0) + newly_allocated

    line_item.allocated_quantity = (line_item.allocated_quantity or 0) + newly_allocated

    gap.allocated_qty = (gap.allocated_qty or 0) + newly_allocated
    gap.gap_qty = max(0, remaining_gap - newly_allocated)
    if gap.gap_qty <= 0:
        gap.status = "RECOVERED"
        gap.resolved_at = datetime.utcnow()

    order = db.get(Order, gap.order_id)
    new_order_status = _recompute_order_status(db, order) if order else None

    db.commit()

    logger.info(
        "Allocation queue: approved %s additional units for gap %s (order %s), new order status=%s",
        newly_allocated, gap.id, gap.order_id, new_order_status,
    )

    return {
        "status": "allocated",
        "demand_gap_id": str(gap.id),
        "newly_allocated_qty": newly_allocated,
        "remaining_gap_qty": gap.gap_qty,
        "gap_status": gap.status,
        "order_status": new_order_status,
    }
