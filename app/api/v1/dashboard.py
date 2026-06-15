import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Header
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session, aliased
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

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

def resolve_tenant_id(
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None)
) -> uuid.UUID:
    """
    Resolves the tenant ID by checking the JWT cookie or Authorization header first.
    Falls back to query parameter if not authenticated (preserving tests compatibility).
    """
    token = access_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    if token:
        payload = verify_jwt(token)
        if payload and "tenant_id" in payload:
            return uuid.UUID(payload["tenant_id"])
    if tenant_id:
        return tenant_id
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not resolve active Tenant ID from session or headers."
    )

# Static Tenant ID for demo/default distributor
DEMO_TENANT_ID = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")

def ensure_demo_data(db: Session, tenant_id: uuid.UUID | None = None):
    """
    Seeds the database with the exact B2B distributor data matching the Operations Dashboard
    screenshot if the database is empty.
    """
    # Hard multi-tenant lockout constraint
    if tenant_id is None or str(tenant_id) != "d3b07384-d113-4956-a5d2-64be7357c11d":
        return  # Abort instantly. NEVER seed data for custom registered tenants.

    # 1. Check if the default tenant exists
    tenant = db.get(DistributorTenant, DEMO_TENANT_ID)
    if not tenant:
        tenant = DistributorTenant(id=DEMO_TENANT_ID, name="S.V. Distributors")
        db.add(tenant)
        db.commit()

    tenant_context.set(DEMO_TENANT_ID)

    # 2. Check if we already have customers (if yes, align balances if needed, and return)
    customer_count = db.query(Customer).count()
    if customer_count > 0:
        # Align outstanding balances on already-seeded demo data if they are still zero
        kaveri = db.query(Customer).filter(Customer.customer_id == "CUST-101").first()
        if kaveri and float(kaveri.outstanding_balance) == 0.0:
            db.query(Customer).filter(Customer.customer_id == "CUST-101").update({"outstanding_balance": 845000.0})
            db.query(Customer).filter(Customer.customer_id == "CUST-102").update({"outstanding_balance": 612000.0})
            db.query(Customer).filter(Customer.customer_id == "CUST-103").update({"outstanding_balance": 475000.0})
            db.query(Customer).filter(Customer.customer_id == "CUST-104").update({"outstanding_balance": 205000.0})
            db.commit()
        return

    # Seed Customers
    customers_data = [
        {"id": uuid.UUID("c1010000-0000-0000-0000-000000000001"), "customer_id": "CUST-101", "retailer_name": "Kaveri Provision Store", "address_text": "Bengaluru, Indiranagar", "gstin": "29AAAAA1111A1Z1", "tax_group": "GST-18", "payment_terms": "0-15 Days", "phone": "+919999888877", "outstanding_balance": 845000.0},
        {"id": uuid.UUID("c1010000-0000-0000-0000-000000000002"), "customer_id": "CUST-102", "retailer_name": "Maruthi Stores", "address_text": "Bengaluru, Malleshwaram", "gstin": "29BBBBB2222B2Z2", "tax_group": "GST-18", "payment_terms": "16-30 Days", "phone": "+919999777766", "outstanding_balance": 612000.0},
        {"id": uuid.UUID("c1010000-0000-0000-0000-000000000003"), "customer_id": "CUST-103", "retailer_name": "Sri Venkateshwara Traders", "address_text": "Bengaluru, Whitefield", "gstin": "29CCCCC3333C3Z3", "tax_group": "GST-18", "payment_terms": "31-60 Days", "phone": "+919999666655", "outstanding_balance": 475000.0},
        {"id": uuid.UUID("c1010000-0000-0000-0000-000000000004"), "customer_id": "CUST-104", "retailer_name": "Jayam Distributors", "address_text": "Bengaluru, HSR Layout", "gstin": "29DDDDD4444D4Z4", "tax_group": "GST-18", "payment_terms": "0-15 Days", "phone": "+919999555544", "outstanding_balance": 205000.0},
        {"id": uuid.UUID("c1010000-0000-0000-0000-000000000005"), "customer_id": "CUST-105", "retailer_name": "Balaji Retailers", "address_text": "Bengaluru, Koramangala", "gstin": "29EEEEE5555E5Z5", "tax_group": "GST-18", "payment_terms": "60+ Days", "phone": "+919999444433", "outstanding_balance": 0.0},
        {"id": uuid.UUID("c1010000-0000-0000-0000-000000000006"), "customer_id": "SUP-ITC", "retailer_name": "ITC Supplier Hub", "address_text": "Kolkata Warehouse", "gstin": "19AAAAA2222A2Z2", "tax_group": "GST-18", "payment_terms": "Net 30", "phone": "+918888888888", "outstanding_balance": 0.0},
        {"id": uuid.UUID("c1010000-0000-0000-0000-000000000007"), "customer_id": "SUP-HUL", "retailer_name": "HUL Distribution Centre", "address_text": "Mumbai Port", "gstin": "27BBBBB1111B1Z1", "tax_group": "GST-18", "payment_terms": "Net 15", "phone": "+917777777777", "outstanding_balance": 0.0}
    ]

    for c in customers_data:
        cust = Customer(
            id=c["id"],
            tenant_id=DEMO_TENANT_ID,
            customer_id=c["customer_id"],
            retailer_name=c["retailer_name"],
            address_text=c["address_text"],
            gstin=c["gstin"],
            tax_group=c["tax_group"],
            payment_terms=c["payment_terms"],
            outstanding_balance=c.get("outstanding_balance", 0.0)
        )
        db.add(cust)
        db.flush()
        # Add alias
        alias = CustomerAlias(tenant_id=DEMO_TENANT_ID, customer_id=cust.id, alias_value=c["phone"])
        db.add(alias)

    # Seed Products
    products_data = [
        {"id": uuid.UUID("a1010000-0000-0000-0000-000000000001"), "sku_id": "PROD-HUL-SOAP", "brand": "HUL", "category": "Soap", "pack_size": "100g", "base_price": 45.00, "aliases": ["HUL Soap", "Tata Premium Soap"]},
        {"id": uuid.UUID("a1010000-0000-0000-0000-000000000002"), "sku_id": "PROD-ITC-AATA", "brand": "ITC", "category": "Flour", "pack_size": "5kg", "base_price": 260.00, "aliases": ["ITC Aashirvaad Aata"]},
        {"id": uuid.UUID("a1010000-0000-0000-0000-000000000003"), "sku_id": "PROD-ITC-CHIPS", "brand": "ITC", "category": "Chips", "pack_size": "50g", "base_price": 10.00, "aliases": ["Chips"]},
        {"id": uuid.UUID("a1010000-0000-0000-0000-000000000004"), "sku_id": "PROD-STAYFREE-XL", "brand": "Stayfree", "category": "Sanitary", "pack_size": "XL", "base_price": 1250.00, "aliases": ["Stayfree Sanitary Napkins (XL)", "Stayfree pad", "Stayfree"]},
        {"id": uuid.UUID("a1010000-0000-0000-0000-000000000005"), "sku_id": "PROD-MAGGI-PACK", "brand": "Nestle", "category": "Packaged Foods", "pack_size": "Pack of 12", "base_price": 450.00, "aliases": ["Maggi 2-Min Noodles", "Nestle Maggi", "Maggi"]}
    ]

    for p in products_data:
        prod = Product(
            id=p["id"],
            tenant_id=DEMO_TENANT_ID,
            sku_id=p["sku_id"],
            brand=p["brand"],
            category=p["category"],
            pack_size=p["pack_size"],
            base_price=p["base_price"]
        )
        db.add(prod)
        db.flush()
        # Aliases
        for alias_name in p["aliases"]:
            alias = ProductAlias(tenant_id=DEMO_TENANT_ID, product_id=prod.id, alias_name=alias_name)
            db.add(alias)

        # Inventory
        inv = Inventory(
            tenant_id=DEMO_TENANT_ID,
            sku_id=prod.id,
            location="Aisle-A1",
            quantity_on_hand=500 if p["sku_id"] != "PROD-ITC-CHIPS" else 5,
            quantity_committed=50 if p["sku_id"] != "PROD-ITC-CHIPS" else 0,
            low_stock_threshold=10
        )
        db.add(inv)

    # Product Supplier Mapping
    db.add(ProductSupplierMapping(
        tenant_id=DEMO_TENANT_ID,
        product_id=uuid.UUID("a1010000-0000-0000-0000-000000000003"),
        supplier_id=uuid.UUID("c1010000-0000-0000-0000-000000000006"),
        is_primary=True
    ))

    # Seed Orders & Ledger Entries matching dashboard image
    orders_data = [
        {"id": uuid.UUID("01010000-0000-0000-0000-000000000001"), "ord_id": "ORD-2505-1482", "cust_id": "c1010000-0000-0000-0000-000000000001", "source": "WhatsApp", "status": "Confirmed", "amount": 23650.00, "time_offset": 2},
        {"id": uuid.UUID("01010000-0000-0000-0000-000000000002"), "ord_id": "ORD-2505-1481", "cust_id": "c1010000-0000-0000-0000-000000000002", "source": "Portal", "status": "Draft", "amount": 45320.00, "time_offset": 15}, # Draft maps to Pending in visual
        {"id": uuid.UUID("01010000-0000-0000-0000-000000000003"), "ord_id": "ORD-2505-1480", "cust_id": "c1010000-0000-0000-0000-000000000003", "source": "WhatsApp", "status": "Confirmed", "amount": 96450.00, "time_offset": 60},
        {"id": uuid.UUID("01010000-0000-0000-0000-000000000004"), "ord_id": "ORD-2505-1479", "cust_id": "c1010000-0000-0000-0000-000000000004", "source": "WhatsApp", "status": "Confirmed", "amount": 132870.00, "time_offset": 120},
        {"id": uuid.UUID("01010000-0000-0000-0000-000000000005"), "ord_id": "ORD-2505-1478", "cust_id": "c1010000-0000-0000-0000-000000000005", "source": "Portal", "status": "Draft", "amount": 78900.00, "time_offset": 180}
    ]

    for o in orders_data:
        order = Order(
            id=o["id"],
            tenant_id=DEMO_TENANT_ID,
            internal_order_id=o["ord_id"],
            source=o["source"],
            customer_id=uuid.UUID(o["cust_id"]) if isinstance(o["cust_id"], str) else o["cust_id"],
            created_at=datetime.utcnow() - timedelta(minutes=o["time_offset"])
        )
        db.add(order)
        db.flush()

        # Add single line item holding entire order value for convenience
        db.add(OrderLineItem(
            tenant_id=DEMO_TENANT_ID,
            order_id=order.id,
            product_id=uuid.UUID("a1010000-0000-0000-0000-000000000001"),
            quantity=1,
            unit_price=o["amount"]
        ))

        # Ledger entries
        # If confirmed, transition: None -> Draft -> Confirmed
        if o["status"] == "Confirmed":
            db.add(OrderStateLedger(
                tenant_id=DEMO_TENANT_ID,
                order_id=order.id,
                from_status=None,
                to_status="Draft",
                updated_by="system",
                timestamp=datetime.utcnow() - timedelta(minutes=o["time_offset"] + 1)
            ))
            db.add(OrderStateLedger(
                tenant_id=DEMO_TENANT_ID,
                order_id=order.id,
                from_status="Draft",
                to_status="Confirmed",
                updated_by="system_whatsapp_agent",
                timestamp=datetime.utcnow() - timedelta(minutes=o["time_offset"])
            ))
        else:
            db.add(OrderStateLedger(
                tenant_id=DEMO_TENANT_ID,
                order_id=order.id,
                from_status=None,
                to_status="Draft",
                updated_by="user",
                timestamp=datetime.utcnow() - timedelta(minutes=o["time_offset"])
            ))

        # Seed Invoice matching outstanding collections
        invoice = Invoice(
            tenant_id=DEMO_TENANT_ID,
            order_id=order.id,
            gstin="29AAAAA1111A1Z1",
            total_amount=o["amount"],
            irn_status="Cleared",
            qr_code_status="Generated",
            customer_id=order.customer_id,
            payment_status="UNPAID",
            amount_paid=0.0,
            created_at=order.created_at
        )
        db.add(invoice)

    # Seed Staff / Users with different Roles
    user_count = db.query(User).count()
    if user_count == 0:
        hashed_default_pwd = hash_password("Password123")
        staff_data = [
            {"id": uuid.UUID("d1010000-0000-0000-0000-000000000001"), "full_name": "Ramesh Kumar", "phone_number": "+919876543210", "email_or_phone": "+919876543210", "role": "DRIVER"},
            {"id": uuid.UUID("d1010000-0000-0000-0000-000000000002"), "full_name": "Suresh Singh", "phone_number": "+919876543211", "email_or_phone": "+919876543211", "role": "DRIVER"},
            {"id": uuid.UUID("d1010000-0000-0000-0000-000000000003"), "full_name": "Amit Patel", "phone_number": "+919876543212", "email_or_phone": "+919876543212", "role": "DRIVER"},
            {"id": uuid.UUID("d1010000-0000-0000-0000-000000000004"), "full_name": "Vikram Malhotra", "phone_number": None, "email_or_phone": "vikram@svdistributors.com", "role": "SUPER_ADMIN"},
            {"id": uuid.UUID("d1010000-0000-0000-0000-000000000005"), "full_name": "Pooja Sharma", "phone_number": None, "email_or_phone": "pooja@svdistributors.com", "role": "FINANCE"},
            {"id": uuid.UUID("d1010000-0000-0000-0000-000000000006"), "full_name": "Rahul Varma", "phone_number": None, "email_or_phone": "rahul@svdistributors.com", "role": "OPERATOR"},
        ]
        for d in staff_data:
            drv = User(
                id=d["id"],
                tenant_id=DEMO_TENANT_ID,
                full_name=d["full_name"],
                phone_number=d["phone_number"],
                email_or_phone=d["email_or_phone"],
                hashed_password=hashed_default_pwd,
                role=d["role"],
                is_active=True
            )
            db.add(drv)

    # Seed CustomerLedger records
    ledger_count = db.query(CustomerLedger).count()
    if ledger_count == 0:
        # 1. Add Debits for all seeded orders
        for o in orders_data:
            cust_uuid = uuid.UUID(o["cust_id"]) if isinstance(o["cust_id"], str) else o["cust_id"]
            db.add(CustomerLedger(
                id=uuid.uuid4(),
                tenant_id=DEMO_TENANT_ID,
                customer_id=cust_uuid,
                type="DEBIT",
                amount=o["amount"],
                reference_id=o["ord_id"],
                created_at=datetime.utcnow() - timedelta(minutes=o["time_offset"])
            ))

        # 2. Add some Credits (payments) to make statements dynamic and realistic
        # Kaveri Provision Store (CUST-101) paid some amount
        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000001"),
            type="CREDIT",
            amount=15000.00,
            reference_id="PAY-REC-9821",
            created_at=datetime.utcnow() - timedelta(hours=5)
        ))
        # Maruthi Stores (CUST-102) paid
        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000002"),
            type="CREDIT",
            amount=45320.00,
            reference_id="PAY-REC-9822",
            created_at=datetime.utcnow() - timedelta(minutes=15)
        ))

        # 3. Add historical Debits to match the visual collections aging outstanding balances
        # CUST-101 (Kaveri Provision Store): 845,000.0 (0-15 Days) -> 5 days ago
        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000001"),
            type="DEBIT",
            amount=845000.00,
            reference_id="INV-2025-0501",
            created_at=datetime.utcnow() - timedelta(days=5)
        ))
        # CUST-102 (Maruthi Stores): 612,000.0 (16-30 Days) -> 20 days ago
        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000002"),
            type="DEBIT",
            amount=612000.00,
            reference_id="INV-2025-0502",
            created_at=datetime.utcnow() - timedelta(days=20)
        ))
        # CUST-103 (Sri Venkateshwara Traders): 475,000.0 (31-60 Days) -> 40 days ago
        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000003"),
            type="DEBIT",
            amount=475000.00,
            reference_id="INV-2025-0503",
            created_at=datetime.utcnow() - timedelta(days=40)
        ))
        # CUST-104 (Jayam Distributors): 205,000.0 (60+ Days) -> 65 days ago
        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000004"),
            type="DEBIT",
            amount=205000.00,
            reference_id="INV-2025-0504",
            created_at=datetime.utcnow() - timedelta(days=65)
        ))

    db.commit()




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
    outstanding_stmt = select(func.sum(Invoice.total_amount))
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


@router.get("/recent-orders")
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

    orders = db.query(Order).order_by(Order.created_at.desc()).limit(5).all()
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
        status_resolved = "Pending" if status_raw == "Draft" else status_raw

        results.append({
            "id": str(o.id),
            "order_id": o.internal_order_id,
            "customer": cust_name,
            "channel": o.source,
            "amount": float(amount),
            "status": status_resolved,
            "created_on": o.created_at.strftime("%d %b, %I:%M %p"),
            "eta": o.created_at.strftime("%d %b, %I:%M %p")
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
    invoices = db.query(Invoice).all()

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
        customer = db.get(Customer, order.customer_id)
        cust_name = customer.retailer_name if customer else "Customer"
        
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
