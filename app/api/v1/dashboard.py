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

    # 4. Outstanding Collections (Snapshot - Timeframe-Irrespective)
    # Always run sum aggregation over the live, current ledger/invoice state tables
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
            "created_on": o.created_at.strftime("%d %b, %I:%M %p"),
            "eta": o.created_at.strftime("%d %b, %I:%M %p"),
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
            "created_on": o.created_at.strftime("%d %b, %I:%M %p"),
            "eta": o.created_at.strftime("%d %b, %I:%M %p"),
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
        invoices = db.query(Invoice).filter(Invoice.tenant_id == tenant_id).all()
        buckets = {
            "0-15 Days": 0.0,
            "16-30 Days": 0.0,
            "31-60 Days": 0.0,
            "60+ Days": 0.0
        }
        for inv in invoices:
            order_for_inv = db.get(Order, inv.order_id)
            if not order_for_inv:
                continue
            days_old = (now - order_for_inv.created_at).days
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
    details = []
    for item in items:
        prod = db.get(Product, item.product_id) if item.product_id is not None else None
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

    # Dynamic calculation based on invoice dates
    now = datetime.utcnow()
    invoices = db.query(Invoice).filter(Invoice.tenant_id == tenant_id).all()

    buckets = {
        "0-15 Days": 0.0,
        "16-30 Days": 0.0,
        "31-60 Days": 0.0,
        "60+ Days": 0.0
    }

    # As this is a simulation, we use a simple day count:
    # (Since SQLite might not have complex date diff, we do it in Python)
    for inv in invoices:
        # Match order to get created_at
        order = db.get(Order, inv.order_id)
        if not order:
            continue
        days_old = (now - order.created_at).days
        
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
    for l in ledgers:
        order = db.get(Order, l.order_id)
        if not order:
            continue
        try:
            customer = (
                db.query(Customer)
                .filter(Customer.id == order.customer_id)
                .options(defer(Customer.phone_number))
                .first()
            )
            if customer:
                cust_name = getattr(customer, "retailer_name", "Registered Retailer")
            else:
                cust_name = "Walk-in Retailer"
        except ProgrammingError as db_api_err:
            logger.error(
                f"Database Schema Mismatch Intercepted inside Dashboard Processing Rails: {str(db_api_err)}"
            )
            cust_name = "Operational Ingestion Influx"
        except Exception as general_err:
            logger.error(f"Unhandled Dashboard Pipeline Exception: {str(general_err)}")
            cust_name = "System Node"
        
        # Calculate time difference text
        minutes_ago = int((datetime.utcnow() - l.timestamp).total_seconds() / 60)
        time_text = f"{minutes_ago} min ago" if minutes_ago < 60 else f"{minutes_ago//60} hr ago" if minutes_ago < 1440 else "1 day ago"

        if l.to_status == "Confirmed":
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
