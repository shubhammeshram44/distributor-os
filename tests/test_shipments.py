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
from app.utils.security import sign_jwt


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

    # Set JWT token cookie to authorize requests to /shipments endpoints
    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    # 1. Call GET /pending

    response = client.get("/api/v1/shipments/pending")
    assert response.status_code == 200
    pending_data = response.json()["items"]
    assert len(pending_data) == 1
    assert pending_data[0]["internal_order_id"] == "ORD-SHIP"
    assert pending_data[0]["invoice_amount"] == 1000.0

    # 2. Call POST to create shipment
    response = client.post(
        "/api/v1/shipments",
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
    response = client.get("/api/v1/shipments/active")
    assert response.status_code == 200
    active_data = response.json()["items"]
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


def test_shipments_query_count_regression(db_session, client):
    from sqlalchemy import event
    
    # Setup Tenant
    tenant = DistributorTenant(name="Shipment Query Count Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Set JWT token cookie
    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    prod = Product(
        sku_id="SHIP-SKU-QC", brand="ShipBrand", category="ShipCat", pack_size="1", base_price=10.0
    )
    db_session.add(prod)
    
    cust = Customer(
        retailer_name="Ship Store QC", customer_id="C-SHIP-QC", address_text="Ship Address",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=50000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()

    # Helper to create active shipment
    def create_mock_shipment(idx):
        order = Order(
            internal_order_id=f"ORD-SHIP-QC-{idx}", source="Portal", customer_id=cust.id, tenant_id=tenant.id
        )
        db_session.add(order)
        db_session.flush()

        item = OrderLineItem(
            tenant_id=tenant.id, order_id=order.id, product_id=prod.id, quantity=1, unit_price=100.0
        )
        db_session.add(item)

        ledger = OrderStateLedger(
            tenant_id=tenant.id, order_id=order.id, from_status=None, to_status="Confirmed", updated_by="test"
        )
        db_session.add(ledger)
        db_session.flush()

        shipment = Shipment(
            tenant_id=tenant.id,
            order_id=order.id,
            carrier="Test Driver",
            tracking_id=f"TEST-VEHICLE-{idx}",
            status="Created",
            destination="Ship Address"
        )
        db_session.add(shipment)
        db_session.commit()

    # Create 1 shipment
    create_mock_shipment(1)

    queries_count_1 = 0
    @event.listens_for(db_session.bind, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal queries_count_1
        queries_count_1 += 1

    resp = client.get("/api/v1/shipments/active")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1

    event.remove(db_session.bind, "after_cursor_execute", receive_after_cursor_execute)

    # Create 4 more shipments
    for i in range(2, 6):
        create_mock_shipment(i)

    queries_count_5 = 0
    @event.listens_for(db_session.bind, "after_cursor_execute")
    def receive_after_cursor_execute_5(conn, cursor, statement, parameters, context, executemany):
        nonlocal queries_count_5
        queries_count_5 += 1

    resp = client.get("/api/v1/shipments/active")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 5

    event.remove(db_session.bind, "after_cursor_execute", receive_after_cursor_execute_5)

    # Assert query count remains constant
    assert queries_count_5 <= queries_count_1 + 1


def test_shipments_pagination_and_search(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Shipment Pagination Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Set JWT token cookie
    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    prod = Product(
        sku_id="SHIP-SKU-PAG", brand="ShipBrand", category="ShipCat", pack_size="1", base_price=10.0
    )
    db_session.add(prod)
    
    cust1 = Customer(
        retailer_name="Alice Store", customer_id="C-SHIP-P1", address_text="Address 1",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    cust2 = Customer(
        retailer_name="Bob Store", customer_id="C-SHIP-P2", address_text="Address 2",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add_all([cust1, cust2])
    db_session.flush()

    # Create 3 orders and shipments
    for i, cust in enumerate([cust1, cust2, cust1]):
        order = Order(
            internal_order_id=f"ORD-PAG-{i}", source="Portal", customer_id=cust.id, tenant_id=tenant.id
        )
        db_session.add(order)
        db_session.flush()

        ledger = OrderStateLedger(
            tenant_id=tenant.id, order_id=order.id, from_status=None, to_status="Confirmed", updated_by="test"
        )
        db_session.add(ledger)
        db_session.flush()

        shipment = Shipment(
            tenant_id=tenant.id,
            order_id=order.id,
            carrier="Driver P",
            tracking_id=f"VEHICLE-{i}",
            status="Created" if i < 2 else "Delivered",
            destination="Address"
        )
        db_session.add(shipment)
        db_session.commit()

    # 1. Test Search by Customer Name
    resp = client.get("/api/v1/shipments/active?q=Alice")
    assert resp.status_code == 200
    data = resp.json()["items"]
    assert len(data) == 2
    assert all("Alice Store" in item["customer_name"] for item in data)

    # 2. Test Search by Order ID
    resp = client.get("/api/v1/shipments/active?q=ORD-PAG-1")
    assert resp.status_code == 200
    data = resp.json()["items"]
    assert len(data) == 1
    assert data[0]["internal_order_id"] == "ORD-PAG-1"

    # 3. Test Filter by status
    resp = client.get("/api/v1/shipments/active?status=Delivered")
    assert resp.status_code == 200
    data = resp.json()["items"]
    assert len(data) == 1
    assert data[0]["status"] == "Delivered"

    # 4. Test Keyset Pagination
    resp = client.get("/api/v1/shipments/active?limit=2")
    assert resp.status_code == 200
    pag_data = resp.json()
    assert len(pag_data["items"]) == 2
    assert pag_data["next_cursor"] is not None

    # Fetch page 2 using cursor
    cursor = pag_data["next_cursor"]
    resp2 = client.get(f"/api/v1/shipments/active?limit=2&cursor={cursor}")
    assert resp2.status_code == 200
    pag_data2 = resp2.json()
    assert len(pag_data2["items"]) == 1
    assert pag_data2["next_cursor"] is None


def _setup_tenant_order_shipment(db_session, tenant_name, order_status="Confirmed", create_shipment=True):
    tenant = DistributorTenant(name=tenant_name)
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    cust = Customer(
        tenant_id=tenant.id, retailer_name=f"{tenant_name} Shop", customer_id=f"C-{tenant_name}",
        address_text="Address", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(tenant_id=tenant.id, internal_order_id=f"ORD-{tenant_name}", source="Portal", customer_id=cust.id)
    db_session.add(order)
    db_session.flush()
    order.status = order_status
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status=order_status, updated_by="test"))
    db_session.commit()

    shipment = None
    if create_shipment:
        shipment = Shipment(
            tenant_id=tenant.id, order_id=order.id, carrier="Test Carrier",
            tracking_id="TRACK-1", status="Out For Delivery", destination="Address"
        )
        db_session.add(shipment)
        db_session.commit()

    return tenant, cust, order, shipment


def test_create_shipment_rejects_cross_tenant_order(db_session, client):
    """
    Regression test for SHIP-1: create_shipment previously fetched Order/
    Customer by PK alone with no tenant_id filter -- any order_id supplied
    in the request body (regardless of which tenant actually owns it) would
    be dispatched. This proves an order belonging to a DIFFERENT tenant than
    the caller is silently skipped, not hijacked.
    """
    tenant_a, _, order_a, _ = _setup_tenant_order_shipment(db_session, "ShipCrossA", create_shipment=False)
    tenant_b = DistributorTenant(name="ShipCrossB")
    db_session.add(tenant_b)
    db_session.commit()

    driver = User(tenant_id=tenant_b.id, full_name="Driver B", phone_number="+919999000011", role="Driver")
    db_session.add(driver)
    db_session.commit()

    token_b = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant_b.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token_b)

    response = client.post(
        "/api/v1/shipments",
        json={"driver_id": str(driver.id), "vehicle_number": "KA-01-XX-0001", "order_ids": [str(order_a.id)]}
    )
    assert response.status_code == 201
    assert response.json()["count"] == 0

    db_session.expire_all()
    db_session.refresh(order_a)
    assert order_a.current_status == "Confirmed"
    assert db_session.query(Shipment).filter(Shipment.order_id == order_a.id).count() == 0
    client.cookies.clear()


def test_create_shipment_rejects_draft_order(db_session, client):
    """
    Regression test for SHIP-3: create_shipment previously dispatched an
    order regardless of its current status. A Draft order must not be
    dispatchable.
    """
    tenant, _, order, _ = _setup_tenant_order_shipment(db_session, "ShipDraftReject", order_status="Draft", create_shipment=False)
    driver = User(tenant_id=tenant.id, full_name="Driver Draft", phone_number="+919999000022", role="Driver")
    db_session.add(driver)
    db_session.commit()

    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    response = client.post(
        "/api/v1/shipments",
        json={"driver_id": str(driver.id), "vehicle_number": "KA-01-XX-0002", "order_ids": [str(order.id)]}
    )
    assert response.status_code == 201
    assert response.json()["count"] == 0

    db_session.expire_all()
    db_session.refresh(order)
    assert order.current_status == "Draft"
    client.cookies.clear()


def test_update_shipment_status_requires_authentication(db_session, client):
    """
    Regression test for SHIP-2: PATCH /shipments/{id}/status previously had
    NO authentication at all -- any caller (even with zero token) could mark
    an arbitrary tenant's shipment delivered.
    """
    tenant, _, order, shipment = _setup_tenant_order_shipment(db_session, "ShipNoAuth", order_status="Dispatched")

    response = client.patch(
        f"/api/v1/shipments/{shipment.id}/status",
        json={"status": "Delivered", "source": "back_office"}
    )
    assert response.status_code == 401

    db_session.expire_all()
    db_session.refresh(shipment)
    assert shipment.status == "Out For Delivery"


def test_update_shipment_status_rejects_cross_tenant(db_session, client):
    """
    Regression test for SHIP-2: an authenticated caller from Tenant B must
    not be able to modify Tenant A's shipment by guessing/enumerating its id.
    """
    tenant_a, _, order_a, shipment_a = _setup_tenant_order_shipment(db_session, "ShipXTenantA", order_status="Dispatched")
    tenant_b = DistributorTenant(name="ShipXTenantB")
    db_session.add(tenant_b)
    db_session.commit()

    token_b = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant_b.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token_b)

    response = client.patch(
        f"/api/v1/shipments/{shipment_a.id}/status",
        json={"status": "Delivered", "source": "back_office"}
    )
    assert response.status_code == 404

    db_session.expire_all()
    db_session.refresh(shipment_a)
    assert shipment_a.status == "Out For Delivery"
    client.cookies.clear()


def test_update_shipment_status_rejects_arbitrary_status(db_session, client):
    """
    Regression test for SHIP-4: payload.status was previously an
    unconstrained string -- arbitrary/garbage values were persisted verbatim
    into shipment.status and order.status.
    """
    tenant, _, order, shipment = _setup_tenant_order_shipment(db_session, "ShipArbitraryStatus", order_status="Dispatched")
    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    response = client.patch(
        f"/api/v1/shipments/{shipment.id}/status",
        json={"status": "totally-made-up-status", "source": "back_office"}
    )
    assert response.status_code == 400

    db_session.expire_all()
    db_session.refresh(shipment)
    assert shipment.status == "Out For Delivery"
    client.cookies.clear()


def test_update_shipment_status_delivered_twice_is_idempotent(db_session, client):
    """
    Regression test for SHIP-4: calling PATCH .../status with "Delivered"
    twice (double-click, retry) previously re-wrote the ledger, overwrote
    delivered_at, and queued a SECOND customer notification each time.
    """
    tenant, _, order, shipment = _setup_tenant_order_shipment(db_session, "ShipDeliverTwice", order_status="Dispatched")
    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    first = client.patch(
        f"/api/v1/shipments/{shipment.id}/status",
        json={"status": "Delivered", "source": "back_office"}
    )
    assert first.status_code == 200

    db_session.expire_all()
    db_session.refresh(order)
    first_delivered_at = order.delivered_at
    ledger_count_after_first = db_session.query(OrderStateLedger).filter(
        OrderStateLedger.order_id == order.id, OrderStateLedger.to_status == "Delivered"
    ).count()
    assert ledger_count_after_first == 1

    # Retry -- must be a safe no-op, not a duplicate transition.
    second = client.patch(
        f"/api/v1/shipments/{shipment.id}/status",
        json={"status": "Delivered", "source": "back_office"}
    )
    assert second.status_code == 200

    db_session.expire_all()
    db_session.refresh(order)
    assert order.delivered_at == first_delivered_at
    ledger_count_after_second = db_session.query(OrderStateLedger).filter(
        OrderStateLedger.order_id == order.id, OrderStateLedger.to_status == "Delivered"
    ).count()
    assert ledger_count_after_second == 1
    client.cookies.clear()


def test_update_shipment_status_requires_order_dispatched_first(db_session, client):
    """
    Regression test for SHIP-4: a shipment must not be marked Delivered
    while its underlying order hasn't actually been Dispatched (e.g. a
    Draft/Cancelled order somehow carrying a shipment row).
    """
    tenant, _, order, shipment = _setup_tenant_order_shipment(db_session, "ShipNotDispatchedYet", order_status="Confirmed")
    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    response = client.patch(
        f"/api/v1/shipments/{shipment.id}/status",
        json={"status": "Delivered", "source": "back_office"}
    )
    assert response.status_code == 409

    db_session.expire_all()
    db_session.refresh(shipment)
    assert shipment.status == "Out For Delivery"
    client.cookies.clear()


def test_create_shipment_race_condition_caught_by_db_constraint(db_session, client, monkeypatch):
    """
    Regression test for SHIP-5: create_shipment's existing-shipment check is
    a plain check-then-insert with no lock -- a classic TOCTOU race. This
    simulates the race directly by monkeypatching the pre-check to always
    report "no existing shipment found" (as if a concurrent request's insert
    hadn't committed yet when this request's SELECT ran), then verifies the
    request still cannot succeed in creating a genuine duplicate: the
    DB-level unique constraint on shipments(tenant_id, order_id) must catch
    it and skip just that order, rather than either crashing the whole
    batch or silently creating two shipment rows for one order.
    """
    tenant, _, order, existing_shipment = _setup_tenant_order_shipment(
        db_session, "ShipRaceTenant", order_status="Confirmed", create_shipment=True
    )

    driver = User(tenant_id=tenant.id, full_name="Race Driver", phone_number="+919999000011", role="Driver")
    db_session.add(driver)
    db_session.commit()

    # Force the pre-check to report "no existing shipment" (simulating the
    # race window), so the request proceeds straight to the insert -- which
    # must then be caught by the DB constraint, not silently succeed.
    from sqlalchemy.orm import Query
    original_first = Query.first

    def _patched_first(self):
        if self.column_descriptions and self.column_descriptions[0]["entity"] is Shipment:
            return None
        return original_first(self)

    monkeypatch.setattr(Query, "first", _patched_first)

    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    response = client.post(
        "/api/v1/shipments",
        json={
            "driver_id": str(driver.id),
            "vehicle_number": "KA-01-RACE-1",
            "order_ids": [str(order.id)]
        }
    )
    client.cookies.clear()

    # The batch endpoint must not 500 -- it should just skip the order that
    # lost the race (count == 0), since a shipment for it already exists.
    assert response.status_code == 201
    assert response.json()["count"] == 0

    db_session.expire_all()
    shipment_count = db_session.query(Shipment).filter(
        Shipment.tenant_id == tenant.id, Shipment.order_id == order.id
    ).count()
    assert shipment_count == 1, "The race must not result in two shipments for the same order"
