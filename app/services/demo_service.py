import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import tenant_context
from app.models.tenant import DistributorTenant
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product, ProductAlias, ProductSupplierMapping
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.invoice import Invoice
from app.models.inventory import Inventory
from app.models.user import User
from app.models.ledger import CustomerLedger
from app.utils.security import hash_password
from app.utils.phone import normalize_phone_number
from app.services.tenant_service import DEMO_TENANT_ID

def ensure_demo_data(db: Session, tenant_id: uuid.UUID | None = None):
    """
    Seeds the database with demo data for the demo tenant if not already seeded.
    Only runs for the well-known demo tenant ID — all other tenants are ignored.
    """
    # Hard multi-tenant lockout constraint
    if tenant_id != DEMO_TENANT_ID and str(tenant_id) != str(DEMO_TENANT_ID):
        return  # Abort immediately. NEVER seed default rows into custom distributor profiles.

    try:
        _seed_demo_data(db)
    except IntegrityError:
        db.rollback()  # Concurrent request already seeded — safe to ignore


def _seed_demo_data(db: Session):
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

    # Seed Customers (values will automatically be normalized by the @validates model validators)
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
            outstanding_balance=c.get("outstanding_balance", 0.0),
            phone_number=c["phone"]
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
        {"id": uuid.UUID("01010000-0000-0000-0000-000000000002"), "ord_id": "ORD-2505-1481", "cust_id": "c1010000-0000-0000-0000-000000000002", "source": "Portal", "status": "Draft", "amount": 45320.00, "time_offset": 15},
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
            created_at=datetime.utcnow() - timedelta(minutes=o["time_offset"]),
            status=o["status"]
        )
        db.add(order)
        db.flush()

        db.add(OrderLineItem(
            tenant_id=DEMO_TENANT_ID,
            order_id=order.id,
            product_id=uuid.UUID("a1010000-0000-0000-0000-000000000001"),
            quantity=1,
            unit_price=o["amount"]
        ))

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

        invoice = Invoice(
            tenant_id=DEMO_TENANT_ID,
            order_id=order.id,
            gstin="29AAAAA1111A1Z1",
            total_amount=o["amount"],
            # Demo data — no real IRP integration exists; keep consistent with
            # production behavior so demo mode doesn't imply a capability we don't have.
            irn_status="NOT_APPLICABLE",
            qr_code_status="NOT_APPLICABLE",
            customer_id=order.customer_id,
            payment_status="UNPAID",
            amount_paid=0.0,
            created_at=order.created_at
        )
        db.add(invoice)

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

    ledger_count = db.query(CustomerLedger).count()
    if ledger_count == 0:
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

        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000001"),
            type="CREDIT",
            amount=15000.00,
            reference_id="PAY-REC-9821",
            created_at=datetime.utcnow() - timedelta(hours=5)
        ))
        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000002"),
            type="CREDIT",
            amount=45320.00,
            reference_id="PAY-REC-9822",
            created_at=datetime.utcnow() - timedelta(minutes=15)
        ))

        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000001"),
            type="DEBIT",
            amount=845000.00,
            reference_id="INV-2025-0501",
            created_at=datetime.utcnow() - timedelta(days=5)
        ))
        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000002"),
            type="DEBIT",
            amount=612000.00,
            reference_id="INV-2025-0502",
            created_at=datetime.utcnow() - timedelta(days=20)
        ))
        db.add(CustomerLedger(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            customer_id=uuid.UUID("c1010000-0000-0000-0000-000000000003"),
            type="DEBIT",
            amount=475000.00,
            reference_id="INV-2025-0503",
            created_at=datetime.utcnow() - timedelta(days=40)
        ))
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
