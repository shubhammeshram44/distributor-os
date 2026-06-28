import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.product import Product, ProductAlias
from app.models.customer import Customer
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.inventory import Inventory
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

    # 2. Setup Products with stock_quantity and Inventory
    p1 = Product(sku_id="PROD-SOAP-1", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    p2 = Product(sku_id="PROD-SOAP-2", brand="HUL", category="Soap", pack_size="200g", base_price=80.0, stock_quantity=50)
    db_session.add_all([p1, p2])
    db_session.flush()

    inv1 = Inventory(tenant_id=tenant.id, sku_id=p1.id, location="Loc1", quantity_on_hand=100, low_stock_threshold=10)
    inv2 = Inventory(tenant_id=tenant.id, sku_id=p2.id, location="Loc2", quantity_on_hand=50, low_stock_threshold=10)
    db_session.add_all([inv1, inv2])
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

    # Verify stock decrements in Inventory
    inv1_db = db_session.query(Inventory).filter_by(sku_id=p1.id).one()
    inv2_db = db_session.query(Inventory).filter_by(sku_id=p2.id).one()
    assert inv1_db.quantity_on_hand == 70  # 100 - 30
    assert inv2_db.quantity_on_hand == 40  # 50 - 10

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

    # Setup Product with low stock_quantity (20) and Inventory
    p = Product(sku_id="PROD-LOW-STOCK", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=20)
    db_session.add(p)
    db_session.flush()

    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=20, low_stock_threshold=10)
    db_session.add(inv)
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
    assert "Insufficient stock" in response.json()["detail"] or "Insufficient physical stock" in response.json()["detail"]

    # Verify stock was NOT decremented (transaction rollback integrity)
    db_session.expire_all()
    inv_db = db_session.query(Inventory).filter_by(sku_id=p.id).one()
    assert inv_db.quantity_on_hand == 20


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

    inv1 = Inventory(tenant_id=tenant.id, sku_id=p1.id, location="Loc1", quantity_on_hand=100, low_stock_threshold=10)
    inv2 = Inventory(tenant_id=tenant.id, sku_id=p2.id, location="Loc2", quantity_on_hand=5, low_stock_threshold=10)
    db_session.add_all([inv1, inv2])
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
    inv1_db = db_session.query(Inventory).filter_by(sku_id=p1.id).one()
    inv2_db = db_session.query(Inventory).filter_by(sku_id=p2.id).one()
    assert inv1_db.quantity_on_hand == 100
    assert inv2_db.quantity_on_hand == 5


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


def test_credit_limit_guardrail_success_and_failure(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Credit Limit Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-CREDIT", brand="HUL", category="Soap", pack_size="100g", base_price=500.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=100, low_stock_threshold=10)
    db_session.add(inv)
    db_session.flush()

    # Setup Customer with structural credit_limit of 5,000.0
    cust = Customer(
        retailer_name="Credit Test Shop", customer_id="C-CREDIT-1", address_text="Credit Street, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=5000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order 1: Total amount = 5 * 500 = 2,500.0
    order1 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-CREDIT-TEST-1",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order1)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order1.id, product_id=p.id, quantity=5, unit_price=500.0))
    db_session.add(OrderStateLedger(order_id=order1.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # Confirm Order 1 (2,500 <= 5,000) -> Should pass
    response = client.put(f"/api/v1/orders/{order1.id}/status", json={"to_status": "Confirmed"})
    assert response.status_code == 200
    db_session.expire_all()
    cust_db = db_session.get(Customer, cust.id)
    assert float(cust_db.outstanding_balance) == 2500.0

    # Setup Order 2: Total amount = 6 * 500 = 3,000.0
    # Combined with Order 1 (2,500) = 5,500.0 which exceeds 5,000.0 credit limit!
    order2 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-CREDIT-TEST-2",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order2)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order2.id, product_id=p.id, quantity=6, unit_price=500.0))
    db_session.add(OrderStateLedger(order_id=order2.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # Confirm Order 2 -> Should fail with 400 Bad Request
    response = client.put(f"/api/v1/orders/{order2.id}/status", json={"to_status": "Confirmed"})
    assert response.status_code == 400
    assert "Credit limit exceeded" in response.json()["detail"]

    # Verify outstanding balance was NOT incremented for Order 2
    db_session.expire_all()
    cust_db2 = db_session.get(Customer, cust.id)
    assert float(cust_db2.outstanding_balance) == 2500.0


def test_list_orders_with_invoice_payment_status(db_session, client):
    from app.models.invoice import Invoice
    
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Payment Status List Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Product
    p = Product(sku_id="PROD-LIST-PAY", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # 3. Setup Customer
    cust = Customer(
        retailer_name="Payment List Customer", customer_id="C-PAY-LIST-1", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # 4. Setup Order 1 (without invoice)
    order1 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-PAY-LIST-1",
        source="WhatsApp",
        customer_id=cust.id
    )
    db_session.add(order1)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order1.id, product_id=p.id, quantity=5, unit_price=45.0))

    # 5. Setup Order 2 (with invoice having status PAID)
    order2 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-PAY-LIST-2",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order2)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order2.id, product_id=p.id, quantity=10, unit_price=45.0))

    # Add Invoice for Order 2
    inv2 = Invoice(
        tenant_id=tenant.id,
        order_id=order2.id,
        gstin=cust.gstin,
        total_amount=450.0,
        payment_status="PAID",
        amount_paid=450.0
    )
    db_session.add(inv2)
    db_session.commit()

    # 6. Call List orders API
    response = client.get(f"/api/v1/orders?tenant_id={tenant.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Map results by order_id
    results_map = {item["order_id"]: item for item in data}

    # Verify Order 1 (no invoice, should default to UNPAID and 0.0 amount_paid)
    assert "ORD-PAY-LIST-1" in results_map
    assert results_map["ORD-PAY-LIST-1"]["payment_status"] == "UNPAID"
    assert results_map["ORD-PAY-LIST-1"]["amount_paid"] == 0.0

    # Verify Order 2 (has invoice with PAID status)
    assert "ORD-PAY-LIST-2" in results_map
    assert results_map["ORD-PAY-LIST-2"]["payment_status"] == "PAID"
    assert results_map["ORD-PAY-LIST-2"]["amount_paid"] == 450.0


def test_get_order_by_id_with_allocations(db_session, client):
    from app.models.invoice import Invoice
    from app.models.payment import Payment, PaymentInvoiceLink
    
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Order Details Detail Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Product
    p = Product(sku_id="PROD-DET-PAY", brand="HUL", category="Soap", pack_size="100g", base_price=50.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # 3. Setup Customer
    cust = Customer(
        retailer_name="Payment Detail Customer", customer_id="C-PAY-DET-1", address_text="Mumbai",
        gstin="27AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # 4. Setup Order (with invoice having status PAID and one allocated payment)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-PAY-DET-1",
        source="WhatsApp",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=50.0))

    # Add Invoice
    inv = Invoice(
        tenant_id=tenant.id,
        order_id=order.id,
        gstin=cust.gstin,
        total_amount=500.0,
        payment_status="PAID",
        amount_paid=500.0
    )
    db_session.add(inv)
    db_session.flush()

    # Add Payment
    pay = Payment(
        tenant_id=tenant.id,
        customer_id=cust.id,
        amount=500.0,
        method="UPI",
        reference_number="TXN1234567890",
        status="COMPLETED"
    )
    db_session.add(pay)
    db_session.flush()

    # Add Payment-Invoice Link
    link = PaymentInvoiceLink(
        tenant_id=tenant.id,
        payment_id=pay.id,
        invoice_id=inv.id,
        amount_allocated=500.0
    )
    db_session.add(link)
    db_session.commit()

    # 5. Call single order lookup API
    response = client.get(f"/api/v1/orders/{order.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(order.id)
    assert data["order_id"] == "ORD-PAY-DET-1"
    assert data["payment_status"] == "PAID"
    assert data["amount_paid"] == 500.0
    assert len(data["payments_allocated"]) == 1
    assert data["payments_allocated"][0]["payment_code"] == f"PAY-REC-{str(pay.id)[:8].upper()}"
    assert data["payments_allocated"][0]["amount_allocated"] == 500.0
    assert data["payments_allocated"][0]["total_voucher_amount"] == 500.0
    assert data["payments_allocated"][0]["method"] == "UPI"
    assert data["payments_allocated"][0]["reference_number"] == "TXN1234567890"

    # 6. Test 404
    fake_id = uuid.uuid4()
    response_404 = client.get(f"/api/v1/orders/{fake_id}")
    assert response_404.status_code == 404


def test_create_order_from_payload(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Create Order Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    prod = Product(
        sku_id="PROD-TEST-CREATE",
        brand="HUL",
        category="Soap",
        pack_size="1 unit",
        base_price=50.0,
        stock_quantity=100
    )
    db_session.add(prod)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Create Order Stores",
        customer_id="C-CREATE-1",
        address_text="Test Address",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days"
    )
    db_session.add(cust)
    db_session.flush()
    db_session.commit()

    # Post creation payload
    payload = {
        "tenant_id": str(tenant.id),
        "customer_id": str(cust.id),
        "source": "WhatsApp",
        "status": "Draft",
        "items": [
            {
                "sku_id": "PROD-TEST-CREATE",
                "quantity": 5,
                "unit_price": 50.0
            }
        ]
    }

    response = client.post("/api/v1/orders", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "order_id" in data
    assert "internal_order_id" in data
    assert data["new_status"] == "Draft"

    # Query DB to check if order and items are created
    created_order_id = uuid.UUID(data["order_id"])
    order = db_session.get(Order, created_order_id)
    assert order is not None
    assert order.tenant_id == tenant.id
    assert order.customer_id == cust.id
    assert order.source == "WhatsApp"
    assert order.current_status == "Draft"

    line_items = db_session.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    assert len(line_items) == 1
    assert line_items[0].product_id == prod.id
    assert line_items[0].quantity == 5
    assert line_items[0].unit_price == 50.0


def test_patch_order_invoice_type(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Patch Order Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Customer
    cust = Customer(
        retailer_name="Patch Order Stores",
        customer_id="C-PATCH-1",
        address_text="Test Address",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-PATCH-1",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="UNSPECIFIED"
    )
    db_session.add(order)
    db_session.commit()

    # 1. Success Patch
    response = client.patch(f"/api/v1/orders/{order.id}", json={"invoice_type": "GST_TAX_INVOICE"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["invoice_type"] == "GST_TAX_INVOICE"

    # Verify db updated
    db_session.refresh(order)
    assert order.invoice_type == "GST_TAX_INVOICE"

    # 2. Validation Failure
    response_fail = client.patch(f"/api/v1/orders/{order.id}", json={"invoice_type": "INVALID_TYPE"})
    assert response_fail.status_code == 422


def test_batch_confirm_order_success(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Batch Confirm Tenant")
    db_session.add(tenant)
    db_session.flush()
    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(
        sku_id="PROD-BATCH-1",
        brand="Brand X",
        category="Category Y",
        pack_size="1 Liter",
        base_price=150.0,
        stock_quantity=100
    )
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Batch Confirm Retailer",
        customer_id="C-BATCH-1",
        address_text="Test Address",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-BATCH-CONFIRM-1",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="UNSPECIFIED"
    )
    db_session.add(order)
    db_session.flush()

    # Setup Unmatched Line Item
    item = OrderLineItem(
        order_id=order.id,
        product_id=None,
        quantity=5,
        unit_price=0.0,
        unmatched_raw_text="Brand X 1L"
    )
    db_session.add(item)
    db_session.commit()

    # Call atomic batch-confirm
    response = client.post(
        f"/api/v1/orders/{order.id}/batch-confirm",
        json={
            "invoice_type": "RETAIL_INVOICE",
            "resolved_items": [
                {
                    "item_id": str(item.id),
                    "product_id": str(p.id)
                }
            ]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["new_status"] == "Confirmed"
    assert data["changes_applied"] == 1

    # Verify db updates
    db_session.refresh(order)
    db_session.refresh(item)
    assert order.current_status == "Confirmed"
    assert order.invoice_type == "RETAIL_INVOICE"
    assert item.product_id == p.id
    assert float(item.unit_price) == 150.0
    assert item.unmatched_raw_text is None  # self-learning cleared it


def test_record_delivery_event(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Delivery Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Customer
    cust = Customer(
        retailer_name="Delivery Retailer", customer_id="C-DEL", address_text="Address",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-DELIVERY-TEST-1",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # Call delivery event endpoint
    response = client.post(
        f"/api/v1/orders/{order.id}/delivery-event",
        json={
            "status": "delivered",
            "source": "manual",
            "tenant_id": str(tenant.id)
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Delivered"
    assert data["delivery_source"] == "manual"
    assert data["delivered_at"] is not None

    db_session.expire_all()
    db_session.refresh(order)
    assert order.current_status == "Delivered"
    assert order.delivery_source == "manual"
    assert order.delivered_at is not None


def test_orders_list_query_count_regression(db_session, client):
    from sqlalchemy import event
    
    # Setup Tenant
    tenant = DistributorTenant(name="Query Count Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Helper to create an order
    def create_mock_order(idx):
        cust = Customer(
            retailer_name=f"Retailer {idx}", customer_id=f"C-Q-{idx}", address_text="Address",
            gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
        )
        db_session.add(cust)
        db_session.flush()

        order = Order(
            tenant_id=tenant.id,
            internal_order_id=f"ORD-QC-{idx}",
            source="Portal",
            customer_id=cust.id,
            status="Draft"
        )
        db_session.add(order)
        db_session.flush()
        
        db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
        db_session.commit()
        return order

    # Create 1 order
    create_mock_order(1)

    queries_count_1 = 0
    @event.listens_for(db_session.bind, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal queries_count_1
        queries_count_1 += 1

    # Call list endpoint
    resp = client.get(f"/api/v1/orders?tenant_id={tenant.id}")
    assert resp.status_code == 200
    
    # Remove listener
    event.remove(db_session.bind, "after_cursor_execute", receive_after_cursor_execute)

    # Create 4 more orders (total 5)
    for i in range(2, 6):
        create_mock_order(i)

    queries_count_5 = 0
    @event.listens_for(db_session.bind, "after_cursor_execute")
    def receive_after_cursor_execute_5(conn, cursor, statement, parameters, context, executemany):
        nonlocal queries_count_5
        queries_count_5 += 1

    # Call list endpoint again
    resp = client.get(f"/api/v1/orders?tenant_id={tenant.id}")
    assert resp.status_code == 200

    event.remove(db_session.bind, "after_cursor_execute", receive_after_cursor_execute_5)

    # Assert query count remains bounded (constant query complexity, not O(N))
    assert queries_count_5 <= queries_count_1 + 1


def test_order_risk_assessment(db_session, client):
    # Setup mock data for tenant, customer, order
    from app.models.tenant import DistributorTenant
    from app.models.customer import Customer
    from app.models.order import Order, OrderLineItem, OrderStateLedger
    from app.models.product import Product
    import uuid

    tenant = DistributorTenant(id=uuid.uuid4(), name="Risk Test Tenant")
    db_session.add(tenant)
    
    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        retailer_name="Risk Test Retailer",
        outstanding_balance=8000.0,
        credit_limit=10000.0,
        phone_number="+919999999999",
        whatsapp_notifications_enabled=True
    )
    db_session.add(customer)
    
    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="PROD-RISK-1",
        brand="Risk Brand",
        category="Risk Cat",
        pack_size="Pack of 1",
        base_price=100.0,
        stock_quantity=50
    )
    db_session.add(product)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        customer_id=customer.id,
        internal_order_id="ORD-RISK-1",
        source="Risk Source",
        status="Draft"
    )
    db_session.add(order)
    db_session.flush()

    line_item = OrderLineItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order.id,
        product_id=product.id,
        quantity=5,
        unit_price=100.0
    )
    db_session.add(line_item)
    
    ledger = OrderStateLedger(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order.id,
        from_status=None,
        to_status="Draft",
        updated_by="test"
    )
    db_session.add(ledger)
    db_session.commit()

    # Call risk assessment endpoint
    resp = client.get(f"/api/v1/orders/{order.id}/risk-assessment?tenant_id={tenant.id}")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["order_id"] == str(order.id)
    assert data["customer_id"] == str(customer.id)
    assert data["score"] >= 0
    assert data["level"] in ("clear", "caution", "high_risk")
    assert "signals" in data
    assert "recommendation" in data
    assert data["outstanding_balance"] == 8000.0
    assert data["credit_limit"] == 10000.0
    assert data["credit_utilisation_pct"] == 80.0

