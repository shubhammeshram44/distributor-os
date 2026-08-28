import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.models.order import Order
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.ledger import CustomerLedger
from app.models.shipment import Shipment
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.services.tenant_service import DEMO_TENANT_ID

client = TestClient(app)

# =====================================================================
# 1. WHATSAPP NLP INGESTION & TRIAGE PIPELINE
# =====================================================================

def test_whatsapp_unmapped_token_creates_needs_review_order(db_session, setup_test_catalog):
    """
    CRITICAL FEAT: Triage Pipeline
    When an unknown token comes through WhatsApp, the system must NOT return 
    an ERR-VAL-404. It must return a 200 OK and create a parent Order 
    with a 'NEEDS_REVIEW' status layout.
    """
    payload = {
        "sender": "+919999888877",
        "message": "Bhaiya, send 5 packs of PatanjaliDantKanti"
    }
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    
    assert response.status_code == 200, "Webhook failed on unmapped token!"
    assert response.json().get("status") == "success"
    
    order = db_session.query(Order).filter(Order.customer_mobile == "+919999888877").first()
    assert order is not None, "Order was not created in the database!"
    assert order.current_status == "Needs Review"


def test_whatsapp_webhook_unwhitelisted_sender(db_session, setup_test_catalog):
    """
    Verifies that webhook requests from unwhitelisted senders log clean 
    and return 200 OK early without creating an order.
    """
    payload = {
        "sender": "+919999000000",
        "message": "Bhaiya, send 5 packs of PatanjaliDantKanti"
    }
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    
    assert response.status_code == 200
    assert response.json().get("status") == "ignored"
    assert "not whitelisted" in response.json().get("message")
    
    # Ensure no order is created for unwhitelisted sender
    order = db_session.query(Order).filter(Order.customer_mobile == "+919999000000").first()
    assert order is None


def test_whatsapp_webhook_decoupled_routing(db_session, setup_test_catalog):
    """
    Verifies smart routing to the correct tenant based on payload.receiver.
    """
    tenant = db_session.query(DistributorTenant).first()
    tenant.whatsapp_order_phone = "+918888888888"
    db_session.commit()
    
    payload = {
        "sender": "+919999888877",
        "receiver": "+918888888888",
        "message": "Bhaiya, send 5 packs of PatanjaliDantKanti"
    }
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    assert response.json().get("status") == "success"


def test_whatsapp_content_duplicate_within_5_minutes_is_skipped(db_session, setup_test_catalog):
    """
    Regression test for WA-2: the spec requires deduplicating orders
    received within 5 minutes from the same customer with identical
    normalized content. Previously only an in-memory, message-ID-keyed
    dedup existed (webhook-retry protection) -- a customer manually
    resending the exact same text (a fresh message ID each time, e.g. a
    retry from their own phone, or a WhatsApp client's own delivery retry
    assigning a new id) created a second, fully independent duplicate order.
    """
    tenant = db_session.query(DistributorTenant).first()
    tenant.whatsapp_order_phone = "+918888888888"
    db_session.commit()

    payload = {
        "sender": "+919999888877",
        "receiver": "+918888888888",
        "message": "Bhaiya, send 5 packs of PatanjaliDantKanti"
    }
    first_response = client.post("/api/v1/whatsapp/webhook", json=payload)
    assert first_response.status_code == 200
    assert first_response.json().get("status") == "success"

    orders_after_first = db_session.query(Order).filter(Order.source == "WhatsApp").count()
    assert orders_after_first == 1

    # Resend the EXACT same content (different casing/whitespace to prove
    # normalization) within the 5-minute window -- must be skipped as a
    # duplicate, not create a second order.
    duplicate_payload = {
        "sender": "+919999888877",
        "receiver": "+918888888888",
        "message": "  Bhaiya,  SEND 5 packs of PatanjaliDantKanti  "
    }
    second_response = client.post("/api/v1/whatsapp/webhook", json=duplicate_payload)
    assert second_response.status_code == 200
    assert second_response.json().get("status") == "duplicate"

    orders_after_second = db_session.query(Order).filter(Order.source == "WhatsApp").count()
    assert orders_after_second == 1, "Resending identical content within 5 minutes must not create a second order"

    # A genuinely DIFFERENT message from the same customer must still go
    # through normally (dedup must not be overly broad).
    different_payload = {
        "sender": "+919999888877",
        "receiver": "+918888888888",
        "message": "Bhaiya, send 20 packs of SurfExcel this time"
    }
    third_response = client.post("/api/v1/whatsapp/webhook", json=different_payload)
    assert third_response.status_code == 200
    assert third_response.json().get("status") == "success"

    orders_after_third = db_session.query(Order).filter(Order.source == "WhatsApp").count()
    assert orders_after_third == 2, "A genuinely different message must not be treated as a duplicate"


# =====================================================================
# 2. THE ORDER JOURNEY (ADDITION, CONFIRMATION, SHIPMENT)
# =====================================================================

def test_order_addition_and_creation(db_session, setup_test_catalog):
    """
    Verifies that structured manual/API order entry correctly adds an order 
    to the system with its initial pending parameters.
    """
    order_payload = {
        "customer_id": 1,
        "items": [
            {"sku_id": "SKU-AASHIRVAAD-AATA", "quantity": 10, "price": 450.00}
        ]
    }
    response = client.post(f"/api/v1/orders/create?tenant_id={DEMO_TENANT_ID}", json=order_payload)
    assert response.status_code == 201
    
    order_id = response.json().get("order_id")
    order = db_session.query(Order).get(order_id)
    assert order is not None
    assert order.total_amount == 4500.00


def test_manually_created_product_gets_inventory_row_and_is_billable(db_session):
    """
    REGRESSION GUARD (payment-blocking bug): products created via
    POST /products (manual "Add Product" form) or CSV bulk import must
    get a matching Inventory row. Without it, order_confirmation_service
    treats the SKU as having 0 stock, silently allocating 0 units and
    zeroing the invoice for any order placed against it.
    """
    tenant = DistributorTenant(name="Inventory Regression Tenant")
    db_session.add(tenant)
    db_session.commit()

    payload = {
        "sku_id": "SKU-NEW-PRODUCT-001",
        "brand": "TestBrand",
        "category": "Snacks",
        "pack_size": "200g",
        "base_price": 99.0
    }
    response = client.post(f"/api/v1/products?tenant_id={tenant.id}", json=payload)
    assert response.status_code == 201

    product = db_session.query(Product).filter_by(sku_id="SKU-NEW-PRODUCT-001").first()
    assert product is not None

    inv = db_session.query(Inventory).filter(Inventory.sku_id == product.id).first()
    assert inv is not None, "Product created via POST /products must get a matching Inventory row"
    assert inv.quantity_on_hand == 100  # matches Product.stock_quantity default


def test_order_create_fallback_product_gets_valid_uuid_and_inventory(db_session, setup_test_catalog):
    """
    REGRESSION GUARD: the /orders/create fallback path (for SKUs with no
    existing Product row) must generate a real UUID for Product.id, not
    reuse the raw SKU string (which crashes on Postgres, a UUID column),
    and must create a matching Inventory row so the order is billable.
    """
    order_payload = {
        "customer_id": 1,
        "items": [
            {"sku_id": "SKU-BRAND-NEW-UNMAPPED", "quantity": 3, "price": 150.00}
        ]
    }
    response = client.post(f"/api/v1/orders/create?tenant_id={DEMO_TENANT_ID}", json=order_payload)
    assert response.status_code == 201

    order_id = response.json().get("order_id")
    order = db_session.query(Order).get(order_id)
    assert order is not None
    assert order.total_amount == 450.00

    product = db_session.query(Product).filter_by(sku_id="SKU-BRAND-NEW-UNMAPPED").first()
    assert product is not None
    assert isinstance(product.id, uuid.UUID)

    inv = db_session.query(Inventory).filter(Inventory.sku_id == product.id).first()
    assert inv is not None
    assert inv.quantity_on_hand >= 3


def test_order_confirmation_workflow(db_session, setup_pending_order):
    """
    Verifies transitioning an order from 'Pending' to 'Confirmed', ensuring
    the transition registers cleanly in the order state ledger.
    """
    order_id = setup_pending_order.id
    response = client.post(f"/api/v1/orders/{order_id}/confirm")
    assert response.status_code == 200
    
    db_session.refresh(setup_pending_order)
    assert setup_pending_order.current_status == "Confirmed"


def test_order_shipment_generation_and_tracking(db_session, setup_confirmed_order):
    """
    Verifies that confirming/processing an order for delivery generates a 
    corresponding Shipment record tracking its logistics state.
    """
    order_id = setup_confirmed_order.id
    shipment_payload = {
        "delivery_partner": "Local Logistics",
        "vehicle_number": "KA-03-EX-1234"
    }
    response = client.post(f"/api/v1/orders/{order_id}/dispatch", json=shipment_payload)
    assert response.status_code == 200
    
    shipment = db_session.query(Shipment).filter(Shipment.order_id == order_id).first()
    assert shipment is not None
    assert shipment.status == "DISPATCHED"


# =====================================================================
# 3. INVENTORY MANAGEMENT (ADDITION & DASHBOARD GRID)
# =====================================================================

def test_inventory_stock_inward_addition(db_session, setup_test_catalog):
    """
    Verifies that dynamic stock inward actions properly increment physical stock
    counts and associate correctly with the item's sku_id.
    """
    inward_payload = {
        "sku_id": "SKU-AASHIRVAAD-AATA",
        "quantity_added": 50,
        "warehouse_location": "Bay-A1"
    }
    response = client.post(f"/api/v1/inventory/inward?tenant_id={DEMO_TENANT_ID}", json=inward_payload)
    assert response.status_code == 200
    
    product = db_session.query(Product).filter_by(sku_id="SKU-AASHIRVAAD-AATA").first()
    inv = db_session.query(Inventory).filter(Inventory.sku_id == product.id).first()
    assert inv.physical_stock >= 50


def test_inventory_grid_includes_zero_stock_items(db_session, setup_empty_catalog_item):
    """
    CRITICAL FEAT: Outer Join Bugfix
    Catalog items with 0 physical stock must still show up on the frontend
    inventory panel instead of being dropped by strict INNER JOINs.
    """
    response = client.get(f"/api/v1/inventory/dashboard-grid?tenant_id={DEMO_TENANT_ID}")
    assert response.status_code == 200
    
    items = response.json().get("data", [])
    zero_stock_item_exists = any(item["sku_code"] == "ZERO_STOCK_SKU" for item in items)
    assert zero_stock_item_exists, "Regression! Items with 0 stock are being hidden from the catalog panel."


# =====================================================================
# 4. PAYMENT PROCESS & FIFO RECONCILIATION
# =====================================================================

def test_payment_voucher_logging(db_session, setup_test_catalog):
    """
    Verifies receiving a direct payment logs a voucher entry under the 
    customer's account ledger.
    """
    customer = db_session.query(Customer).first()
    payload = {
        "customer_id": str(customer.id),
        "amount": 2000.00,
        "payment_mode": "Cash"
    }
    response = client.post(f"/api/v1/payments/voucher?tenant_id={DEMO_TENANT_ID}", json=payload)
    assert response.status_code == 201

    ledger_entry = db_session.query(CustomerLedger).filter(
        CustomerLedger.customer_id == customer.id
    ).order_by(CustomerLedger.id.desc()).first()
    assert ledger_entry is not None
    assert ledger_entry.credit == 2000.00


def test_fifo_payment_cascade(db_session, setup_unpaid_orders):
    """
    CRITICAL FEAT: FIFO Cascade
    When a customer pays an amount, it must systematically close out older
    outstanding invoices/orders in a First-In, First-Out sequence, avoiding 
    permanently un-synced 'Unpaid' statuses.
    """
    customer_id = setup_unpaid_orders["customer_id"]
    order_1_id = setup_unpaid_orders["order_1_id"] # Due: 500
    order_2_id = setup_unpaid_orders["order_2_id"] # Due: 1000
    
    payment_payload = {
        "customer_id": customer_id,
        "amount": 700.00,
        "payment_mode": "UPI"
    }
    response = client.post(f"/api/v1/payments/collect?tenant_id={DEMO_TENANT_ID}", json=payment_payload)
    assert response.status_code == 200
    
    order_1 = db_session.query(Order).get(order_1_id)
    assert order_1.payment_status == "PAID"
    
    order_2 = db_session.query(Order).get(order_2_id)
    assert order_2.payment_status == "PARTIALLY_PAID"


def test_partial_allocation_on_batch_confirm(db_session, setup_test_catalog):
    """
    Verifies that calling POST /orders/{id}/batch-confirm correctly:
    - Sets allocated_quantity == 125 on the line item
    - Reduces inventory.quantity_on_hand to 0
    - Creates a DemandGap with gap_qty == 775
    - Creates an Invoice with total_amount == 125 * unit_price (1250)
    - Sets order.total_amount == 125 * unit_price (1250)
    """
    from app.models.product import Product
    from app.models.inventory import Inventory
    from app.models.order import OrderLineItem, OrderStateLedger
    from app.models.demand_gap import DemandGap
    from app.models.invoice import Invoice
    from app.models.customer import Customer
    import uuid

    # 1. Fetch catalog setups
    tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    cust = db_session.query(Customer).filter_by(tenant_id=tenant_id).first()
    assert cust is not None

    # 2. Create product with 125 units in inventory
    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        sku_id="PROD-BATCH-1",
        brand="HUL",
        category="Soap",
        pack_size="1 unit",
        base_price=10.0,
        stock_quantity=125
    )
    db_session.add(product)
    db_session.flush()

    inv = Inventory(
        tenant_id=tenant_id,
        sku_id=product.id,
        location="WH1",
        quantity_on_hand=125,
        low_stock_threshold=10
    )
    db_session.add(inv)
    db_session.flush()

    # 3. Create order for 900 units
    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        internal_order_id="ORD-BATCH-TEST-1",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderStateLedger(
        tenant_id=tenant_id,
        order_id=order.id,
        from_status=None,
        to_status="Draft",
        updated_by="test"
    ))
    db_session.add(OrderLineItem(
        tenant_id=tenant_id,
        order_id=order.id,
        product_id=product.id,
        quantity=900,
        unit_price=10.0
    ))
    db_session.commit()

    # 4. Call batch-confirm API
    response = client.post(
        f"/api/v1/orders/{order.id}/batch-confirm",
        json={"resolved_items": []}
    )
    assert response.status_code == 200

    # 5. Verify assertions
    db_session.expire_all()
    
    # - allocated_quantity == 125 on the line item
    item_db = db_session.query(OrderLineItem).filter_by(order_id=order.id).one()
    assert item_db.allocated_quantity == 125

    # - inventory.quantity_on_hand == 125, quantity_committed == 125
    inv_db = db_session.query(Inventory).filter_by(sku_id=product.id).one()
    assert inv_db.quantity_on_hand == 0
    assert inv_db.quantity_committed == 125

    # - DemandGap exists with gap_qty == 775
    gap_db = db_session.query(DemandGap).filter_by(order_id=order.id).one()
    assert gap_db.gap_qty == 775
    assert float(gap_db.revenue_at_risk) == 7750.0

    # - Invoice total_amount == 125 * unit_price (1250)
    invoice_db = db_session.query(Invoice).filter_by(order_id=order.id).one()
    assert float(invoice_db.total_amount) == 1250.0

    # - order.total_amount == 125 * unit_price (1250)
    order_db = db_session.query(Order).filter_by(id=order.id).one()
    assert order_db.total_amount == 1250.0


def test_partial_allocation_on_confirm_order_post(db_session, setup_test_catalog):
    """
    Verifies that calling POST /orders/{id}/confirm correctly:
    - Sets allocated_quantity == 125 on the line item
    - Reduces inventory.quantity_on_hand to 0
    - Creates a DemandGap with gap_qty == 775
    - Creates an Invoice with total_amount == 1250
    - Sets order.total_amount == 1250
    """
    from app.models.product import Product
    from app.models.inventory import Inventory
    from app.models.order import OrderLineItem, OrderStateLedger
    from app.models.demand_gap import DemandGap
    from app.models.invoice import Invoice
    from app.models.customer import Customer
    import uuid

    tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    cust = db_session.query(Customer).filter_by(tenant_id=tenant_id).first()
    assert cust is not None

    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        sku_id="PROD-POSTCONF-1",
        brand="HUL",
        category="Soap",
        pack_size="1 unit",
        base_price=10.0,
        stock_quantity=125
    )
    db_session.add(product)
    db_session.flush()

    inv = Inventory(
        tenant_id=tenant_id,
        sku_id=product.id,
        location="WH1",
        quantity_on_hand=125,
        low_stock_threshold=10
    )
    db_session.add(inv)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        internal_order_id="ORD-POSTCONF-TEST-1",
        source="API",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderStateLedger(
        tenant_id=tenant_id,
        order_id=order.id,
        from_status=None,
        to_status="Draft",
        updated_by="API"
    ))
    db_session.add(OrderLineItem(
        tenant_id=tenant_id,
        order_id=order.id,
        product_id=product.id,
        quantity=900,
        unit_price=10.0
    ))
    db_session.commit()

    response = client.post(f"/api/v1/orders/{order.id}/confirm")
    assert response.status_code == 200

    db_session.expire_all()
    item_db = db_session.query(OrderLineItem).filter_by(order_id=order.id).one()
    assert item_db.allocated_quantity == 125

    inv_db = db_session.query(Inventory).filter_by(sku_id=product.id).one()
    assert inv_db.quantity_on_hand == 0
    assert inv_db.quantity_committed == 125

    gap_db = db_session.query(DemandGap).filter_by(order_id=order.id).one()
    assert gap_db.gap_qty == 775

    invoice_db = db_session.query(Invoice).filter_by(order_id=order.id).one()
    assert float(invoice_db.total_amount) == 1250.0

    order_db = db_session.query(Order).filter_by(id=order.id).one()
    assert order_db.total_amount == 1250.0


def test_partial_allocation_on_create_order_confirm_on_create(db_session, setup_test_catalog):
    """
    Verifies that calling POST /orders with status="Confirmed" correctly:
    - Sets allocated_quantity == 125 on the line item
    - Reduces inventory.quantity_on_hand to 0
    - Creates a DemandGap with gap_qty == 775
    - Creates an Invoice with total_amount == 1250
    - Sets order.total_amount == 1250
    """
    from app.models.product import Product
    from app.models.inventory import Inventory
    from app.models.order import OrderLineItem
    from app.models.demand_gap import DemandGap
    from app.models.invoice import Invoice
    from app.models.customer import Customer
    import uuid

    tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    cust = db_session.query(Customer).filter_by(tenant_id=tenant_id).first()
    assert cust is not None

    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        sku_id="PROD-CREAT-1",
        brand="HUL",
        category="Soap",
        pack_size="1 unit",
        base_price=10.0,
        stock_quantity=125
    )
    db_session.add(product)
    db_session.flush()

    inv = Inventory(
        tenant_id=tenant_id,
        sku_id=product.id,
        location="WH1",
        quantity_on_hand=125,
        low_stock_threshold=10
    )
    db_session.add(inv)
    db_session.commit()

    payload = {
        "tenant_id": str(tenant_id),
        "customer_id": str(cust.id),
        "source": "Portal",
        "status": "Confirmed",
        "items": [
            {
                "sku_id": "PROD-CREAT-1",
                "quantity": 900,
                "unit_price": 10.0
            }
        ]
    }
    response = client.post("/api/v1/orders", json=payload)
    assert response.status_code == 201
    order_id = uuid.UUID(response.json()["order_id"])

    db_session.expire_all()
    item_db = db_session.query(OrderLineItem).filter_by(order_id=order_id).one()
    assert item_db.allocated_quantity == 125

    inv_db = db_session.query(Inventory).filter_by(sku_id=product.id).one()
    assert inv_db.quantity_on_hand == 0
    assert inv_db.quantity_committed == 125

    gap_db = db_session.query(DemandGap).filter_by(order_id=order_id).one()
    assert gap_db.gap_qty == 775

    invoice_db = db_session.query(Invoice).filter_by(order_id=order_id).one()
    assert float(invoice_db.total_amount) == 1250.0

    order_db = db_session.query(Order).filter_by(id=order_id).one()
    assert order_db.total_amount == 1250.0


def test_credit_limit_on_batch_confirm(db_session, setup_test_catalog):
    """
    Verifies that calling POST /orders/{id}/batch-confirm when customer combined balance
    exceeds credit limit returns 400 and logs a CREDIT_LIMIT DemandGap row.
    """
    from app.models.product import Product
    from app.models.inventory import Inventory
    from app.models.order import OrderLineItem, OrderStateLedger
    from app.models.demand_gap import DemandGap
    from app.models.customer import Customer
    import uuid

    tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    cust = db_session.query(Customer).filter_by(tenant_id=tenant_id).first()
    assert cust is not None

    cust.credit_limit = 100.0  # Set low credit limit
    cust.outstanding_balance = 0.0
    db_session.commit()

    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        sku_id="PROD-CRED-BC",
        brand="HUL",
        category="Soap",
        pack_size="1 unit",
        base_price=10.0,
        stock_quantity=125
    )
    db_session.add(product)
    db_session.flush()

    inv = Inventory(
        tenant_id=tenant_id,
        sku_id=product.id,
        location="WH1",
        quantity_on_hand=125,
        low_stock_threshold=10
    )
    db_session.add(inv)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        internal_order_id="ORD-CRED-BC",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderStateLedger(
        tenant_id=tenant_id,
        order_id=order.id,
        from_status=None,
        to_status="Draft",
        updated_by="test"
    ))
    db_session.add(OrderLineItem(
        tenant_id=tenant_id,
        order_id=order.id,
        product_id=product.id,
        quantity=50,  # total is 500, limit is 100
        unit_price=10.0
    ))
    db_session.commit()

    response = client.post(
        f"/api/v1/orders/{order.id}/batch-confirm",
        json={"resolved_items": []}
    )
    assert response.status_code == 400
    assert "Credit limit exceeded" in response.json()["detail"]

    # Verify a CREDIT_LIMIT DemandGap exists
    gap_db = db_session.query(DemandGap).filter_by(order_id=order.id).one()
    assert gap_db.reason_code == "CREDIT_LIMIT"
    assert float(gap_db.revenue_at_risk) == 500.0


def test_credit_limit_on_confirm_order_post(db_session, setup_test_catalog):
    """
    Verifies that calling POST /orders/{id}/confirm when customer combined balance
    exceeds credit limit returns 400 and logs a CREDIT_LIMIT DemandGap row.
    """
    from app.models.product import Product
    from app.models.inventory import Inventory
    from app.models.order import OrderLineItem, OrderStateLedger
    from app.models.demand_gap import DemandGap
    from app.models.customer import Customer
    import uuid

    tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    cust = db_session.query(Customer).filter_by(tenant_id=tenant_id).first()
    assert cust is not None

    cust.credit_limit = 100.0  # Set low credit limit
    cust.outstanding_balance = 0.0
    db_session.commit()

    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        sku_id="PROD-CRED-CONF",
        brand="HUL",
        category="Soap",
        pack_size="1 unit",
        base_price=10.0,
        stock_quantity=125
    )
    db_session.add(product)
    db_session.flush()

    inv = Inventory(
        tenant_id=tenant_id,
        sku_id=product.id,
        location="WH1",
        quantity_on_hand=125,
        low_stock_threshold=10
    )
    db_session.add(inv)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        internal_order_id="ORD-CRED-CONF",
        source="API",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderStateLedger(
        tenant_id=tenant_id,
        order_id=order.id,
        from_status=None,
        to_status="Draft",
        updated_by="API"
    ))
    db_session.add(OrderLineItem(
        tenant_id=tenant_id,
        order_id=order.id,
        product_id=product.id,
        quantity=50,  # total is 500, limit is 100
        unit_price=10.0
    ))
    db_session.commit()

    response = client.post(f"/api/v1/orders/{order.id}/confirm")
    assert response.status_code == 400
    assert "Credit limit exceeded" in response.json()["detail"]

    # Verify a CREDIT_LIMIT DemandGap exists
    gap_db = db_session.query(DemandGap).filter_by(order_id=order.id).one()
    assert gap_db.reason_code == "CREDIT_LIMIT"
    assert float(gap_db.revenue_at_risk) == 500.0



def test_inventory_inward_rejects_wrong_tenant_and_requires_tenant_id(db_session, setup_test_catalog):
    """
    Regression test for TENANT-4: inward_stock previously resolved 'the
    tenant' via db.query(DistributorTenant).first() -- an arbitrary row,
    ignoring the caller's actual identity. In a real multi-tenant
    deployment, this silently wrote every stock-inward request against
    whichever tenant happened to be first in the table. Now requires an
    explicit, resolvable tenant_id.
    """
    inward_payload = {
        "sku_id": "SKU-AASHIRVAAD-AATA",
        "quantity_added": 5,
        "warehouse_location": "Bay-Z9"
    }
    # No tenant_id at all -> rejected, not silently applied to an arbitrary tenant.
    response = client.post("/api/v1/inventory/inward", json=inward_payload)
    assert response.status_code == 401


def test_inventory_dashboard_grid_requires_tenant_id(db_session, setup_test_catalog):
    """Regression test for TENANT-4 on get_inventory_dashboard_grid."""
    response = client.get("/api/v1/inventory/dashboard-grid")
    assert response.status_code == 401


def test_payments_voucher_requires_tenant_id(db_session, setup_test_catalog):
    """Regression test for TENANT-4 on record_voucher."""
    customer = db_session.query(Customer).first()
    payload = {"customer_id": str(customer.id), "amount": 100.00, "payment_mode": "Cash"}
    response = client.post("/api/v1/payments/voucher", json=payload)
    assert response.status_code == 401


def test_payments_collect_requires_tenant_id(db_session, setup_test_catalog):
    """Regression test for TENANT-4 on collect_payment."""
    customer = db_session.query(Customer).first()
    payload = {"customer_id": str(customer.id), "amount": 100.00, "payment_mode": "UPI"}
    response = client.post("/api/v1/payments/collect", json=payload)
    assert response.status_code == 401


def test_orders_create_requires_tenant_id(db_session, setup_test_catalog):
    """Regression test for TENANT-4 on create_order_generic."""
    order_payload = {
        "customer_id": 1,
        "items": [{"sku_id": "SKU-AASHIRVAAD-AATA", "quantity": 1, "price": 450.00}]
    }
    response = client.post("/api/v1/orders/create", json=order_payload)
    assert response.status_code == 401


def test_payments_voucher_updates_outstanding_balance(db_session, setup_test_catalog):
    """
    Regression test for PAY-2: record_voucher previously inserted a
    CustomerLedger row directly instead of going through record_transaction(),
    leaving customer.outstanding_balance permanently stale.
    """
    customer = db_session.query(Customer).first()
    # Give the customer a real existing DEBIT balance first -- without this,
    # a fresh customer starts at 0.0, and outstanding_balance is floored at
    # 0.0 either way (with or without the fix), which would mask the bug
    # this test exists to catch.
    from app.services.ledger_service import record_transaction
    record_transaction(
        db=db_session, tenant_id=customer.tenant_id, customer_id=customer.id,
        type="DEBIT", amount=2000.0, reference_id="PRE-EXISTING-DEBIT",
        description="Pre-existing balance for PAY-2 regression test"
    )
    db_session.commit()
    db_session.refresh(customer)
    balance_before = float(customer.outstanding_balance or 0.0)
    assert balance_before == 2000.0

    payload = {"customer_id": str(customer.id), "amount": 500.00, "payment_mode": "Cash"}
    response = client.post(f"/api/v1/payments/voucher?tenant_id={DEMO_TENANT_ID}", json=payload)
    assert response.status_code == 201

    db_session.expire_all()
    db_session.refresh(customer)
    # A CREDIT voucher reduces outstanding balance.
    assert float(customer.outstanding_balance) == balance_before - 500.00


def test_payments_collect_updates_outstanding_balance(db_session, setup_unpaid_orders):
    """
    Regression test for PAY-2: collect_payment previously inserted a
    CustomerLedger row directly instead of going through record_transaction(),
    leaving customer.outstanding_balance permanently stale.
    """
    from app.models.customer import Customer as CustomerModel
    customer_id = setup_unpaid_orders["customer_id"]
    customer = db_session.get(CustomerModel, customer_id)
    balance_before = float(customer.outstanding_balance or 0.0)

    payload = {"customer_id": str(customer_id), "amount": 300.00, "payment_mode": "UPI"}
    response = client.post(f"/api/v1/payments/collect?tenant_id={DEMO_TENANT_ID}", json=payload)
    assert response.status_code == 200

    db_session.expire_all()
    customer_after = db_session.get(CustomerModel, customer_id)
    assert float(customer_after.outstanding_balance) == max(0.0, balance_before - 300.00)
