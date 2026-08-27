from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, Header
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, aliased

from app.database import get_db, tenant_context
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.api.v1.dashboard import get_dashboard_metrics, get_dashboard_overview
from app.services.tenant_service import resolve_tenant_id

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

SALE_STATUSES = (
    "Confirmed",
    "Partially Confirmed",
    "Dispatched",
    "Delivered",
    "Awaiting Stock",
)


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00").replace("+00:00", ""))
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return None


def _latest_sale_order_ids():
    ledger_alias = aliased(OrderStateLedger)
    return (
        select(OrderStateLedger.order_id)
        .where(
            and_(
                OrderStateLedger.to_status.in_(SALE_STATUSES),
                OrderStateLedger.timestamp
                == (
                    select(func.max(ledger_alias.timestamp))
                    .where(ledger_alias.order_id == OrderStateLedger.order_id)
                    .scalar_subquery()
                ),
            )
        )
    )


def _allocated_sales(db: Session, tenant_id, start_dt=None, end_dt=None) -> float:
    """Confirmed sales value is based on allocated units, never original requested demand."""
    allocated_qty = func.coalesce(OrderLineItem.allocated_quantity, 0)
    stmt = (
        select(func.sum(allocated_qty * OrderLineItem.unit_price))
        .join(Order, OrderLineItem.order_id == Order.id)
        .where(Order.id.in_(_latest_sale_order_ids()))
        .where(Order.tenant_id == tenant_id)
    )
    if start_dt:
        stmt = stmt.where(Order.created_at >= start_dt)
    if end_dt:
        stmt = stmt.where(Order.created_at <= end_dt)
    return float(db.execute(stmt).scalar() or 0.0)


def _apply_allocated_recent_order_amounts(payload: dict):
    for order in payload.get("recent_orders", []):
        if order.get("status") not in SALE_STATUSES:
            continue
        order["amount"] = float(
            sum(
                (line.get("allocated_quantity") or 0) * float(line.get("unit_price") or 0)
                for line in order.get("line_items", [])
            )
        )


@router.get("/metrics")
def get_fulfillment_aware_dashboard_metrics(
    tenant_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Compatibility wrapper correcting sales metrics to actual allocated quantities."""
    result = get_dashboard_metrics(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        access_token=access_token,
        authorization=authorization,
        db=db,
    )
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    tenant_context.set(resolved_tenant_id)
    total_sales = _allocated_sales(db, resolved_tenant_id, _parse_dt(start_date), _parse_dt(end_date))
    result["total_sales"] = total_sales
    order_count = int(result.get("orders_count") or 0)
    result["average_order_value"] = total_sales / order_count if order_count else 0.0
    return result


@router.get("/overview")
def get_fulfillment_aware_dashboard_overview(
    tenant_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Compatibility wrapper correcting overview sales and recent confirmed-order amounts."""
    result = get_dashboard_overview(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        access_token=access_token,
        authorization=authorization,
        db=db,
    )
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    tenant_context.set(resolved_tenant_id)
    total_sales = _allocated_sales(db, resolved_tenant_id, _parse_dt(start_date), _parse_dt(end_date))
    metrics = result.get("metrics", {})
    metrics["total_sales"] = total_sales
    order_count = int(metrics.get("orders_count") or 0)
    metrics["average_order_value"] = total_sales / order_count if order_count else 0.0
    _apply_allocated_recent_order_amounts(result)
    return result
