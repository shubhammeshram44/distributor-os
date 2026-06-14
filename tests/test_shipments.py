import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.product import Product
from app.models.customer import Customer
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.shipment import Shipment
from app.models.user import User
from app.database import tenant_context


@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_shipment_endpoints(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Shipment Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    prod = Product(
        sku_id="SHIP-SKU", brand="ShipBrand", category="ShipCat", pack_size="1", base_price=10.0
    )
    db_session.add(prod)
    
    # Setup Customer
    cust = Customer(
        retailer_name="Ship Store", customer_id="C-SHIP", address_text="Ship Address",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=50000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        internal_order_id="ORD-SHIP", source="Portal", customer_id=cust.id, tenant_id=tenant.id
    )
    db_session.add(order)
    db_session.flush()

    # Line Item
    item = OrderLineItem(
        tenant_id=tenant.id, order_id=order.id, product_id=prod.id, quantity=1, unit_price=1000.0
    )
    db_session.add(item)

    # Ledger transition to Confirmed
    ledger = OrderStateLedger(
        tenant_id=tenant.id, order_id=order.id, from_status=None, to_status="Confirmed", updated_by="test"
    )
    db_session.add(ledger)

    # Setup Driver User
    driver = User(
        tenant_id=tenant.id, full_name="John Doe", phone_number="+919999888877", role="Driver"
    )
    db_session.add(driver)
    db_session.commit()

    # 0. Call GET /users?role=Driver
    response = client.get(f"/api/v1/users?role=Driver&tenant_id={tenant.id}")
    assert response.status_code == 200
    drivers_list = response.json()
    assert len(drivers_list) == 1
    assert drivers_list[0]["full_name"] == "John Doe"
    assert drivers_list[0]["phone_number"] == "+919999888877"

    # 1. Call GET /pending

    response = client.get(f"/api/v1/shipments/pending?tenant_id={tenant.id}")
    assert response.status_code == 200
    pending_data = response.json()
    assert len(pending_data) == 1
    assert pending_data[0]["internal_order_id"] == "ORD-SHIP"
    assert pending_data[0]["invoice_amount"] == 1000.0

    # 2. Call POST to create shipment
    response = client.post(
        f"/api/v1/shipments?tenant_id={tenant.id}",
        json={
            "driver_id": str(driver.id),
            "vehicle_number": "KA-05-AB-1234",
            "order_ids": [pending_data[0]["order_id"]]
        }
    )

    assert response.status_code == 201
    assert response.json()["status"] == "success"
    assert response.json()["count"] == 1

    # 3. Call GET /active
    response = client.get(f"/api/v1/shipments/active?tenant_id={tenant.id}")
    assert response.status_code == 200
    active_data = response.json()
    assert len(active_data) == 1
    assert active_data[0]["driver_name"] == "John Doe"
    assert active_data[0]["vehicle_number"] == "KA-05-AB-1234"
    assert active_data[0]["status"] == "Out For Delivery"
    assert active_data[0]["is_paid"] is False

    shipment_id = active_data[0]["shipment_id"]

    # 4. Call PATCH to change status to Delivered
    response = client.patch(
        f"/api/v1/shipments/{shipment_id}/status",
        json={
            "status": "Delivered",
            "source": "back_office"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["new_status"] == "Delivered"

    # Verify DB update
    db_session.expire_all()
    shipment_db = db_session.get(Shipment, uuid.UUID(shipment_id))
    assert shipment_db.status == "Delivered"

    # Verify order state ledger has Delivered transition
    db_session.expire_all()
    assert order.current_status == "Delivered"
