import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Header
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session, aliased, defer, joinedload
from sqlalchemy.exc import ProgrammingError
import logging

logger = logging.getLogger("uvicorn.error")
from app.database import get_db, tenant_context
from app.models.tenant import DistributorTenant
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product, ProductAlias, ProductSupplierMapping
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentInvoiceLink
from app.models.inventory import Inventory
from app.models.ingestion import IngestionJob, IngestionStaging
from app.models.user import User
from app.models.ledger import CustomerLedger
from app.utils.security import hash_password, verify_jwt
from app.models.demand_gap import DemandGap
from app.utils.payment_terms import parse_credit_days

from pydantic import BaseModel

class DashboardLineItemResponse(BaseModel):
    id: str
    sku_id: str
    brand: str
    category: str
    pack_size: str
    quantity: int
    allocated_quantity: int | None = None
    unit_price: float
    total_price: float


class RecentOrderResponse(BaseModel):
    id: str
    order_id: str
    customer: str
    channel: str
    amount: float
    status: str
    created_on: str
    eta: str
    invoice_type: str
    raw_source_text: str | None = None
    line_items: list[DashboardLineItemResponse] = []

class DashboardOverviewResponse(BaseModel):
    metrics: dict
    recent_orders: list[RecentOrderResponse]
    donut_data: list[dict]

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

from app.services.tenant_service import resolve_tenant_id, DEMO_TENANT_ID, get_validated_tenant_id
from app.services.demo_service import ensure_demo_data




@router.get("/metrics")
def get_dashboard_metrics(
    tenant_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns high-level metric values. Tries to read from live tables;
    if database is empty, automatically triggers seeder first.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    if str(tenant_id) == "d3b07384-d113-4956-a5d2-64be7357c11d":
        ensure_demo_data(db, tenant_id)
    tenant_context.set(tenant_id)

    # Parse date filters if provided
    start_dt = None
    end_dt = None
    if start_date:
        try:
            if "T" in start_date:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00").replace("+00:00", ""))
            else:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except Exception:
            pass
    if end_date:
        try:
            if "T" in end_date:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00").replace("+00:00", ""))
            else:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except Exception:
            pass

    has_date_filter = start_dt is not None or end_dt is not None

    # Calculate actual values under this tenant
    # 1. Total Sales (sum of LineItems in non-Draft orders)
    ledger_alias = aliased(OrderStateLedger)
    valid_orders_sub = (
        select(OrderStateLedger.order_id)
        .where(
            and_(
                OrderStateLedger.to_status != "Draft",
                OrderStateLedger.timestamp == (
                    select(func.max(ledger_alias.timestamp))
                    .where(ledger_alias.order_id == OrderStateLedger.order_id)
                    .scalar_subquery()
                )
            )
        )
    )

    total_sales_stmt = (
        select(func.sum(OrderLineItem.quantity * OrderLineItem.unit_price))
        .join(Order, OrderLineItem.order_id == Order.id)
        .where(Order.id.in_(valid_orders_sub))
        .where(Order.tenant_id == tenant_id)  # CRITICAL: tenant isolation
    )
    if start_dt:
        total_sales_stmt = total_sales_stmt.where(Order.created_at >= start_dt)
    if end_dt:
        total_sales_stmt = total_sales_stmt.where(Order.created_at <= end_dt)
    total_sales = db.execute(total_sales_stmt).scalar() or 0.0

    # 2. Orders Count
    orders_count_stmt = select(func.count(Order.id)).where(Order.tenant_id == tenant_id)
    if start_dt:
        orders_count_stmt = orders_count_stmt.where(Order.created_at >= start_dt)
    if end_dt:
        orders_count_stmt = orders_count_stmt.where(Order.created_at <= end_dt)
    orders_count = db.execute(orders_count_stmt).scalar() or 0

    # 3. Average Order Value
    aov = total_sales / orders_count if orders_count > 0 else 0.0

    # Calculate comparison trend changes if date filters are present
    total_sales_change = 0.0
    orders_count_change = 0.0
    average_order_value_change = 0.0

    if start_dt and end_dt:
        delta = end_dt - start_dt
        hist_start_dt = start_dt - delta
        hist_end_dt = start_dt

        hist_total_sales_stmt = (
            select(func.sum(OrderLineItem.quantity * OrderLineItem.unit_price))
            .join(Order, OrderLineItem.order_id == Order.id)
            .where(Order.id.in_(valid_orders_sub))
            .where(Order.tenant_id == tenant_id)  # CRITICAL: tenant isolation
            .where(Order.created_at >= hist_start_dt)
            .where(Order.created_at <= hist_end_dt)
        )
        hist_total_sales = db.execute(hist_total_sales_stmt).scalar() or 0.0

        hist_orders_count_stmt = (
            select(func.count(Order.id))
            .where(Order.tenant_id == tenant_id)
            .where(Order.created_at >= hist_start_dt)
            .where(Order.created_at <= hist_end_dt)
        )
        hist_orders_count = db.execute(hist_orders_count_stmt).scalar() or 0

        hist_aov = hist_total_sales / hist_orders_count if hist_orders_count > 0 else 0.0

        if hist_total_sales > 0:
            total_sales_change = float((total_sales - hist_total_sales) / hist_total_sales * 100)
        if hist_orders_count > 0:
            orders_count_change = float((orders_count - hist_orders_count) / hist_orders_count * 100)
        if hist_aov > 0:
            average_order_value_change = float((aov - hist_aov) / hist_aov * 100)

    # 4. Outstanding Collections — sum of (total - paid) for all non-fully-paid invoices
    from app.models.invoice import Invoice as _Invoice
    outstanding_stmt = (
        select(func.sum(_Invoice.total_amount - _Invoice.amount_paid))
        .where(
            and_(_Invoice.tenant_id == tenant_id, _Invoice.payment_status != "PAID")
        )
    )
    outstanding = db.execute(outstanding_stmt).scalar() or 0.0

    # 5. Inventory counts (Low Stock, Out of Stock, Total SKUs, Inventory Value)
    total_skus_count = db.query(Inventory).filter(Inventory.tenant_id == tenant_id).count()

    low_stock_count = db.query(Inventory).filter(
        and_(
            Inventory.tenant_id == tenant_id,
            Inventory.quantity_on_hand < Inventory.low_stock_threshold,
            Inventory.quantity_on_hand > 0
        )
    ).count()

    out_of_stock_count = db.query(Inventory).filter(
        and_(
            Inventory.tenant_id == tenant_id,
            Inventory.quantity_on_hand == 0
        )
    ).count()

    inventory_val_sum = db.query(func.sum(Inventory.quantity_on_hand * Product.base_price))\
        .join(Product, Inventory.sku_id == Product.id)\
        .filter(Inventory.tenant_id == tenant_id).scalar() or 0.0

    if inventory_val_sum >= 10000000:
        inventory_value_str = f"₹ {(inventory_val_sum / 10000000):.2f} Cr"
    elif inventory_val_sum >= 100000:
        inventory_value_str = f"₹ {(inventory_val_sum / 100000):.2f}L"
    else:
        inventory_value_str = f"₹ {inventory_val_sum:,.2f}"

    # 6. High-Risk Overdue Accounts (60+ days)
    now = datetime.utcnow()
    cutoff_date = now - timedelta(days=60)
    
    credit_sub = (
        select(func.coalesce(func.sum(CustomerLedger.amount), 0.0))
        .where(
            and_(
                CustomerLedger.tenant_id == tenant_id,
                CustomerLedger.customer_id == Customer.id,
                CustomerLedger.type == "CREDIT"
            )
        )
        .scalar_subquery()
    )

    debit_sub = (
        select(func.coalesce(func.sum(CustomerLedger.amount), 0.0))
        .where(
            and_(
                CustomerLedger.tenant_id == tenant_id,
                CustomerLedger.customer_id == Customer.id,
                CustomerLedger.type == "DEBIT",
                CustomerLedger.created_at < cutoff_date
            )
        )
        .scalar_subquery()
    )

    overdue_stmt = (
        select(func.count(Customer.id))
        .where(Customer.tenant_id == tenant_id)
        .where(debit_sub > credit_sub)
    )
    overdue_60_count = db.execute(overdue_stmt).scalar() or 0

    return {
        "total_sales": float(total_sales),
        "total_sales_change": float(total_sales_change),
        "orders_count": int(orders_count),
        "orders_count_change": float(orders_count_change),
        "average_order_value": float(aov),
        "average_order_value_change": float(average_order_value_change),
        "outstanding_collections": float(outstanding),
        "outstanding_collections_change": 0.0,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "total_skus_count": total_skus_count,
        "inventory_value": inventory_value_str,
        "overdue_60_count": overdue_60_count,
        "total_skus": total_skus_count,
        "total_inventory_value": float(inventory_val_sum)
    }


@router.get("/recent-orders", response_model=list[RecentOrderResponse])
def get_recent_orders(
    tenant_id: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns the latest 5 orders with their status resolved from the ledger.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    if str(tenant_id) == "d3b07384-d113-4956-a5d2-64be7357c11d":
        ensure_demo_data(db, tenant_id)
    tenant_context.set(tenant_id)

    orders = (
        db.query(Order)
        .options(
            joinedload(Order.customer),
            joinedload(Order.line_items).joinedload(OrderLineItem.product)
        )
        .filter(Order.tenant_id == tenant_id)
        .order_by(Order.created_at.desc())
        .limit(5)
        .all()
    )
    results = []
    
    for o in orders:
        cust_name = o.customer.retailer_name if o.customer else "Unknown Retailer"

        # Calculate total amount
        amount = sum(float(item.quantity * item.unit_price) for item in o.line_items)

        # Status badge conversion: Draft = "Pending", Confirmed = "Confirmed"
        status_raw = o.current_status
        has_triage_sku = any(
            item.product_id is None or (item.product is not None and item.product.sku_id in ("UNMATCHED_SKU", "UNMATCHED_TRIAGE_SKU"))
            for item in o.line_items
        )
        if has_triage_sku or status_raw == "pending_review":
            status_raw = "pending_review"
        status_resolved = "Pending" if status_raw == "Draft" else ("Needs Review" if status_raw in ["NEEDS_REVIEW", "pending_review"] else status_raw)

        line_items_data = []
        for item in o.line_items:
            sku = item.product.sku_id if item.product else "UNMATCHED_SKU"
            brand = item.product.brand if item.product else (item.unmatched_raw_text or "")
            category = item.product.category if item.product else "Triage"
            pack_size = item.product.pack_size if item.product else "1 Unit"
            allocated_qty = item.allocated_quantity if item.allocated_quantity is not None else item.quantity
            line_items_data.append({
                "id": str(item.id),
                "sku_id": sku,
                "brand": brand,
                "category": category,
                "pack_size": pack_size,
                "quantity": item.quantity,
                "allocated_quantity": item.allocated_quantity,
                "unit_price": float(item.unit_price),
                "total_price": float(allocated_qty * item.unit_price)
            })

        results.append({
            "id": str(o.id),
            "order_id": o.internal_order_id,
            "customer": cust_name,
            "channel": o.source,
            "amount": float(amount),
            "status": status_resolved,
            "created_on": o.created_at.isoformat() + "Z",
            "eta": o.created_at.isoformat() + "Z",
            "invoice_type": o.invoice_type,
            "raw_source_text": o.raw_source_text,
            "line_items": line_items_data
        })

    return results


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    tenant_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Consolidated dashboard overview endpoint returning metrics, recent orders,
    and collections aging donut data in a single request.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    if str(tenant_id) == "d3b07384-d113-4956-a5d2-64be7357c11d":
        ensure_demo_data(db, tenant_id)
    tenant_context.set(tenant_id)

    # Parse date filters if provided
    start_dt = None
    end_dt = None
    if start_date:
        try:
            if "T" in start_date:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00").replace("+00:00", ""))
            else:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except Exception:
            pass
    if end_date:
        try:
            if "T" in end_date:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00").replace("+00:00", ""))
            else:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except Exception:
            pass

    # ---------------- METRICS CALCULATION ----------------
    # 1. Total Sales (sum of LineItems in non-Draft orders)
    ledger_alias = aliased(OrderStateLedger)
    valid_orders_sub = (
        select(OrderStateLedger.order_id)
        .where(
            and_(
                OrderStateLedger.to_status != "Draft",
                OrderStateLedger.timestamp == (
                    select(func.max(ledger_alias.timestamp))
                    .where(ledger_alias.order_id == OrderStateLedger.order_id)
                    .scalar_subquery()
                )
            )
        )
    )

    total_sales_stmt = (
        select(func.sum(OrderLineItem.quantity * OrderLineItem.unit_price))
        .join(Order, OrderLineItem.order_id == Order.id)
        .where(Order.id.in_(valid_orders_sub))
        .where(Order.tenant_id == tenant_id)
    )
    if start_dt:
        total_sales_stmt = total_sales_stmt.where(Order.created_at >= start_dt)
    if end_dt:
        total_sales_stmt = total_sales_stmt.where(Order.created_at <= end_dt)
    total_sales = db.execute(total_sales_stmt).scalar() or 0.0

    # 2. Orders Count
    orders_count_stmt = select(func.count(Order.id)).where(Order.tenant_id == tenant_id)
    if start_dt:
        orders_count_stmt = orders_count_stmt.where(Order.created_at >= start_dt)
    if end_dt:
        orders_count_stmt = orders_count_stmt.where(Order.created_at <= end_dt)
    orders_count = db.execute(orders_count_stmt).scalar() or 0

    # 3. Average Order Value
    aov = total_sales / orders_count if orders_count > 0 else 0.0

    # Calculate comparison trend changes if date filters are present
    total_sales_change = 0.0
    orders_count_change = 0.0
    average_order_value_change = 0.0

    if start_dt and end_dt:
        delta = end_dt - start_dt
        hist_start_dt = start_dt - delta
        hist_end_dt = start_dt

        hist_total_sales_stmt = (
            select(func.sum(OrderLineItem.quantity * OrderLineItem.unit_price))
            .join(Order, OrderLineItem.order_id == Order.id)
            .where(Order.id.in_(valid_orders_sub))
            .where(Order.tenant_id == tenant_id)
            .where(Order.created_at >= hist_start_dt)
            .where(Order.created_at <= hist_end_dt)
        )
        hist_total_sales = db.execute(hist_total_sales_stmt).scalar() or 0.0

        hist_orders_count_stmt = (
            select(func.count(Order.id))
            .where(Order.tenant_id == tenant_id)
            .where(Order.created_at >= hist_start_dt)
            .where(Order.created_at <= hist_end_dt)
        )
        hist_orders_count = db.execute(hist_orders_count_stmt).scalar() or 0

        hist_aov = hist_total_sales / hist_orders_count if hist_orders_count > 0 else 0.0

        if hist_total_sales > 0:
            total_sales_change = float((total_sales - hist_total_sales) / hist_total_sales * 100)
        if hist_orders_count > 0:
            orders_count_change = float((orders_count - hist_orders_count) / hist_orders_count * 100)
        if hist_aov > 0:
            average_order_value_change = float((aov - hist_aov) / hist_aov * 100)

    # 4. Outstanding Collections (Snapshot - Timeframe-Irrespective)
    outstanding_stmt = select(func.sum(Invoice.total_amount)).where(Invoice.tenant_id == tenant_id)
    outstanding = db.execute(outstanding_stmt).scalar() or 0.0

    # 5. Inventory counts (Low Stock, Out of Stock, Total SKUs, Inventory Value)
    total_skus_count = db.query(Inventory).filter(Inventory.tenant_id == tenant_id).count()

    low_stock_count = db.query(Inventory).filter(
        and_(
            Inventory.tenant_id == tenant_id,
            Inventory.quantity_on_hand < Inventory.low_stock_threshold,
            Inventory.quantity_on_hand > 0
        )
    ).count()

    out_of_stock_count = db.query(Inventory).filter(
        and_(
            Inventory.tenant_id == tenant_id,
            Inventory.quantity_on_hand == 0
        )
    ).count()

    inventory_val_sum = db.query(func.sum(Inventory.quantity_on_hand * Product.base_price))\
        .join(Product, Inventory.sku_id == Product.id)\
        .filter(Inventory.tenant_id == tenant_id).scalar() or 0.0

    if inventory_val_sum >= 10000000:
        inventory_value_str = f"₹ {(inventory_val_sum / 10000000):.2f} Cr"
    elif inventory_val_sum >= 100000:
        inventory_value_str = f"₹ {(inventory_val_sum / 100000):.2f}L"
    else:
        inventory_value_str = f"₹ {inventory_val_sum:,.2f}"

    # 6. High-Risk Overdue Accounts (60+ days) - Optimized set-based SQL subquery
    now = datetime.utcnow()
    cutoff_date = now - timedelta(days=60)
    
    credit_sub = (
        select(func.coalesce(func.sum(CustomerLedger.amount), 0.0))
        .where(
            and_(
                CustomerLedger.tenant_id == tenant_id,
                CustomerLedger.customer_id == Customer.id,
                CustomerLedger.type == "CREDIT"
            )
        )
        .scalar_subquery()
    )

    debit_sub = (
        select(func.coalesce(func.sum(CustomerLedger.amount), 0.0))
        .where(
            and_(
                CustomerLedger.tenant_id == tenant_id,
                CustomerLedger.customer_id == Customer.id,
                CustomerLedger.type == "DEBIT",
                CustomerLedger.created_at < cutoff_date
            )
        )
        .scalar_subquery()
    )

    overdue_stmt = (
        select(func.count(Customer.id))
        .where(Customer.tenant_id == tenant_id)
        .where(debit_sub > credit_sub)
    )
    overdue_60_count = db.execute(overdue_stmt).scalar() or 0

    metrics = {
        "total_sales": float(total_sales),
        "total_sales_change": float(total_sales_change),
        "orders_count": int(orders_count),
        "orders_count_change": float(orders_count_change),
        "average_order_value": float(aov),
        "average_order_value_change": float(average_order_value_change),
        "outstanding_collections": float(outstanding),
        "outstanding_collections_change": 0.0,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "total_skus_count": total_skus_count,
        "inventory_value": inventory_value_str,
        "overdue_60_count": overdue_60_count,
        "total_skus": total_skus_count,
        "total_inventory_value": float(inventory_val_sum)
    }

    # ---------------- RECENT ORDERS CALCULATION ----------------
    orders = (
        db.query(Order)
        .options(
            joinedload(Order.customer),
            joinedload(Order.line_items).joinedload(OrderLineItem.product)
        )
        .filter(Order.tenant_id == tenant_id)
        .order_by(Order.created_at.desc())
        .limit(5)
        .all()
    )
    recent_orders = []
    
    for o in orders:
        cust_name = o.customer.retailer_name if o.customer else "Unknown Retailer"
        amount = sum(float(item.quantity * item.unit_price) for item in o.line_items)

        # Status badge conversion: Draft = "Pending", Confirmed = "Confirmed"
        status_raw = o.current_status
        has_triage_sku = any(
            item.product_id is None or (item.product is not None and item.product.sku_id in ("UNMATCHED_SKU", "UNMATCHED_TRIAGE_SKU"))
            for item in o.line_items
        )
        if has_triage_sku or status_raw == "pending_review":
            status_raw = "pending_review"
        status_resolved = "Pending" if status_raw == "Draft" else ("Needs Review" if status_raw in ["NEEDS_REVIEW", "pending_review"] else status_raw)

        line_items_data = []
        for item in o.line_items:
            sku = item.product.sku_id if item.product else "UNMATCHED_SKU"
            brand = item.product.brand if item.product else (item.unmatched_raw_text or "")
            category = item.product.category if item.product else "Triage"
            pack_size = item.product.pack_size if item.product else "1 Unit"
            allocated_qty = item.allocated_quantity if item.allocated_quantity is not None else item.quantity
            line_items_data.append({
                "id": str(item.id),
                "sku_id": sku,
                "brand": brand,
                "category": category,
                "pack_size": pack_size,
                "quantity": item.quantity,
                "allocated_quantity": item.allocated_quantity,
                "unit_price": float(item.unit_price),
                "total_price": float(allocated_qty * item.unit_price)
            })

        recent_orders.append({
            "id": str(o.id),
            "order_id": o.internal_order_id,
            "customer": cust_name,
            "channel": o.source,
            "amount": float(amount),
            "status": status_resolved,
            "created_on": o.created_at.isoformat() + "Z",
            "eta": o.created_at.isoformat() + "Z",
            "invoice_type": o.invoice_type,
            "raw_source_text": o.raw_source_text,
            "line_items": line_items_data
        })

    # ---------------- COLLECTIONS DONUT CALCULATION ----------------
    donut_data = []
    if tenant_id == DEMO_TENANT_ID:
        donut_data = [
            {"name": "0-15 Days", "value": 845000, "percentage": 39},
            {"name": "16-30 Days", "value": 612000, "percentage": 29},
            {"name": "31-60 Days", "value": 475000, "percentage": 22},
            {"name": "60+ Days", "value": 205000, "percentage": 10}
        ]
    else:
        # Bucket by the invoice's own created_at (avoids an N+1 db.get(Order, ...) call
        # per invoice — see get_collections_donut below for the identical fix/rationale;
        # this duplicate copy runs on every dashboard-overview load, the main dashboard
        # page's initial fetch).
        invoices = db.query(Invoice).filter(Invoice.tenant_id == tenant_id).all()
        buckets = {
            "0-15 Days": 0.0,
            "16-30 Days": 0.0,
            "31-60 Days": 0.0,
            "60+ Days": 0.0
        }
        for inv in invoices:
            days_old = (now - inv.created_at).days
            if days_old <= 15:
                buckets["0-15 Days"] += float(inv.total_amount)
            elif days_old <= 30:
                buckets["16-30 Days"] += float(inv.total_amount)
            elif days_old <= 60:
                buckets["31-60 Days"] += float(inv.total_amount)
            else:
                buckets["60+ Days"] += float(inv.total_amount)

        total_bucket_sum = sum(buckets.values())
        if total_bucket_sum == 0:
            donut_data = [
                {"name": "0-15 Days", "value": 0, "percentage": 0},
                {"name": "16-30 Days", "value": 0, "percentage": 0},
                {"name": "31-60 Days", "value": 0, "percentage": 0},
                {"name": "60+ Days", "value": 0, "percentage": 0}
            ]
        else:
            donut_data = [
                {"name": name, "value": val, "percentage": int(round((val / total_bucket_sum) * 100))}
                for name, val in buckets.items()
            ]

    return {
        "metrics": metrics,
        "recent_orders": recent_orders,
        "donut_data": donut_data
    }


@router.get("/order-details/{order_id}")
def get_order_details(
    order_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Surfaces row-level OrderLineItem details for a specific order.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = db.query(OrderLineItem).filter_by(order_id=order_id).all()
    # Batch-fetch all referenced products in a single query instead of one db.get() per
    # line item — avoids an N+1 query pattern that scaled with order size.
    product_ids = {item.product_id for item in items if item.product_id is not None}
    products_by_id = {}
    if product_ids:
        products_by_id = {
            p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()
        }
    details = []
    for item in items:
        prod = products_by_id.get(item.product_id) if item.product_id is not None else None
        allocated_qty = item.allocated_quantity if item.allocated_quantity is not None else item.quantity
        details.append({
            "id": str(item.id),
            "sku_id": prod.sku_id if prod else "UNMATCHED_SKU",
            "brand": prod.brand if prod else (item.unmatched_raw_text or ""),
            "category": prod.category if prod else "Triage",
            "pack_size": prod.pack_size if prod else "1 Unit",
            "quantity": item.quantity,
            "allocated_quantity": item.allocated_quantity,
            "unit_price": float(item.unit_price),
            "total_price": float(allocated_qty * item.unit_price),
            "raw_source_text": order.raw_source_text,
            "product_id": str(item.product_id) if item.product_id is not None else None
        })
    return details


# SKUs the WhatsApp ingestion pipeline assigns to line items it could not resolve.
UNMATCHED_SKUS = ("UNMATCHED_SKU", "UNMATCHED_TRIAGE_SKU")


@router.get("/customer-whatsapp-thread/{customer_id}")
def get_customer_whatsapp_thread(
    customer_id: uuid.UUID,
    tenant_id: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns the most recent WhatsApp-sourced order for a customer along with its
    line items. The Messages cockpit uses this to render the real AI-ingested
    order (created by the WhatsApp webhook pipeline) instead of mock data.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    ensure_demo_data(db, tenant_id)
    tenant_context.set(tenant_id)

    order = (
        db.query(Order)
        .filter(
            Order.tenant_id == tenant_id,
            Order.customer_id == customer_id,
            Order.source == "WhatsApp",
        )
        .order_by(Order.created_at.desc())
        .first()
    )

    if not order:
        return {"order": None, "items": [], "total": 0.0, "has_unmatched": False}

    items = []
    total = 0.0
    has_unmatched = False
    line_items = db.query(OrderLineItem).filter_by(order_id=order.id).all()
    # Batch-fetch all referenced products in a single query instead of one db.get() per
    # line item — avoids an N+1 query pattern that scaled with order size.
    product_ids = {li.product_id for li in line_items if li.product_id is not None}
    products_by_id = {}
    if product_ids:
        products_by_id = {
            p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()
        }
    for item in line_items:
        prod = products_by_id.get(item.product_id)
        sku_id = prod.sku_id if prod else "UNKNOWN"
        if sku_id in UNMATCHED_SKUS:
            has_unmatched = True
        line_total = float(item.quantity * item.unit_price)
        total += line_total
        items.append({
            "id": str(item.id),
            "sku_id": sku_id,
            "product_name": (prod.brand if prod and prod.brand else sku_id),
            "brand": prod.brand if prod else "",
            "category": prod.category if prod else "",
            "pack_size": prod.pack_size if prod else "",
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "total_price": line_total,
        })

    return {
        "order": {
            "id": str(order.id),
            "order_id": order.internal_order_id,
            "status": order.current_status,
            "source": order.source,
            "created_on": order.created_at.isoformat() + "Z",
            "invoice_type": order.invoice_type,
        },
        "items": items,
        "total": total,
        "has_unmatched": has_unmatched,
    }


@router.get("/collections-donut")
def get_collections_donut(
    tenant_id: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Calculatesoutstanding collection balances grouped by aging periods.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    if str(tenant_id) == "d3b07384-d113-4956-a5d2-64be7357c11d":
        ensure_demo_data(db, tenant_id)
    tenant_context.set(tenant_id)

    # Grouping logic (0-15, 16-30, 31-60, 60+ days)
    # For demo tenant, we return the design mock directly.
    if tenant_id == DEMO_TENANT_ID:
        return [
            {"name": "0-15 Days", "value": 845000, "percentage": 39},
            {"name": "16-30 Days", "value": 612000, "percentage": 29},
            {"name": "31-60 Days", "value": 475000, "percentage": 22},
            {"name": "60+ Days", "value": 205000, "percentage": 10}
        ]

    # Dynamic calculation based on invoice age (invoice.created_at, not a per-row Order
    # lookup — using the invoice's own timestamp avoids an N+1 db.get(Order, ...) call
    # per invoice, which previously made this endpoint scale linearly with invoice count
    # (10-50+ seconds for tenants with thousands of invoices).
    now = datetime.utcnow()
    invoices = db.query(Invoice).filter(Invoice.tenant_id == tenant_id).all()

    buckets = {
        "0-15 Days": 0.0,
        "16-30 Days": 0.0,
        "31-60 Days": 0.0,
        "60+ Days": 0.0
    }

    for inv in invoices:
        days_old = (now - inv.created_at).days

        if days_old <= 15:
            buckets["0-15 Days"] += float(inv.total_amount)
        elif days_old <= 30:
            buckets["16-30 Days"] += float(inv.total_amount)
        elif days_old <= 60:
            buckets["31-60 Days"] += float(inv.total_amount)
        else:
            buckets["60+ Days"] += float(inv.total_amount)

    total = sum(buckets.values())
    if total == 0:
        return [
            {"name": "0-15 Days", "value": 0, "percentage": 0},
            {"name": "16-30 Days", "value": 0, "percentage": 0},
            {"name": "31-60 Days", "value": 0, "percentage": 0},
            {"name": "60+ Days", "value": 0, "percentage": 0}
        ]

    return [
        {"name": name, "value": val, "percentage": int(round((val / total) * 100))}
        for name, val in buckets.items()
    ]


@router.get("/recent-activity")
def get_recent_activity(
    tenant_id: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns a chronologically merged activity feed from the ledger and file ingestion logs.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    if str(tenant_id) == "d3b07384-d113-4956-a5d2-64be7357c11d":
        ensure_demo_data(db, tenant_id)
    tenant_context.set(tenant_id)

    activity = []

    # 1. Fetch newest Order Ledger logs
    ledgers = db.query(OrderStateLedger).order_by(OrderStateLedger.timestamp.desc()).limit(5).all()

    # Batch-fetch the orders and customers referenced by these ledger rows instead of
    # issuing a db.get(Order, ...) + a separate Customer query per ledger row.
    ledger_order_ids = {l.order_id for l in ledgers}
    orders_by_id = {}
    customers_by_id = {}
    if ledger_order_ids:
        orders_by_id = {
            o.id: o for o in db.query(Order).filter(Order.id.in_(ledger_order_ids)).all()
        }
        customer_ids = {o.customer_id for o in orders_by_id.values() if o.customer_id is not None}
        if customer_ids:
            try:
                customers_by_id = {
                    c.id: c
                    for c in db.query(Customer)
                    .filter(Customer.id.in_(customer_ids))
                    .options(defer(Customer.phone_number))
                    .all()
                }
            except ProgrammingError as db_api_err:
                logger.error(
                    f"Database Schema Mismatch Intercepted inside Dashboard Processing Rails: {str(db_api_err)}"
                )
                customers_by_id = {}

    for l in ledgers:
        order = orders_by_id.get(l.order_id)
        if not order:
            continue
        try:
            customer = customers_by_id.get(order.customer_id) if order.customer_id is not None else None
            if customer:
                cust_name = getattr(customer, "retailer_name", "Registered Retailer")
            else:
                cust_name = "Walk-in Retailer"
        except Exception as general_err:
            logger.error(f"Unhandled Dashboard Pipeline Exception: {str(general_err)}")
            cust_name = "System Node"
        
        # Calculate time difference text
        minutes_ago = int((datetime.utcnow() - l.timestamp).total_seconds() / 60)
        time_text = f"{minutes_ago} min ago" if minutes_ago < 60 else f"{minutes_ago//60} hr ago" if minutes_ago < 1440 else "1 day ago"

        if l.to_status in ("Confirmed", "Partially Confirmed", "Awaiting Stock"):
            msg = f"Order {order.internal_order_id} confirmed by {cust_name}"
            category = "order"
        elif l.to_status == "Dispatched":
            msg = f"Order {order.internal_order_id} dispatched to {cust_name}"
            category = "delivery"
        else:
            msg = f"Order {order.internal_order_id} state updated to {l.to_status}"
            category = "system"

        activity.append({
            "message": msg,
            "time": time_text,
            "timestamp": l.timestamp,
            "category": category
        })

    # 2. Fetch newest Ingestion Job logs
    jobs = db.query(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(5).all()
    for j in jobs:
        minutes_ago = int((datetime.utcnow() - j.created_at).total_seconds() / 60)
        time_text = f"{minutes_ago} min ago" if minutes_ago < 60 else f"{minutes_ago//60} hr ago" if minutes_ago < 1440 else "1 day ago"

        if j.source in ["Excel", "CSV"]:
            msg = f"Stock updated for {j.total_rows} SKUs via file ingestion"
            category = "inventory"
        else:
            msg = f"WhatsApp webhook job processed: {j.successful_rows} successful"
            category = "system"

        activity.append({
            "message": msg,
            "time": time_text,
            "timestamp": j.created_at,
            "category": category
        })

    # Add hardcoded activities to replicate the exact activity list from the visual design asset
    if tenant_id == DEMO_TENANT_ID:
        activity.append({"message": "Payment of ₹ 45,320 received from Maruthi Stores", "time": "15 min ago", "timestamp": datetime.utcnow() - timedelta(minutes=15), "category": "payment"})
        activity.append({"message": 'New customer "Suresh Enterprises" registered', "time": "1 hr ago", "timestamp": datetime.utcnow() - timedelta(hours=1), "category": "customer"})
        activity.append({"message": "Stock updated for 32 SKUs", "time": "2 hrs ago", "timestamp": datetime.utcnow() - timedelta(hours=2), "category": "inventory"})
        activity.append({"message": "Delivery completed for order ORD-2505-1476", "time": "3 hrs ago", "timestamp": datetime.utcnow() - timedelta(hours=3), "category": "delivery"})

    # Sort merged list chronologically
    activity = sorted(activity, key=lambda a: a["timestamp"], reverse=True)
    return activity[:6] # Return top 6


@router.get("/customers")
def get_customers(
    tenant_id: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns all customers for a tenant.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    if str(tenant_id) == "d3b07384-d113-4956-a5d2-64be7357c11d":
        ensure_demo_data(db, tenant_id)
    tenant_context.set(tenant_id)
    customers = db.query(Customer).filter(Customer.tenant_id == tenant_id).all()
    results = []
    for c in customers:
        # Get alias phone number
        alias = db.query(CustomerAlias).filter(CustomerAlias.customer_id == c.id).first()
        phone = alias.alias_value if alias else "N/A"
        results.append({
            "id": str(c.id),
            "customer_id": c.customer_id,
            "retailer_name": c.retailer_name,
            "address_text": c.address_text,
            "gstin": c.gstin,
            "tax_group": c.tax_group,
            "payment_terms": c.payment_terms,
            "phone": phone,
            "credit_limit": float(c.credit_limit),
            "outstanding_balance": float(c.outstanding_balance),
            "whatsapp_notifications_enabled": c.whatsapp_notifications_enabled
        })
    return results


@router.get("/demand-gap-summary")
def get_demand_gap_summary(
    tenant_id: str | None = None,
    days: int = 7,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """
    Rolling-window summary of unmet customer demand.

    Query params:
      - tenant_id: UUID of the tenant (resolved from cookie/header if omitted)
      - days: look-back window in days; default 7, max 90

    Response shape is generic: `by_reason` is a list ordered by revenue_at_risk desc,
    one entry per reason_code present in the window. Adding a new reason_code in the
    backend automatically surfaces it here without a frontend schema change.
    """
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    tenant_context.set(resolved_tenant_id)

    # Clamp window to a sensible max
    days = max(1, min(days, 90))
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Base query: all demand_gaps for this tenant in the window
    gaps = (
        db.query(DemandGap)
        .filter(
            DemandGap.tenant_id == resolved_tenant_id,
            DemandGap.created_at >= cutoff,
        )
        .all()
    )

    # Aggregate totals across ALL reason codes
    total_revenue_at_risk = sum(float(g.revenue_at_risk) for g in gaps)
    distinct_customers = len({g.customer_id for g in gaps})

    # Group by reason_code
    by_reason_map: dict = {}
    for g in gaps:
        rc = g.reason_code
        if rc not in by_reason_map:
            by_reason_map[rc] = {
                "reason_code": rc,
                "events": 0,
                "units_gap": 0,          # None for reason codes without a unit concept
                "has_units": False,
                "revenue_at_risk": 0.0,
                "customer_ids": set(),
            }
        bucket = by_reason_map[rc]
        bucket["events"] += 1
        bucket["revenue_at_risk"] += float(g.revenue_at_risk)
        bucket["customer_ids"].add(g.customer_id)
        if g.gap_qty is not None:
            bucket["units_gap"] += g.gap_qty
            bucket["has_units"] = True

    by_reason = sorted(
        [
            {
                "reason_code": b["reason_code"],
                "events": b["events"],
                # units_gap is null for reason codes that have no quantity concept (e.g. CREDIT_LIMIT)
                "units_gap": b["units_gap"] if b["has_units"] else None,
                "revenue_at_risk": round(b["revenue_at_risk"], 2),
                "customers_affected": len(b["customer_ids"]),
            }
            for b in by_reason_map.values()
        ],
        key=lambda x: x["revenue_at_risk"],
        reverse=True,
    )

    return {
        "window_days": days,
        "total_revenue_at_risk": round(total_revenue_at_risk, 2),
        "distinct_customers_affected": distinct_customers,
        "by_reason": by_reason,
    }


@router.get("/onboarding-status")
def get_onboarding_status(
    tenant_id: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns real setup-completion state for the "Getting Started" onboarding
    checklist shown on an empty dashboard. Every flag reflects an actual
    database/config check — nothing here is hardcoded or simulated.
    """
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    tenant_context.set(resolved_tenant_id)

    tenant = db.get(DistributorTenant, resolved_tenant_id)

    has_product = db.query(Product.id).filter(Product.tenant_id == resolved_tenant_id).first() is not None
    has_customer = db.query(Customer.id).filter(Customer.tenant_id == resolved_tenant_id).first() is not None
    has_order = db.query(Order.id).filter(Order.tenant_id == resolved_tenant_id).first() is not None
    has_whatsapp = bool(tenant and tenant.whatsapp_phone_id)
    has_razorpay = bool(tenant and tenant.razorpay_key_id and tenant.razorpay_key_secret_enc)

    steps = [
        {"key": "add_product", "label": "Add your first product", "done": has_product},
        {"key": "add_customer", "label": "Add your first customer", "done": has_customer},
        {"key": "connect_whatsapp", "label": "Connect WhatsApp", "done": has_whatsapp},
        {"key": "connect_razorpay", "label": "Connect Razorpay", "done": has_razorpay},
        {"key": "first_order", "label": "Take your first order", "done": has_order},
    ]
    completed_count = sum(1 for s in steps if s["done"])

    return {
        "is_new_workspace": completed_count == 0,
        "completed_count": completed_count,
        "total_count": len(steps),
        "steps": steps,
    }


def parse_payment_terms_days(payment_terms: str | None) -> int:
    """Parse payment terms string to number of days."""
    if not payment_terms:
        return 30
    pt = payment_terms.strip().upper()
    if "COD" in pt:
        return 0
    # Handle "Net X" format
    if "NET" in pt:
        try:
            return int(''.join(filter(str.isdigit, pt.split("NET")[1][:5])))
        except:
            return 30
    # Handle "X-Y Days" format — use the higher number
    if "DAYS" in pt or "DAY" in pt:
        import re
        numbers = re.findall(r'\d+', pt)
        if numbers:
            return max(int(n) for n in numbers)
    # Handle plain number
    try:
        return int(''.join(filter(str.isdigit, pt))[:3])
    except:
        return 30


@router.get("/credit-risk-alerts")
def get_credit_risk_alerts(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Returns top customers by credit risk for dashboard widget.
    Shows max 5 customers, ordered by risk level then overdue days.
    """
    from app.models.customer import Customer
    from app.models.ledger import CustomerLedger
    from datetime import datetime, timedelta

    customers = db.query(Customer).filter(
        Customer.tenant_id == tenant_id,
        Customer.outstanding_balance > 0
    ).all()

    results = []
    for customer in customers:
        outstanding = float(customer.outstanding_balance)
        credit_limit = float(customer.credit_limit) if customer.credit_limit else 0
        credit_utilisation = (outstanding / credit_limit * 100) if credit_limit > 0 else 0

        # Calculate overdue days from oldest unpaid invoice
        from app.models.invoice import Invoice
        oldest_unpaid = db.query(func.min(Invoice.created_at)).filter(
            Invoice.customer_id == customer.id,
            Invoice.payment_status.in_(["UNPAID", "PARTIALLY_PAID"]),
            Invoice.total_amount > 0
        ).scalar()

        if not oldest_unpaid:
            continue

        payment_terms_days = parse_payment_terms_days(customer.payment_terms)
        due_date = oldest_unpaid + timedelta(days=payment_terms_days)
        overdue_days = max(0, (datetime.utcnow() - due_date).days)

        # Determine risk level
        if overdue_days > 45:
            risk_level = "high_risk"
        elif overdue_days > 15 or credit_utilisation > 70:
            risk_level = "caution"
        else:
            risk_level = "clear"

        if risk_level == "clear":
            continue  # Only show customers needing attention

        results.append({
            "customer_id": str(customer.id),
            "customer_name": customer.retailer_name,
            "outstanding": outstanding,
            "credit_limit": credit_limit,
            "credit_utilisation_pct": round(credit_utilisation, 1),
            "overdue_days": overdue_days,
            "risk_level": risk_level
        })

    logger.info("Credit risk scan: found %d customers at risk", len(results))

    # Sort: high_risk first, then by overdue days desc
    results.sort(key=lambda x: (
        0 if x["risk_level"] == "high_risk" else 1,
        -x["overdue_days"]
    ))

    return {
        "alerts": results[:5],  # max 5
        "total_at_risk_count": len(results),
        "total_at_risk_amount": sum(r["outstanding"] for r in results)
    }


@router.get("/cash-flow-forecast")
def get_cash_flow_forecast(
    tenant_id: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Cash flow forecasting signal for the collections dashboard:
      - expected_collections_this_week: outstanding balance for customers who are NOT
        already overdue beyond their credit terms, restricted to invoices whose due date
        (invoice.created_at + customer credit_days, via parse_credit_days) falls within
        the next 7 days.
      - at_risk: full outstanding balance for customers who already have at least one
        invoice past its due date (mirrors the "oldest unpaid invoice" overdue check used
        by /credit-risk-alerts).
    """
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    tenant_context.set(resolved_tenant_id)

    tenant = db.get(DistributorTenant, resolved_tenant_id)
    tenant_name = tenant.name if tenant else "Unknown"

    now = datetime.utcnow()
    week_from_now = now + timedelta(days=7)

    customers = db.query(Customer).filter(
        Customer.tenant_id == resolved_tenant_id,
        Customer.outstanding_balance > 0
    ).all()

    expected_total = 0.0
    at_risk_total = 0.0
    expected_customers_count = 0
    at_risk_customers_count = 0

    for customer in customers:
        invoices = db.query(Invoice).filter(
            Invoice.customer_id == customer.id,
            Invoice.payment_status.in_(["UNPAID", "PARTIALLY_PAID"]),
            Invoice.total_amount > 0
        ).all()
        if not invoices:
            continue

        credit_days = parse_credit_days(customer.payment_terms, customer.name, tenant_name)

        # Customer-level overdue check: same "oldest unpaid invoice" idiom as
        # /credit-risk-alerts — if the oldest unpaid invoice has passed its due date,
        # the customer is already overdue beyond their credit terms.
        oldest_created = min(inv.created_at for inv in invoices)
        oldest_due_date = oldest_created + timedelta(days=credit_days)
        is_overdue = oldest_due_date < now

        customer_outstanding = sum(float(inv.total_amount - inv.amount_paid) for inv in invoices)

        if is_overdue:
            at_risk_total += customer_outstanding
            at_risk_customers_count += 1
        else:
            due_this_week = sum(
                float(inv.total_amount - inv.amount_paid)
                for inv in invoices
                if (inv.created_at + timedelta(days=credit_days)) <= week_from_now
            )
            if due_this_week > 0:
                expected_total += due_this_week
                expected_customers_count += 1

    return {
        "expected_collections_this_week": round(expected_total, 2),
        "at_risk": round(at_risk_total, 2),
        "expected_customers_count": expected_customers_count,
        "at_risk_customers_count": at_risk_customers_count,
    }


@router.get("/decision-focus")
def get_decision_focus(
    tenant_id: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns actionable business intelligence for the Decision Focus card.
    Single endpoint, single DB pass — all data computed together.
    Each item has: type, headline, detail, amount_at_stake, action_url, priority
    """
    from app.models.whatsapp_message_log import WhatsappMessageLog
    import re

    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)

    decisions = []

    # ── 1. BATCH LOAD all data upfront (no N+1) ──────────────────────────────

    # Pending orders with line items pre-loaded
    pending_orders = db.query(Order).options(
        joinedload(Order.line_items).joinedload(OrderLineItem.product),
        joinedload(Order.customer)
    ).filter(
        Order.tenant_id == resolved_tenant_id,
        Order.status.in_(["Draft", "Pending"])
    ).all()

    # Orders needing review
    review_orders = db.query(Order).filter(
        Order.tenant_id == resolved_tenant_id,
        Order.status.in_(["pending_review", "NEEDS_REVIEW"])
    ).all()

    # Unpaid invoices
    unpaid_invoices = db.query(Invoice).filter(
        Invoice.tenant_id == resolved_tenant_id,
        Invoice.payment_status.in_(["UNPAID", "PARTIALLY_PAID"]),
        Invoice.total_amount > 0
    ).all()

    # All customers — batch loaded once into a dict
    customers = {
        c.id: c for c in db.query(Customer).filter(
            Customer.tenant_id == resolved_tenant_id
        ).all()
    }

    # All active products — batch loaded once into a dict
    products = {
        p.id: p for p in db.query(Product).filter(
            Product.tenant_id == resolved_tenant_id,
            Product.is_active == True
        ).all()
    }

    # Inventory items joined to products
    inventory_items = db.query(Inventory).join(
        Product, Inventory.sku_id == Product.id
    ).filter(
        Inventory.tenant_id == resolved_tenant_id,
        Product.is_active == True
    ).all()

    # Pending order quantities per product — computed from pre-loaded line items
    pending_product_qty: dict = {}
    for order in pending_orders:
        for item in order.line_items:
            if item.product_id:
                pending_product_qty[item.product_id] = (
                    pending_product_qty.get(item.product_id, 0) + item.quantity
                )

    # Last payment reminder per customer — batch loaded, no loop queries
    last_reminders: dict = {}
    reminder_logs = db.query(WhatsappMessageLog).filter(
        WhatsappMessageLog.tenant_id == resolved_tenant_id,
        WhatsappMessageLog.event == "payment_reminder"
    ).order_by(WhatsappMessageLog.created_at.desc()).all()
    for log in reminder_logs:
        if log.customer_id not in last_reminders:
            last_reminders[log.customer_id] = log.created_at

    # ── 2. COMPUTE DECISIONS (pure in-memory, zero extra DB calls) ────────────

    # Decision A — Pending orders blocking revenue
    if pending_orders:
        total_blocked = sum(
            sum(
                float((item.allocated_quantity or item.quantity) * item.unit_price)
                for item in order.line_items
            )
            for order in pending_orders
        )
        oldest = min(o.created_at for o in pending_orders)
        oldest_pending_hours = int((datetime.utcnow() - oldest).total_seconds() / 3600)
        decisions.append({
            "type": "pending_orders",
            "priority": 1,
            "icon": "📦",
            "headline": f"₹{total_blocked:,.0f} revenue waiting",
            "detail": f"{len(pending_orders)} orders pending confirmation. Oldest: {oldest_pending_hours}h ago.",
            "amount_at_stake": total_blocked,
            "action_label": "Confirm Now",
            "action_url": "/dashboard/orders?status=Pending"
        })

    # Decision B — Orders needing review
    if review_orders:
        decisions.append({
            "type": "needs_review",
            "priority": 2,
            "icon": "💬",
            "headline": f"{len(review_orders)} order{'s' if len(review_orders) > 1 else ''} need your input",
            "detail": "Items couldn't be matched automatically. Review to confirm or reject.",
            "amount_at_stake": 0,
            "action_label": "Review",
            "action_url": "/dashboard/orders?status=Needs+Review"
        })

    # Decision C — Overdue collections
    now = datetime.utcnow()
    overdue_customers = []
    for invoice in unpaid_invoices:
        customer = customers.get(invoice.customer_id)
        if not customer:
            continue
        pt = customer.payment_terms or "Net 30"
        days = 30
        if "Net" in pt:
            try:
                days = int(''.join(filter(str.isdigit, pt.split("Net")[1][:5])))
            except Exception:
                days = 30
        due_date = invoice.created_at + timedelta(days=days)
        overdue_days = (now - due_date).days
        if overdue_days > 0:
            last_reminder = last_reminders.get(invoice.customer_id)
            days_since_reminder = (now - last_reminder).days if last_reminder else 999
            overdue_customers.append({
                "customer_id": str(invoice.customer_id),
                "name": customer.retailer_name,
                "outstanding": float(customer.outstanding_balance),
                "overdue_days": overdue_days,
                "days_since_reminder": days_since_reminder
            })

    if overdue_customers:
        overdue_customers.sort(key=lambda x: (-x["overdue_days"], -x["days_since_reminder"]))
        total_overdue = sum(c["outstanding"] for c in overdue_customers)
        most_urgent = overdue_customers[0]
        decisions.append({
            "type": "overdue_collections",
            "priority": 3,
            "icon": "💰",
            "headline": f"₹{total_overdue:,.0f} overdue from {len(overdue_customers)} customer{'s' if len(overdue_customers) > 1 else ''}",
            "detail": f"{most_urgent['name']} hasn't paid in {most_urgent['overdue_days']} days. {'No reminder sent recently.' if most_urgent['days_since_reminder'] > 3 else 'Reminder sent recently.'}",
            "amount_at_stake": total_overdue,
            "action_label": "View Collections",
            "action_url": "/dashboard/collections"
        })

    # Decision D — Stock-out risk (uses products dict — no loop queries)
    stockout_risks = []
    for inv in inventory_items:
        product_id = inv.sku_id
        pending_qty = pending_product_qty.get(product_id, 0)
        available = inv.quantity_on_hand
        if available <= 5 or (pending_qty > 0 and pending_qty > available):
            product = products.get(product_id)
            if not product:
                continue
            revenue_at_risk = float(pending_qty * (product.base_price or 0)) if pending_qty > available else 0
            stockout_risks.append({
                "product_name": f"{product.brand} {product.pack_size or ''}".strip(),
                "available": available,
                "pending_qty": pending_qty,
                "revenue_at_risk": revenue_at_risk
            })

    if stockout_risks:
        stockout_risks.sort(key=lambda x: -x["revenue_at_risk"])
        total_at_risk = sum(s["revenue_at_risk"] for s in stockout_risks)
        top = stockout_risks[0]
        detail = f"{top['product_name']}: {top['available']} units left"
        if top["pending_qty"] > top["available"]:
            detail += f", {top['pending_qty']} units needed for pending orders"
        decisions.append({
            "type": "stockout_risk",
            "priority": 4,
            "icon": "⚠️",
            "headline": f"{len(stockout_risks)} product{'s' if len(stockout_risks) > 1 else ''} may cause order failures",
            "detail": detail + (f". ₹{total_at_risk:,.0f} revenue at risk." if total_at_risk > 0 else ""),
            "amount_at_stake": total_at_risk,
            "action_label": "Restock Now",
            "action_url": "/dashboard/inventory"
        })

    decisions.sort(key=lambda x: x["priority"])

    return {
        "decisions": decisions,
        "all_clear": len(decisions) == 0,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/business-health-score")
def get_business_health_score(
    tenant_id: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Computes a 0-100 Business Health Score from 5 weighted signals.
    Only shown when sufficient data exists (7+ days, 5+ confirmed orders).

    Weights:
    - Collections Health: 30 points
    - Sales Momentum: 25 points  
    - Payment Recovery Speed: 20 points
    - Inventory Health: 15 points
    - Order Fulfillment Rate: 10 points
    """
    from app.models.order import Order, OrderLineItem
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.inventory import Inventory
    from app.models.product import Product
    from app.models.payment import Payment, PaymentInvoiceLink
    from sqlalchemy.orm import joinedload
    from datetime import datetime, timedelta

    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    now = datetime.utcnow()

    # ── BATCH LOAD all data upfront ──────────────────────────────────────────

    # All confirmed orders last 30 days
    confirmed_orders_30d = db.query(Order).options(
        joinedload(Order.line_items)
    ).filter(
        Order.tenant_id == resolved_tenant_id,
        Order.status.in_(["Confirmed", "Dispatched", "Delivered"]),
        Order.created_at >= now - timedelta(days=30)
    ).all()

    # This week vs last week orders
    this_week_orders = db.query(Order).filter(
        Order.tenant_id == resolved_tenant_id,
        Order.status.in_(["Confirmed", "Dispatched", "Delivered"]),
        Order.created_at >= now - timedelta(days=7)
    ).all()

    last_week_orders = db.query(Order).filter(
        Order.tenant_id == resolved_tenant_id,
        Order.status.in_(["Confirmed", "Dispatched", "Delivered"]),
        Order.created_at >= now - timedelta(days=14),
        Order.created_at < now - timedelta(days=7)
    ).all()

    # Minimum data threshold check
    total_confirmed = len(confirmed_orders_30d)
    
    min_created_at = db.query(func.min(Order.created_at)).filter(
        Order.tenant_id == resolved_tenant_id
    ).scalar()
    
    days_of_data = (now - min_created_at).days if min_created_at else 0

    if total_confirmed < 5 or days_of_data < 7:
        return {
            "has_sufficient_data": False,
            "message": "Score available after 7 days and 5+ confirmed orders",
            "days_of_data": days_of_data,
            "confirmed_orders": total_confirmed
        }

    # All unpaid invoices
    unpaid_invoices = db.query(Invoice).filter(
        Invoice.tenant_id == resolved_tenant_id,
        Invoice.payment_status.in_(["UNPAID", "PARTIALLY_PAID"]),
        Invoice.total_amount > 0
    ).all()

    # All customers
    customers = db.query(Customer).filter(
        Customer.tenant_id == resolved_tenant_id
    ).all()

    # All inventory
    inventory_items = db.query(Inventory).filter(
        Inventory.tenant_id == resolved_tenant_id
    ).all()

    # ── SIGNAL 1: Collections Health (30 points) ─────────────────────────────

    total_outstanding = sum(float(c.outstanding_balance) for c in customers)

    overdue_30d = 0
    for invoice in unpaid_invoices:
        customer = next((c for c in customers if c.id == invoice.customer_id), None)
        if not customer:
            continue
        pt = customer.payment_terms or "Net 30"
        days = 30
        if "Net" in pt:
            try:
                days = int(''.join(filter(str.isdigit, pt.split("Net")[1][:5])))
            except Exception:
                days = 30
        elif "Days" in pt:
            import re
            numbers = re.findall(r'\d+', pt)
            if numbers:
                days = max(int(n) for n in numbers)

        due_date = invoice.created_at + timedelta(days=days)
        if (now - due_date).days > 30:
            overdue_30d += float(invoice.total_amount - (invoice.amount_paid or 0))

    if total_outstanding == 0:
        collections_score = 30  # no outstanding = perfect
    else:
        overdue_ratio = overdue_30d / total_outstanding
        if overdue_ratio == 0:       collections_score = 30
        elif overdue_ratio < 0.10:   collections_score = 25
        elif overdue_ratio < 0.25:   collections_score = 19
        elif overdue_ratio < 0.50:   collections_score = 12
        else:                         collections_score = 4

    collections_detail = {
        "score": collections_score,
        "max": 30,
        "total_outstanding": total_outstanding,
        "overdue_30d": overdue_30d,
        "overdue_ratio_pct": round((overdue_30d / total_outstanding * 100) if total_outstanding > 0 else 0, 1),
        "status": "good" if collections_score >= 22 else "attention" if collections_score >= 12 else "critical"
    }

    # ── SIGNAL 2: Sales Momentum (25 points) ──────────────────────────────────

    this_week_revenue = sum(float(o.total_amount or 0) for o in this_week_orders)
    last_week_revenue = sum(float(o.total_amount or 0) for o in last_week_orders)

    if last_week_revenue == 0:
        growth_pct = 100 if this_week_revenue > 0 else 0
    else:
        growth_pct = ((this_week_revenue - last_week_revenue) / last_week_revenue) * 100

    if growth_pct > 20:    sales_score = 25
    elif growth_pct > 10:  sales_score = 21
    elif growth_pct > 0:   sales_score = 17
    elif growth_pct == 0:  sales_score = 12
    elif growth_pct > -10: sales_score = 7
    else:                   sales_score = 3

    sales_detail = {
        "score": sales_score,
        "max": 25,
        "this_week_revenue": this_week_revenue,
        "last_week_revenue": last_week_revenue,
        "growth_pct": round(growth_pct, 1),
        "status": "good" if sales_score >= 17 else "attention" if sales_score >= 10 else "critical"
    }

    # ── SIGNAL 3: Payment Recovery Speed (20 points) ──────────────────────────

    # Calculate avg days between invoice creation and payment using payments directly joined with invoices
    recent_payments_with_invoices = db.query(Payment, Invoice).join(
        PaymentInvoiceLink, PaymentInvoiceLink.payment_id == Payment.id
    ).join(
        Invoice, Invoice.id == PaymentInvoiceLink.invoice_id
    ).filter(
        Payment.tenant_id == resolved_tenant_id,
        Payment.status == "COMPLETED",
        Payment.created_at >= now - timedelta(days=30)
    ).all()

    if recent_payments_with_invoices:
        days_to_pay_list = [
            max(0, (pay.created_at - inv.created_at).days)
            for pay, inv in recent_payments_with_invoices
            if pay.created_at and inv.created_at
        ]
        avg_days_to_pay = sum(days_to_pay_list) / len(days_to_pay_list) if days_to_pay_list else 30
    else:
        avg_days_to_pay = 30  # default assumption

    if avg_days_to_pay <= 7:    recovery_score = 20
    elif avg_days_to_pay <= 15: recovery_score = 17
    elif avg_days_to_pay <= 30: recovery_score = 13
    elif avg_days_to_pay <= 45: recovery_score = 8
    else:                        recovery_score = 3

    recovery_detail = {
        "score": recovery_score,
        "max": 20,
        "avg_days_to_pay": round(avg_days_to_pay, 1),
        "status": "good" if recovery_score >= 13 else "attention" if recovery_score >= 8 else "critical"
    }

    # ── SIGNAL 4: Inventory Health (15 points) ────────────────────────────────

    active_products = db.query(Product).filter(
        Product.tenant_id == resolved_tenant_id,
        Product.is_active == True,
        Product.sku_id != "UNMATCHED_TRIAGE_SKU"
    ).count()

    if active_products == 0:
        inventory_score = 15
        stockout_count = 0
    else:
        stockout_count = sum(1 for inv in inventory_items if inv.quantity_on_hand == 0)
        stockout_ratio = stockout_count / active_products

        if stockout_ratio == 0:      inventory_score = 15
        elif stockout_ratio < 0.05:  inventory_score = 13
        elif stockout_ratio < 0.10:  inventory_score = 10
        elif stockout_ratio < 0.20:  inventory_score = 6
        else:                         inventory_score = 2

    inventory_detail = {
        "score": inventory_score,
        "max": 15,
        "total_products": active_products,
        "stockout_count": stockout_count,
        "status": "good" if inventory_score >= 10 else "attention" if inventory_score >= 6 else "critical"
    }

    # ── SIGNAL 5: Order Fulfillment Rate (10 points) ──────────────────────────

    if not confirmed_orders_30d:
        fulfillment_score = 10
        fulfillment_rate = 100.0
    else:
        fully_fulfilled = 0
        for order in confirmed_orders_30d:
            all_fulfilled = all(
                (item.allocated_quantity or 0) >= item.quantity
                for item in order.line_items
            )
            if all_fulfilled:
                fully_fulfilled += 1

        fulfillment_rate = (fully_fulfilled / len(confirmed_orders_30d)) * 100

        if fulfillment_rate >= 95:   fulfillment_score = 10
        elif fulfillment_rate >= 85: fulfillment_score = 8
        elif fulfillment_rate >= 70: fulfillment_score = 6
        elif fulfillment_rate >= 50: fulfillment_score = 3
        else:                         fulfillment_score = 1

    fulfillment_detail = {
        "score": fulfillment_score,
        "max": 10,
        "fulfillment_rate_pct": round(fulfillment_rate, 1),
        "status": "good" if fulfillment_score >= 7 else "attention" if fulfillment_score >= 4 else "critical"
    }

    # ── TOTAL SCORE ────────────────────────────────────────────────────────────

    total_score = (
        collections_score +
        sales_score +
        recovery_score +
        inventory_score +
        fulfillment_score
    )

    # Score band
    if total_score >= 85:   band = "excellent"
    elif total_score >= 70: band = "good"
    elif total_score >= 50: band = "attention"
    else:                    band = "at_risk"

    band_labels = {
        "excellent": "Excellent",
        "good": "Good",
        "attention": "Needs Attention",
        "at_risk": "At Risk"
    }

    band_colors = {
        "excellent": "green",
        "good": "yellow",
        "attention": "orange",
        "at_risk": "red"
    }

    # ── WEEK-ON-WEEK TREND ────────────────────────────────────────────────────
    # Simple proxy: compare this week revenue growth direction
    if growth_pct > 2:    trend = "up"
    elif growth_pct < -2: trend = "down"
    else:                  trend = "stable"

    # ── PRIMARY INSIGHT (one actionable line) ─────────────────────────────────
    # Find worst performing signal and generate insight
    signals = [
        (collections_score / 30, "collections", collections_detail),
        (sales_score / 25, "sales", sales_detail),
        (recovery_score / 20, "recovery", recovery_detail),
        (inventory_score / 15, "inventory", inventory_detail),
        (fulfillment_score / 10, "fulfillment", fulfillment_detail),
    ]
    worst_signal = min(signals, key=lambda x: x[0])

    insights = {
        "collections": f"₹{overdue_30d:,.0f} overdue for 30+ days — follow up with retailers today.",
        "sales": f"Sales dropped {abs(growth_pct):.0f}% vs last week — check if orders are coming in.",
        "recovery": f"Retailers take {avg_days_to_pay:.0f} days to pay on average — send payment reminders.",
        "inventory": f"{stockout_count} products out of stock — restock to avoid missing orders.",
        "fulfillment": f"Only {fulfillment_rate:.0f}% of orders fully fulfilled — check inventory levels."
    }

    primary_insight = insights.get(worst_signal[1], "Your business is running well.")
    if total_score >= 85:
        primary_insight = "Your business is performing excellently. Keep it up!"

    return {
        "has_sufficient_data": True,
        "score": total_score,
        "band": band,
        "band_label": band_labels[band],
        "band_color": band_colors[band],
        "trend": trend,
        "trend_points": abs(round(growth_pct / 4)),
        "primary_insight": primary_insight,
        "signals": {
            "collections": collections_detail,
            "sales": sales_detail,
            "recovery": recovery_detail,
            "inventory": inventory_detail,
            "fulfillment": fulfillment_detail
        },
        "generated_at": now.isoformat() + "Z"
    }

