import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.product import Product
from app.models.customer import Customer
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_confirm_order_success(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Orders Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Products with stock_quantity
    p1 = Product(sku_id="PROD-SOAP-1", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    p2 = Product(sku_id="PROD-SOAP-2", brand="HUL", category="Soap", pack_size="200g", base_price=80.0, stock_quantity=50)
    db_session.add_all([p1, p2])
    db_session.flush()

    # 3. Setup Customer
    cust = Customer(
        retailer_name="Aggarwal Kirana", customer_id="C-1", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # 4. Setup Order (currently in Pending/Draft status)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-CONFIRM-TEST-1",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add lines
    db_session.add(OrderLineItem(order_id=order.id, product_id=p1.id, quantity=30, unit_price=45.0))
    db_session.add(OrderLineItem(order_id=order.id, product_id=p2.id, quantity=10, unit_price=80.0))

    # Ledger transition: None -> Draft
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # 5. Call confirmation endpoint
    response = client.put(
        f"/api/v1/orders/{order.id}/status",
        json={"to_status": "Confirmed"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["new_status"] == "Confirmed"

    # 6. Verify database state
    db_session.expire_all()

    # Verify stock decrements
    p1_db = db_session.get(Product, p1.id)
    p2_db = db_session.get(Product, p2.id)
    assert p1_db.stock_quantity == 70  # 100 - 30
    assert p2_db.stock_quantity == 40  # 50 - 10

    # Verify ledger entry
    latest_ledger = db_session.query(OrderStateLedger).filter_by(order_id=order.id).order_by(OrderStateLedger.timestamp.desc()).first()
    assert latest_ledger.to_status == "Confirmed"
    assert latest_ledger.from_status == "Draft"


def test_confirm_order_insufficient_stock(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Orders Test Tenant 2")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product with low stock_quantity (20)
    p = Product(sku_id="PROD-LOW-STOCK", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=20)
    db_session.add(p)
    db_session.flush()

    cust = Customer(
        retailer_name="Aggarwal Kirana", customer_id="C-2", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-CONFIRM-TEST-2",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add line with requested qty (30) which exceeds stock (20)
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=30, unit_price=45.0))
    db_session.commit()

    # Call confirmation endpoint
    response = client.put(
        f"/api/v1/orders/{order.id}/status",
        json={"to_status": "Confirmed"}
    )

    # Assert 400 Bad Request
    assert response.status_code == 400
    assert "Insufficient stock" in response.json()["detail"]

    # Verify stock was NOT decremented (transaction rollback integrity)
    db_session.expire_all()
    p_db = db_session.get(Product, p.id)
    assert p_db.stock_quantity == 20


def test_confirm_order_atomic_rollback(db_session, client):
    tenant = DistributorTenant(name="Orders Test Tenant 3")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup 2 products: p1 has enough stock (100), p2 has insufficient stock (5)
    p1 = Product(sku_id="PROD-OK", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    p2 = Product(sku_id="PROD-NOT-OK", brand="HUL", category="Soap", pack_size="200g", base_price=80.0, stock_quantity=5)
    db_session.add_all([p1, p2])
    db_session.flush()

    cust = Customer(
        retailer_name="Aggarwal Kirana", customer_id="C-3", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-CONFIRM-TEST-3",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add line items: p1 requested qty is valid, p2 requested qty exceeds stock
    db_session.add(OrderLineItem(order_id=order.id, product_id=p1.id, quantity=30, unit_price=45.0))
    db_session.add(OrderLineItem(order_id=order.id, product_id=p2.id, quantity=10, unit_price=80.0))
    db_session.commit()

    # Call confirmation endpoint
    response = client.put(
        f"/api/v1/orders/{order.id}/status",
        json={"to_status": "Confirmed"}
    )

    # Assert 400 Bad Request
    assert response.status_code == 400

    # Verify atomic rollback: p1 stock is NOT decremented (should remain 100)
    db_session.expire_all()
    p1_db = db_session.get(Product, p1.id)
    p2_db = db_session.get(Product, p2.id)
    assert p1_db.stock_quantity == 100
    assert p2_db.stock_quantity == 5


def test_resolve_order_item(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Resolve Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Products
    p_valid = Product(sku_id="PROD-VALID", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    p_unmatched = Product(sku_id="UNMATCHED_SKU", brand="Generic", category="Grocery", pack_size="1 unit", base_price=0.0)
    db_session.add_all([p_valid, p_unmatched])
    db_session.flush()

    # 3. Setup Customer
    cust = Customer(
        retailer_name="Aggarwal Kirana", customer_id="C-4", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # 4. Setup Order (Needs Review status)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-RESOLVE-TEST-1",
        source="WhatsApp",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add unmatched line item
    line_item = OrderLineItem(order_id=order.id, product_id=p_unmatched.id, quantity=10, unit_price=0.0)
    db_session.add(line_item)
    db_session.flush()

    # Ledger transition: None -> Needs Review
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Needs Review", updated_by="system_whatsapp_agent"))
    db_session.commit()

    # 5. Call resolve endpoint
    payload = {
        "sku_code": "PROD-VALID",
        "quantity": 5
    }

    response = client.patch(
        f"/api/v1/orders/items/{line_item.id}/resolve",
        json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["sku_code"] == "PROD-VALID"
    assert data["quantity"] == 5
    assert data["unit_price"] == 45.0
    assert data["order_status"] == "Pending"

    # 6. Verify database state
    db_session.expire_all()
    item_db = db_session.get(OrderLineItem, line_item.id)
    assert item_db.product_id == p_valid.id
    assert item_db.quantity == 5
    assert float(item_db.unit_price) == 45.0

    order_db = db_session.get(Order, order.id)
    assert order_db.current_status == "Draft"  # Maps to Pending


def test_get_order_invoice_success(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Invoice Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-INVOICE", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Invoice Stores", customer_id="C-INV-1", address_text="Invoice Street, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order (Confirmed status)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-INVOICE-TEST-1",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add line item
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=45.0))

    # Ledger transition: None -> Confirmed
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Confirmed", updated_by="admin"))
    db_session.commit()

    # Get PDF invoice
    response = client.get(f"/api/v1/orders/{order.id}/invoice")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=invoice_" in response.headers["content-disposition"]
    assert len(response.content) > 0


def test_get_order_invoice_not_confirmed(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Invoice Test Tenant 2")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-INVOICE-2", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Invoice Stores 2", customer_id="C-INV-2", address_text="Invoice Street 2, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order (Draft status, not Confirmed)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-INVOICE-TEST-2",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add line item
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=45.0))

    # Ledger transition: None -> Draft
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # Attempt to get PDF invoice
    response = client.get(f"/api/v1/orders/{order.id}/invoice")
    assert response.status_code == 400
    assert "Invoices can only be generated for Confirmed orders" in response.json()["detail"]


def test_list_orders(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="List Orders Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-LIST", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="List Customer", customer_id="C-LIST-1", address_text="List Street, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-LIST-TEST-1",
        source="WhatsApp",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add line item
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=5, unit_price=45.0))
    db_session.commit()

    # List orders via API
    response = client.get(f"/api/v1/orders?tenant_id={tenant.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["order_id"] == "ORD-LIST-TEST-1"
    assert data[0]["customer"] == "List Customer"
    assert data[0]["amount"] == 225.0
    assert data[0]["status"] == "Pending"  # Draft maps to Pending

