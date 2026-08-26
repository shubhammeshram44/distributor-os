import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db, tenant_context
from app.models.demand_gap import DemandGap
from app.models.inventory import Inventory
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.services.order_confirmation_service import confirm_order

router = APIRouter(prefix="/orders", tags=["Orders"])


class FulfillmentLineDecision(BaseModel):
    item_id: uuid.UUID
    approved_quantity: int = Field(ge=0)


class FulfillmentDecisionPayload(BaseModel):
    action: Literal["CONFIRM_AVAILABLE", "CONFIRM_CUSTOM", "CANCEL_FULL"]
    line_decisions: list[FulfillmentLineDecision] = []


def _record_full_cancellation_gap(db: Session, order: Order, item: OrderLineItem) -> None:
    """Capture the entire original demand as lost without creating a backorder."""
    existing = db.query(DemandGap).filter(
        DemandGap.order_id == order.id,
        DemandGap.product_id == item.product_id,
        DemandGap.reason_code == "CUSTOMER_CANCELLED_SHORTAGE",
    ).first()
    now = datetime.utcnow()
    values = {
        "requested_qty": item.quantity,
        "allocated_qty": 0,
        "gap_qty": item.quantity,
        "unit_price": float(item.unit_price),
        "revenue_at_risk": float(item.quantity * item.unit_price),
        "status": "LOST",
        "resolved_at": now,
    }
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        return

    db.add(DemandGap(
        id=uuid.uuid4(),
        tenant_id=order.tenant_id,
        order_id=order.id,
        customer_id=order.customer_id,
        product_id=item.product_id,
        reason_code="CUSTOMER_CANCELLED_SHORTAGE",
        created_at=now,
        **values,
    ))


@router.get("/{order_id}/fulfillment-preview", status_code=status.HTTP_200_OK)
def preview_fulfillment(order_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return real-time requested vs available quantities before confirmation."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    tenant_context.set(order.tenant_id)

    items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    inventory = {
        row.sku_id: row
        for row in db.query(Inventory).filter(
            Inventory.tenant_id == order.tenant_id,
            Inventory.sku_id.in_({item.product_id for item in items}),
        ).all()
    } if items else {}

    lines = []
    for item in items:
        inv = inventory.get(item.product_id)
        available = max(0, inv.quantity_on_hand or 0) if inv else 0
        suggested = min(item.quantity, available)
        lines.append({
            "item_id": str(item.id),
            "product_id": str(item.product_id) if item.product_id else None,
            "requested_quantity": item.quantity,
            "available_quantity": available,
            "suggested_quantity": suggested,
            "has_shortage": available < item.quantity,
        })

    return {
        "order_id": str(order.id),
        "has_shortage": any(line["has_shortage"] for line in lines),
        "requested_quantity": sum(line["requested_quantity"] for line in lines),
        "available_quantity": sum(line["available_quantity"] for line in lines),
        "suggested_quantity": sum(line["suggested_quantity"] for line in lines),
        "lines": lines,
    }


@router.post("/{order_id}/fulfillment-decision", status_code=status.HTTP_200_OK)
def decide_fulfillment(
    order_id: uuid.UUID,
    payload: FulfillmentDecisionPayload,
    db: Session = Depends(get_db),
):
    """
    Resolve a stock-short order while preserving original customer demand.

    CONFIRM_AVAILABLE: allocate min(requested, available) for each line.
    CONFIRM_CUSTOM: allocate up to the customer-approved quantity for each line.
    CANCEL_FULL: cancel the entire order, deduct no stock, and record full lost demand.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    tenant_context.set(order.tenant_id)
    current_status = order.current_status
    if current_status not in ("Draft", "Pending"):
        raise HTTPException(
            status_code=409,
            detail=f"Fulfillment decision is only allowed for a pending order. Current status: {current_status}",
        )

    items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    if not items:
        raise HTTPException(status_code=400, detail="Order has no line items")

    try:
        if payload.action == "CANCEL_FULL":
            for item in items:
                _record_full_cancellation_gap(db, order, item)
                item.allocated_quantity = 0

            db.add(OrderStateLedger(
                tenant_id=order.tenant_id,
                order_id=order.id,
                from_status=current_status,
                to_status="Cancelled",
                updated_by="operator_fulfillment_decision",
            ))
            order.status = "Cancelled"
            db.commit()
            return {
                "status": "success",
                "order_id": str(order.id),
                "new_status": "Cancelled",
                "requested_quantity": sum(i.quantity for i in items),
                "confirmed_quantity": 0,
                "demand_gap_quantity": sum(i.quantity for i in items),
            }

        approved_quantities = None
        if payload.action == "CONFIRM_CUSTOM":
            if not payload.line_decisions:
                raise HTTPException(status_code=422, detail="line_decisions are required for CONFIRM_CUSTOM")

            order_item_ids = {item.id for item in items}
            approved_quantities = {}
            for decision in payload.line_decisions:
                if decision.item_id not in order_item_ids:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Line item {decision.item_id} does not belong to this order",
                    )
                approved_quantities[decision.item_id] = decision.approved_quantity

        confirm_order(
            db,
            order,
            updated_by="operator_fulfillment_decision",
            approved_quantities=approved_quantities,
        )
        db.commit()

        db.refresh(order)
        refreshed_items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
        requested = sum(i.quantity for i in refreshed_items)
        confirmed = sum(i.allocated_quantity or 0 for i in refreshed_items)
        return {
            "status": "success",
            "order_id": str(order.id),
            "new_status": order.current_status,
            "requested_quantity": requested,
            "confirmed_quantity": confirmed,
            "demand_gap_quantity": requested - confirmed,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Fulfillment decision failed: {str(exc)}")
