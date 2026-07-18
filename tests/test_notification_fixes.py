"""
Regression tests for two notification-related bugs found during the
performance/UX audit:

1. dispatch_order_post / record_delivery_event previously fired WhatsApp
   notifications via a hand-rolled asyncio.get_running_loop()/asyncio.run()
   fallback. Since both are plain `def` (sync) endpoints executed in
   FastAPI's threadpool (no running event loop in that worker thread), the
   fallback always took the `asyncio.run()` branch — which blocks the HTTP
   response until the WhatsApp API call completes (up to a 10s timeout).
   This test proves the notification is now deferred via FastAPI's
   BackgroundTasks mechanism instead of being run inline.

2. GET/PATCH /api/v1/tenant/notification-prefs previously trusted a raw
   `tenant_id` query parameter with no authentication check at all, unlike
   every sibling endpoint in app/api/v1/tenant.py. This let any caller read
   or silently change another tenant's notification preferences just by
   knowing/guessing their tenant_id. This test proves a request carrying a
   valid JWT for tenant A cannot read/modify tenant B's preferences by
   passing tenant B's id as a query param.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from starlette.background import BackgroundTasks

from app.main import app
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.order import Order, OrderStateLedger
from app.database import tenant_context
from app.utils.security import sign_jwt


@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)


def _make_tenant_and_confirmed_order(db_session, tenant_name, whatsapp_enabled=True):
    tenant = DistributorTenant(name=tenant_name)
    if whatsapp_enabled:
        tenant.whatsapp_phone_id = "test-instance"
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    cust = Customer(
        retailer_name=f"{tenant_name} Retailer", customer_id=f"C-{tenant_name}",
        address_text="Address", gstin="07AAAAA1111A1Z1", tax_group="GST",
        payment_terms="COD", phone_number="9876543210",
        whatsapp_notifications_enabled=True,
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id,
        internal_order_id=f"ORD-{tenant_name}-1",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Confirmed", updated_by="admin"))
    order.status = "Confirmed"
    db_session.commit()

    return tenant, cust, order


def test_dispatch_notification_deferred_to_background_task(db_session):
    """
    Calling dispatch_order_post directly (bypassing the ASGI/TestClient layer,
    which executes background tasks synchronously) must queue the WhatsApp
    notification onto BackgroundTasks rather than awaiting it inline.
    """
    from app.api.v1.orders import dispatch_order_post, DispatchPayload

    tenant, cust, order = _make_tenant_and_confirmed_order(db_session, "DispatchBGTest")

    background_tasks = BackgroundTasks()
    payload = DispatchPayload(delivery_partner="Local Logistics", vehicle_number="KA-01-AB-1234")

    result = dispatch_order_post(order.id, payload, background_tasks, db=db_session)

    assert result["status"] == "success"
    # The notification must be queued as a background task, not executed
    # synchronously inside the request handler.
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func.__name__ == "_fire_dispatched_notification_task"


def test_delivery_event_notification_deferred_to_background_task(db_session):
    from app.api.v1.orders import record_delivery_event, DeliveryEventRequest

    tenant, cust, order = _make_tenant_and_confirmed_order(db_session, "DeliveryBGTest")

    background_tasks = BackgroundTasks()
    payload = DeliveryEventRequest(status="delivered", source="manual", tenant_id=str(tenant.id))

    result = record_delivery_event(order.id, payload, background_tasks, db=db_session)

    assert result["status"] == "Delivered"
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func.__name__ == "_fire_delivered_notification_task"


def test_dispatch_skips_background_task_when_no_customer(db_session):
    """No customer on the order (edge case) must not queue a notification task."""
    from app.api.v1.orders import dispatch_order_post, DispatchPayload

    tenant = DistributorTenant(name="NoCustomerTenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    cust = Customer(
        retailer_name="Orphan Retailer", customer_id="C-ORPHAN", address_text="Addr",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(tenant_id=tenant.id, internal_order_id="ORD-NOCUST-1", source="Portal", customer_id=cust.id)
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Confirmed", updated_by="admin"))
    order.status = "Confirmed"
    db_session.commit()
    # Delete the customer row so order.customer_id points nowhere, matching
    # the pre-existing "if customer:" guard in the endpoint.
    db_session.delete(cust)
    db_session.commit()

    background_tasks = BackgroundTasks()
    payload = DispatchPayload(delivery_partner="Local Logistics", vehicle_number="KA-01-AB-1234")
    result = dispatch_order_post(order.id, payload, background_tasks, db=db_session)

    assert result["status"] == "success"
    assert len(background_tasks.tasks) == 0


def test_notification_prefs_cross_tenant_access_denied(db_session, client):
    """
    A caller authenticated as tenant A must not be able to read or modify
    tenant B's notification preferences by passing tenant B's id as the
    `tenant_id` query parameter.
    """
    tenant_a = DistributorTenant(name="Tenant A")
    tenant_b = DistributorTenant(name="Tenant B", notification_prefs={"order_confirmed": True})
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    token_a = sign_jwt({"tenant_id": str(tenant_a.id), "user_id": str(uuid.uuid4())})

    # GET: even though tenant_id query param points at Tenant B, the resolved
    # tenant must be Tenant A (the JWT owner) — not Tenant B.
    resp = client.get(
        f"/api/v1/tenant/notification-prefs?tenant_id={tenant_b.id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert resp.status_code == 200
    # Tenant A has no notification_prefs set (defaults to None/{}), Tenant B's
    # explicit {"order_confirmed": True} must NOT have been returned.
    assert resp.json() != {"order_confirmed": True}

    # PATCH: attempting to disable Tenant B's order_confirmed notifications
    # while authenticated as Tenant A must not mutate Tenant B's row.
    resp = client.patch(
        f"/api/v1/tenant/notification-prefs?tenant_id={tenant_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"order_confirmed": False}
    )
    assert resp.status_code == 200

    db_session.refresh(tenant_b)
    assert tenant_b.notification_prefs.get("order_confirmed") is True  # untouched


def test_notification_prefs_own_tenant_still_works(db_session, client):
    """Sanity check: a tenant can still read/update its own preferences via JWT."""
    tenant = DistributorTenant(name="Self Access Tenant", notification_prefs={"order_confirmed": True})
    db_session.add(tenant)
    db_session.commit()

    token = sign_jwt({"tenant_id": str(tenant.id), "user_id": str(uuid.uuid4())})

    resp = client.get(
        f"/api/v1/tenant/notification-prefs?tenant_id={tenant.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json().get("order_confirmed") is True

    resp = client.patch(
        f"/api/v1/tenant/notification-prefs?tenant_id={tenant.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"order_confirmed": False}
    )
    assert resp.status_code == 200
    assert resp.json().get("order_confirmed") is False

    db_session.refresh(tenant)
    assert tenant.notification_prefs.get("order_confirmed") is False
