import pytest
import uuid
import os
os.environ.setdefault("ENCRYPTION_KEY", "u-F_l4aA83_3-xOQ221eT7XW1bT4oI7YvN0bM9L_Rws=")
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, tenant_context, get_db

# Register all models
from app.models.tenant import DistributorTenant
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.inventory import Inventory
from app.models.ledger import CustomerLedger
from app.models.invoice import Invoice

@pytest.fixture(name="db_engine")
def fixture_db_engine():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        engine = create_engine(database_url)
        # Make sure the schema exists (usually already applied via Alembic in
        # CI, but this is a harmless no-op in that case) and reset all data
        # before each test. Without this, tests share state through the same
        # real database and fail/pass depending on run order (unlike the
        # sqlite:///:memory: branch below, which gets a brand-new empty
        # engine per test automatically).
        Base.metadata.create_all(bind=engine, checkfirst=True)
        with engine.begin() as connection:
            table_names = [t.name for t in reversed(Base.metadata.sorted_tables)]
            if table_names:
                quoted = ", ".join(f'"{name}"' for name in table_names)
                connection.exec_driver_sql(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
        yield engine
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="db_session")
def fixture_db_session(db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()
    # Reset tenant context
    tenant_context.set(None)

@pytest.fixture(autouse=True)
def reset_webhook_dedup_cache():
    """The WhatsApp webhook keeps a module-level set of processed Evolution API
    message IDs to dedupe retries. Clear it between tests so reused ids (e.g.
    'wamid.123') in different tests don't leak across and look like duplicates."""
    from app.api.v1 import whatsapp as _wa
    _wa._PROCESSED_MSG_IDS.clear()
    yield
    _wa._PROCESSED_MSG_IDS.clear()

@pytest.fixture
def seed_demo_data(db_session):
    """Opt-in fixture: seeds the demo tenant, customers, products, orders.
    Use in tests that rely on the standard demo dataset (e.g. dashboard)."""
    from app.services.demo_service import ensure_demo_data
    from app.services.tenant_service import DEMO_TENANT_ID
    ensure_demo_data(db_session, DEMO_TENANT_ID)
    return DEMO_TENANT_ID

@pytest.fixture(autouse=True)
def override_get_db(db_session):
    from app.main import app
    def _override():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def setup_test_catalog(db_session):
    # Create Tenant
    tenant = DistributorTenant(id=uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"), name="Demo Tenant")
    db_session.add(tenant)
    db_session.flush()

    # Create Customer with ID matching string "1" (test uses customer_id: 1)
    cust = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        customer_id="CUST-1",
        retailer_name="Kaveri Provision Store",
        address_text="Bengaluru",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days",
        credit_limit=100000.0,
        outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()

    cust_alias = CustomerAlias(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        customer_id=cust.id,
        alias_value="+919999888877"
    )
    db_session.add(cust_alias)
    db_session.flush()

    # Create Product with SKU matching "SKU-AASHIRVAAD-AATA"
    prod = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="SKU-AASHIRVAAD-AATA",
        brand="Generic",
        category="Grocery",
        pack_size="1 unit",
        base_price=450.00
    )
    db_session.add(prod)
    db_session.commit()

@pytest.fixture
def setup_pending_order(db_session):
    tenant = db_session.query(DistributorTenant).first()
    if not tenant:
        tenant = DistributorTenant(id=uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"), name="Demo Tenant")
        db_session.add(tenant)
        db_session.flush()

    customer = db_session.query(Customer).first()
    if not customer:
        customer = Customer(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            customer_id="CUST-1",
            retailer_name="Kaveri Provision Store",
            address_text="Bengaluru",
            gstin="29AAAAA1111A1Z1",
            tax_group="GST-18",
            payment_terms="0-15 Days",
            credit_limit=100000.0,
            outstanding_balance=0.0
        )
        db_session.add(customer)
        db_session.flush()

    prod = db_session.query(Product).filter_by(sku_id="SKU-AASHIRVAAD-AATA").first()
    if not prod:
        prod = Product(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            sku_id="SKU-AASHIRVAAD-AATA",
            brand="Generic",
            category="Grocery",
            pack_size="1 unit",
            base_price=450.00
        )
        db_session.add(prod)
        db_session.flush()

    inv = db_session.query(Inventory).filter_by(sku_id=prod.id).first()
    if not inv:
        inv = Inventory(
            tenant_id=tenant.id,
            sku_id=prod.id,
            location="Bay-A1",
            quantity_on_hand=100,
            quantity_committed=0,
            low_stock_threshold=10
        )
        db_session.add(inv)
        db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        internal_order_id=f"ORD-2506-{uuid.uuid4().hex[:4].upper()}",
        source="Portal",
        customer_id=customer.id,
        created_at=datetime.utcnow()
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderLineItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order.id,
        product_id=prod.id,
        quantity=10,
        unit_price=450.00
    ))

    db_session.add(OrderStateLedger(
        tenant_id=tenant.id,
        order_id=order.id,
        from_status=None,
        to_status="Draft",
        updated_by="API"
    ))
    db_session.commit()
    return order

@pytest.fixture
def setup_confirmed_order(db_session, setup_pending_order):
    order = setup_pending_order
    db_session.add(OrderStateLedger(
        tenant_id=order.tenant_id,
        order_id=order.id,
        from_status="Draft",
        to_status="Confirmed",
        updated_by="API"
    ))
    
    customer = db_session.get(Customer, order.customer_id)
    current_order_total = sum(float(item.quantity * item.unit_price) for item in order.line_items)
    customer.outstanding_balance = float(customer.outstanding_balance) + current_order_total
    db_session.add(CustomerLedger(
        id=uuid.uuid4(),
        tenant_id=order.tenant_id,
        customer_id=order.customer_id,
        type="DEBIT",
        amount=current_order_total,
        reference_id=order.internal_order_id
    ))
    
    invoice = Invoice(
        tenant_id=order.tenant_id,
        order_id=order.id,
        gstin=customer.gstin if customer.gstin else "29AAAAA1111A1Z1",
        total_amount=current_order_total,
        irn_status="Cleared",
        qr_code_status="Generated",
        customer_id=order.customer_id,
        payment_status="UNPAID",
        amount_paid=0.0,
        created_at=datetime.utcnow()
    )
    db_session.add(invoice)
    
    db_session.commit()
    return order

@pytest.fixture
def setup_empty_catalog_item(db_session):
    tenant = db_session.query(DistributorTenant).first()
    if not tenant:
        tenant = DistributorTenant(id=uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"), name="Demo Tenant")
        db_session.add(tenant)
        db_session.flush()

    prod = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="ZERO_STOCK_SKU",
        brand="Generic",
        category="Grocery",
        pack_size="1 unit",
        base_price=10.00
    )
    db_session.add(prod)
    db_session.flush()
    
    inv = Inventory(
        tenant_id=tenant.id,
        sku_id=prod.id,
        location="Bay-A2",
        quantity_on_hand=0,
        quantity_committed=0,
        low_stock_threshold=10
    )
    db_session.add(inv)
    db_session.commit()

@pytest.fixture
def setup_unpaid_orders(db_session):
    tenant = db_session.query(DistributorTenant).first()
    if not tenant:
        tenant = DistributorTenant(id=uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"), name="Demo Tenant")
        db_session.add(tenant)
        db_session.flush()

    cust = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        customer_id="CUST-FIFO",
        retailer_name="FIFO Kirana Store",
        address_text="Bengaluru",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days",
        credit_limit=100000.0,
        outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()

    prod = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="SKU-FIFO-ITEM",
        brand="Generic",
        category="Grocery",
        pack_size="1 unit",
        base_price=1.00
    )
    db_session.add(prod)
    db_session.flush()

    inv = Inventory(
        tenant_id=tenant.id,
        sku_id=prod.id,
        location="Bay-A1",
        quantity_on_hand=10000,
        quantity_committed=0,
        low_stock_threshold=10
    )
    db_session.add(inv)
    db_session.flush()

    order_1 = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        internal_order_id="ORD-FIFO-1",
        source="Portal",
        customer_id=cust.id,
        created_at=datetime.utcnow() - timedelta(days=2)
    )
    db_session.add(order_1)
    db_session.flush()

    db_session.add(OrderLineItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order_1.id,
        product_id=prod.id,
        quantity=500,
        unit_price=1.00
    ))

    db_session.add(OrderStateLedger(
        tenant_id=tenant.id,
        order_id=order_1.id,
        from_status=None,
        to_status="Confirmed",
        updated_by="API",
        timestamp=datetime.utcnow() - timedelta(days=2)
    ))

    order_2 = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        internal_order_id="ORD-FIFO-2",
        source="Portal",
        customer_id=cust.id,
        created_at=datetime.utcnow() - timedelta(days=1)
    )
    db_session.add(order_2)
    db_session.flush()

    db_session.add(OrderLineItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order_2.id,
        product_id=prod.id,
        quantity=1000,
        unit_price=1.00
    ))

    db_session.add(OrderStateLedger(
        tenant_id=tenant.id,
        order_id=order_2.id,
        from_status=None,
        to_status="Confirmed",
        updated_by="API",
        timestamp=datetime.utcnow() - timedelta(days=1)
    ))

    cust.outstanding_balance = 1500.0
    db_session.add(CustomerLedger(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        customer_id=cust.id,
        type="DEBIT",
        amount=500.0,
        reference_id=order_1.internal_order_id,
        created_at=datetime.utcnow() - timedelta(days=2)
    ))
    db_session.add(CustomerLedger(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        customer_id=cust.id,
        type="DEBIT",
        amount=1000.0,
        reference_id=order_2.internal_order_id,
        created_at=datetime.utcnow() - timedelta(days=1)
    ))

    inv1 = Invoice(
        tenant_id=tenant.id,
        order_id=order_1.id,
        gstin="29AAAAA1111A1Z1",
        total_amount=500.0,
        irn_status="Cleared",
        qr_code_status="Generated",
        customer_id=cust.id,
        payment_status="UNPAID",
        amount_paid=0.0,
        created_at=datetime.utcnow() - timedelta(days=2)
    )
    inv2 = Invoice(
        tenant_id=tenant.id,
        order_id=order_2.id,
        gstin="29AAAAA1111A1Z1",
        total_amount=1000.0,
        irn_status="Cleared",
        qr_code_status="Generated",
        customer_id=cust.id,
        payment_status="UNPAID",
        amount_paid=0.0,
        created_at=datetime.utcnow() - timedelta(days=1)
    )
    db_session.add_all([inv1, inv2])
    db_session.commit()

    return {
        "customer_id": str(cust.id),
        "order_1_id": str(order_1.id),
        "order_2_id": str(order_2.id)
    }

