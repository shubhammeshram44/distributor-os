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
from app.models.product import Product
from app.services.order_confirmation_service import confirm_order

router = APIRouter(prefix="/orders", tags=["Orders"])


class FulfillmentLineDecision(BaseModel):
    item_id: uuid.UUID
    approved_quantity: int = Field(ge=0)


class FulfillmentResolvedItem(BaseModel):
    item_id: uuid.UUID
    product_id: uuid.UUID


class FulfillmentPreviewPayload(BaseModel):
    resolved_items: list[FulfillmentResolvedItem] = []


class FulfillmentDecisionPayload(BaseModel):
    action: Literal["CONFIRM_AVAILABLE", "CONFIRM_CUSTOM", "CANCEL_FULL"]
    line_decisions: list[FulfillmentLineDecision] = []
    resolved_items: list[FulfillmentResolvedItem] = []
    invoice_type: str | None = None


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


def _resolve_preview_product_ids(
    order: Order,
    items: list[OrderLineItem],
    resolved_items: list[FulfillmentResolvedItem],
) -> dict[uuid.UUID, uuid.UUID | None]:
    """Return the product id each line would use after staged frontend resolution."""
    line_ids = {item.id for item in items}
    resolved_map: dict[uuid.UUID, uuid.UUID] = {}
    for change in resolved_items:
        if change.item_id not in line_ids:
            raise HTTPException(status_code=422, detail=f"Line item {change.item_id} does not belong to this order")
        resolved_map[change.item_id] = change.product_id
    return {item.id: resolved_map.get(item.id, item.product_id) for item in items}


def _apply_resolved_items(
    db: Session,
    order: Order,
    items: list[OrderLineItem],
    resolved_items: list[FulfillmentResolvedItem],
) -> None:
    """Apply the same staged SKU mapping accepted by batch-confirm before allocation."""
    if not resolved_items:
        return
    items_by_id = {item.id: item for item in items}
    for change in resolved_items:
        item = items_by_id.get(change.item_id)
        if not item:
            raise HTTPException(status_code=422, detail=f"Line item {change.item_id} does not belong to this order")
        product = db.get(Product, change.product_id)
        if not product or product.tenant_id != order.tenant_id:
            raise HTTPException(status_code=404, detail=f"Product {change.product_id} not found")
        item.product_id = product.id
        item.unit_price = product.base_price
    db.flush()


def _build_preview(
    db: Session,
    order: Order,
    resolved_items: list[FulfillmentResolvedItem],
):
    items = db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    effective_product_ids = _resolve_preview_product_ids(order, items, resolved_items)
    product_ids = {pid for pid in effective_product_ids.values() if pid is not None}
    inventory = {
        row.sku_id: row
        for row in db.query(Inventory).filter(
            Inventory.tenant_id == order.tenant_id,
            Inventory.sku_id.in_(product_ids),
        ).all()
    } if product_ids else {}

    lines = []
    for item in items:
        product_id = effective_product_ids[item.id]
        inv = inventory.get(product_id)
        available = max(0, inv.quantity_on_hand or 0) if inv else 0
        suggested = min(item.quantity, available)
        lines.append({
            "item_id": str(item.id),
            "product_id": str(product_id) if product_id else None,
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


@router.get("/{order_id}/fulfillment-preview", status_code=status.HTTP_200_OK)
def preview_fulfillment(order_id: uuid.UUID, db: Session = Depends(get_db)):
    """Backward-compatible preview for callers without staged SKU resolutions."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    tenant_context.set(order.tenant_id)
    return _build_preview(db, order, [])


@router.post("/{order_id}/fulfillment-preview", status_code=status.HTTP_200_OK)
def preview_fulfillment_with_resolutions(
    order_id: uuid.UUID,
    payload: FulfillmentPreviewPayload,
    db: Session = Depends(get_db),
):
    """Preview stock using staged SKU resolutions without mutating the order."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    tenant_context.set(order.tenant_id)
    return _build_preview(db, order, payload.resolved_items)


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
    if current_status not in ("Draft", "Pending", "Needs Review", "pending_review", "NEEDS_REVIEW"):
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

        _apply_resolved_items(db, order, items, payload.resolved_items)
        if payload.invoice_type:
            order.invoice_type = payload.invoice_type

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
