import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, desc, select, and_, cast, Date
from sqlalchemy.orm import Session, aliased
from app.database import get_db, tenant_context
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.product import Product
from app.models.customer import Customer
from app.api.v1.dashboard import ensure_demo_data, resolve_tenant_id

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/sales-overview")
def get_sales_analytics(
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    resolved_tenant_id: uuid.UUID = Depends(resolve_tenant_id)
):
    ensure_demo_data(db, resolved_tenant_id)
    tenant_context.set(resolved_tenant_id)

    # 1. Total orders count
    total_orders = db.query(Order).filter(Order.tenant_id == resolved_tenant_id).count()

    # 2. Count of orders grouped by status
    ledger_alias = aliased(OrderStateLedger)
    latest_status_sub = (
        db.query(
            OrderStateLedger.order_id,
            OrderStateLedger.to_status.label("status")
        )
        .where(
            and_(
                OrderStateLedger.tenant_id == resolved_tenant_id,
                OrderStateLedger.timestamp == (
                    select(func.max(ledger_alias.timestamp))
                    .where(
                        and_(
                            ledger_alias.tenant_id == resolved_tenant_id,
                            ledger_alias.order_id == OrderStateLedger.order_id
                        )
                    )
                    .scalar_subquery()
                )
            )
        )
        .subquery()
    )

    status_counts_query = (
        db.query(
            latest_status_sub.c.status,
            func.count(Order.id)
        )
        .join(latest_status_sub, Order.id == latest_status_sub.c.order_id)
        .filter(Order.tenant_id == resolved_tenant_id)
        .group_by(latest_status_sub.c.status)
        .all()
    )

    status_counts = {"Draft": 0, "Confirmed": 0, "Dispatched": 0, "Pending": 0}
    for status_str, count in status_counts_query:
        status_key = "Pending" if status_str == "Draft" else status_str
        status_counts[status_key] = status_counts.get(status_key, 0) + count

    # If demo tenant, make sure we show realistic statuses
    if not status_counts_query and resolved_tenant_id == uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"):
        status_counts = {"Pending": 2, "Confirmed": 3, "Dispatched": 0}

    # 3. Top 5 moving SKUs sorted by total quantity
    top_moving = (
        db.query(
            Product.sku_id.label("sku_code"),
            Product.brand,
            Product.category,
            func.sum(OrderLineItem.quantity).label("total_quantity")
        )
        .join(Product, OrderLineItem.product_id == Product.id)
        .join(Order, OrderLineItem.order_id == Order.id)
        .filter(Order.tenant_id == resolved_tenant_id)
        .group_by(Product.sku_id, Product.brand, Product.category)
        .order_by(desc("total_quantity"))
        .limit(5)
        .all()
    )

    top_moving_skus = [
        {
            "sku_code": row.sku_code,
            "brand": row.brand,
            "category": row.category,
            "total_quantity": int(row.total_quantity or 0)
        }
        for row in top_moving
    ]

    return {
        "status": "success",
        "total_orders": total_orders,
        "status_distribution": status_counts,
        "top_moving_skus": top_moving_skus
    }

@router.get("/revenue-trend")
def get_revenue_analytics(
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    resolved_tenant_id: uuid.UUID = Depends(resolve_tenant_id)
):
    ensure_demo_data(db, resolved_tenant_id)
    tenant_context.set(resolved_tenant_id)

    # 1. Total gross revenue sum
    ledger_alias = aliased(OrderStateLedger)
    confirmed_orders_sub = (
        select(OrderStateLedger.order_id)
        .where(
            and_(
                OrderStateLedger.tenant_id == resolved_tenant_id,
                OrderStateLedger.to_status == "Confirmed",
                OrderStateLedger.timestamp == (
                    select(func.max(ledger_alias.timestamp))
                    .where(
                        and_(
                            ledger_alias.tenant_id == resolved_tenant_id,
                            ledger_alias.order_id == OrderStateLedger.order_id
                        )
                    )
                    .scalar_subquery()
                )
            )
        )
    )

    total_revenue_stmt = (
        select(func.sum(OrderLineItem.quantity * OrderLineItem.unit_price))
        .join(Order, OrderLineItem.order_id == Order.id)
        .where(and_(Order.tenant_id == resolved_tenant_id, Order.id.in_(confirmed_orders_sub)))
    )
    total_revenue = db.execute(total_revenue_stmt).scalar() or 0.0

    # 2. Total receivables balance
    total_receivables = db.query(func.sum(Customer.outstanding_balance)).filter(Customer.tenant_id == resolved_tenant_id).scalar() or 0.0

    # 3. Time-series dataset grouping sales totals by day
    time_series_query = (
        db.query(
            func.date(Order.created_at).label("date"),
            func.sum(OrderLineItem.quantity * OrderLineItem.unit_price).label("sales")
        )
        .join(OrderLineItem, OrderLineItem.order_id == Order.id)
        .filter(Order.tenant_id == resolved_tenant_id)
        .group_by(func.date(Order.created_at))
        .order_by("date")
        .all()
    )

    time_series = [
        {"date": str(row.date), "sales": float(row.sales or 0.0)}
        for row in time_series_query
    ]

    # Seed some sample data for demo tenant if it's too sparse to render a nice line chart
    if len(time_series) < 3 and resolved_tenant_id == uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"):
        time_series = [
            {"date": "2026-06-08", "sales": 15000},
            {"date": "2026-06-09", "sales": 24000},
            {"date": "2026-06-10", "sales": 18000},
            {"date": "2026-06-11", "sales": 32000},
            {"date": "2026-06-12", "sales": 29000},
            {"date": "2026-06-13", "sales": 45000},
            {"date": "2026-06-14", "sales": 38000}
        ]

    return {
        "status": "success",
        "total_revenue": float(total_revenue),
        "total_receivables": float(total_receivables),
        "time_series": time_series
    }
