import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Header
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session, aliased, defer
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

from pydantic import BaseModel

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

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

from app.services.tenant_service import resolve_tenant_id, DEMO_TENANT_ID
from app.services.demo_service import ensure_demo_data




@router.get("/metrics")
def get_dashboard_metrics(
    tenant_id: uuid.UUID | None = None,
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
    customers = db.query(Customer).filter(Customer.tenant_id == tenant_id).all()
    overdue_60_count = 0

    for customer in customers:
        entries = db.query(CustomerLedger).filter(
            and_(
                CustomerLedger.tenant_id == tenant_id,
                CustomerLedger.customer_id == customer.id
            )
        ).order_by(CustomerLedger.created_at.asc()).all()

        total_credits = sum(e.amount for e in entries if e.type == "CREDIT")

        has_overdue = False
        for e in entries:
            if e.type == "DEBIT":
                if total_credits >= e.amount:
                    total_credits -= e.amount
                else:
                    if e.created_at < cutoff_date:
                        has_overdue = True
                        break
                    total_credits = 0
        if has_overdue:
            overdue_60_count += 1

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
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns the latest 5 orders with their status resolved from the ledger.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    ensure_demo_data(db, tenant_id)
    tenant_context.set(tenant_id)

    orders = db.query(Order).filter(Order.tenant_id == tenant_id).order_by(Order.created_at.desc()).limit(5).all()
    results = []
    
    for o in orders:
        # Resolve customer name
        customer = db.get(Customer, o.customer_id)
        cust_name = customer.retailer_name if customer else "Unknown Retailer"

        # Calculate total amount
        amount_stmt = select(func.sum(OrderLineItem.quantity * OrderLineItem.unit_price)).where(OrderLineItem.order_id == o.id)
        amount = db.execute(amount_stmt).scalar() or 0.0

        # Status badge conversion: Draft = "Pending", Confirmed = "Confirmed"
        status_raw = o.current_status
        has_triage_sku = any(
            db.get(Product, item.product_id) is not None and db.get(Product, item.product_id).sku_id == "UNMATCHED_TRIAGE_SKU"
            for item in o.line_items
        )
        if has_triage_sku:
            status_raw = "NEEDS_REVIEW"
        status_resolved = "Pending" if status_raw == "Draft" else ("Needs Review" if status_raw == "NEEDS_REVIEW" else status_raw)

        results.append({
            "id": str(o.id),
            "order_id": o.internal_order_id,
            "customer": cust_name,
            "channel": o.source,
            "amount": float(amount),
            "status": status_resolved,
            "created_on": o.created_at.strftime("%d %b, %I:%M %p"),
            "eta": o.created_at.strftime("%d %b, %I:%M %p"),
            "invoice_type": o.invoice_type
        })

    return results


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
        prod = db.get(Product, item.product_id)
        details.append({
            "id": str(item.id),
            "sku_id": prod.sku_id if prod else "UNKNOWN",
            "brand": prod.brand if prod else "",
            "category": prod.category if prod else "",
            "pack_size": prod.pack_size if prod else "",
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "total_price": float(item.quantity * item.unit_price)
        })
    return details


@router.get("/collections-donut")
def get_collections_donut(
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Calculatesoutstanding collection balances grouped by aging periods.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
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
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns a chronologically merged activity feed from the ledger and file ingestion logs.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
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
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns all customers for a tenant.
    """
    tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
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
            "outstanding_balance": float(c.outstanding_balance)
        })
    return results
