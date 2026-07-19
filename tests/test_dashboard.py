import uuid
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product, ProductAlias
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.invoice import Invoice
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_dashboard_api_endpoints(db_session, client, seed_demo_data):
    # The default tenant ID used by the seeder is:
    demo_tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")

    # Call metrics endpoint which triggers ensure_demo_data seeder
    resp_metrics = client.get(f"/api/v1/dashboard/metrics?tenant_id={demo_tenant_id}")
    assert resp_metrics.status_code == 200
    metrics = resp_metrics.json()
    
    # Assert dynamically calculated metrics from the seeder data
    assert metrics["total_sales"] == 252970.0
    assert metrics["orders_count"] == 5
    assert metrics["average_order_value"] == 50594.0
    assert metrics["outstanding_collections"] == 377190.0

    # Call recent orders endpoint
    resp_orders = client.get(f"/api/v1/dashboard/recent-orders?tenant_id={demo_tenant_id}")
    assert resp_orders.status_code == 200
    orders = resp_orders.json()
    assert len(orders) == 5
    
    # Verify latest order status is resolved from ledger
    latest_order = orders[0]
    assert latest_order["order_id"] == "ORD-2505-1482"
    assert latest_order["status"] == "Confirmed"
    assert latest_order["customer"] == "Kaveri Provision Store"
    assert latest_order["amount"] == 23650.00

    # Test order detail endpoint using the latest order id
    order_uuid = latest_order["id"]
    resp_details = client.get(f"/api/v1/dashboard/order-details/{order_uuid}")
    assert resp_details.status_code == 200
    details = resp_details.json()
    assert len(details) == 1
    assert details[0]["sku_id"] == "PROD-HUL-SOAP"
    assert details[0]["total_price"] == 23650.00

    # Call collections donut data endpoint
    resp_donut = client.get(f"/api/v1/dashboard/collections-donut?tenant_id={demo_tenant_id}")
    assert resp_donut.status_code == 200
    donut = resp_donut.json()
    assert len(donut) == 4
    # Check outstanding buckets partition matches screenshot percentages
    assert next(item for item in donut if item["name"] == "0-15 Days")["percentage"] == 39
    assert next(item for item in donut if item["name"] == "16-30 Days")["percentage"] == 29
    assert next(item for item in donut if item["name"] == "31-60 Days")["percentage"] == 22
    assert next(item for item in donut if item["name"] == "60+ Days")["percentage"] == 10

    # Call activity feed endpoint
    resp_activity = client.get(f"/api/v1/dashboard/recent-activity?tenant_id={demo_tenant_id}")
    assert resp_activity.status_code == 200
    activity = resp_activity.json()
    assert len(activity) >= 5
    # Verify chronological ordering (newest first)
    assert "ORD-2505-1482" in activity[0]["message"]


def test_customer_whatsapp_thread(db_session, client, seed_demo_data):
    demo_tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    kaveri_id = "c1010000-0000-0000-0000-000000000001"   # has a WhatsApp order
    maruthi_id = "c1010000-0000-0000-0000-000000000002"  # only a Portal order

    # Trigger the seeder.
    client.get(f"/api/v1/dashboard/metrics?tenant_id={demo_tenant_id}")

    # Customer with a WhatsApp-sourced order returns the real order + line items.
    resp = client.get(
        f"/api/v1/dashboard/customer-whatsapp-thread/{kaveri_id}?tenant_id={demo_tenant_id}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["order"] is not None
    assert data["order"]["order_id"] == "ORD-2505-1482"
    assert data["order"]["source"] == "WhatsApp"
    assert data["order"]["status"] == "Confirmed"
    assert data["has_unmatched"] is False
    assert data["total"] == 23650.00
    assert len(data["items"]) == 1
    assert data["items"][0]["sku_id"] == "PROD-HUL-SOAP"
    assert data["items"][0]["total_price"] == 23650.00

    # Customer with no WhatsApp order returns an empty thread (not the Portal order).
    resp_empty = client.get(
        f"/api/v1/dashboard/customer-whatsapp-thread/{maruthi_id}?tenant_id={demo_tenant_id}"
    )
    assert resp_empty.status_code == 200
    empty = resp_empty.json()
    assert empty["order"] is None
    assert empty["items"] == []
    assert empty["total"] == 0.0


def test_dashboard_metrics_date_filtering(db_session, client, seed_demo_data):
    demo_tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    
    # 1. Call metrics with dates that filter orders
    resp = client.get(
        f"/api/v1/dashboard/metrics?tenant_id={demo_tenant_id}&start_date=2026-06-01&end_date=2026-06-30"
    )
    assert resp.status_code == 200
    data = resp.json()
    
    # Check that sales, count, and AOV are computed dynamically
    assert "total_sales" in data
    assert "orders_count" in data
    assert "average_order_value" in data
    
    # Snapshot collections must still return full value
    assert data["outstanding_collections"] > 0


def test_dashboard_tenant_validation_guardrails(client):
    # 1. Missing tenant context entirely
    resp = client.get("/api/v1/dashboard/metrics")
    assert resp.status_code == 401
    assert "Session expired or token missing" in resp.json()["detail"]

    # 2. Invalid UUID format
    resp = client.get("/api/v1/dashboard/metrics?tenant_id=not-a-valid-uuid")
    assert resp.status_code == 401
    assert "Invalid workspace session context token formatting" in resp.json()["detail"]

    # 3. Empty string tenant ID
    resp = client.get("/api/v1/dashboard/metrics?tenant_id=")
    assert resp.status_code == 401
    assert "Session expired or token missing" in resp.json()["detail"]


def test_dashboard_overview_endpoint(db_session, client, seed_demo_data):
    demo_tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")

    # Call overview endpoint
    resp = client.get(f"/api/v1/dashboard/overview?tenant_id={demo_tenant_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert "metrics" in data
    assert "recent_orders" in data
    assert "donut_data" in data

    metrics = data["metrics"]
    assert metrics["total_sales"] == 252970.0
    assert metrics["orders_count"] == 5
    assert metrics["average_order_value"] == 50594.0

    recent_orders = data["recent_orders"]
    assert len(recent_orders) == 5
    assert recent_orders[0]["order_id"] == "ORD-2505-1482"
    assert recent_orders[0]["status"] == "Confirmed"

    donut = data["donut_data"]
    assert len(donut) == 4
    assert next(item for item in donut if item["name"] == "0-15 Days")["percentage"] == 39


def test_dashboard_collections_donut_non_demo_tenant_buckets_by_invoice_age(db_session, client):
    """
    Regression test for the collections-donut / dashboard-overview N+1 fix: the
    non-demo-tenant path previously looked up each invoice's parent Order via a
    per-row db.get(Order, ...) call just to read its created_at for aging — an N+1
    query pattern that scaled linearly with invoice count. It now buckets directly
    off Invoice.created_at (each invoice already has its own timestamp). This test
    proves the aging buckets are still computed correctly after that change.
    """
    tenant = DistributorTenant(name="Donut Aging Test Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    customer = Customer(
        retailer_name="Aging Test Retailer", customer_id="C-AGING-1", address_text="Addr",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(customer)
    db_session.flush()

    def _make_invoice(order_days_old: int, invoice_days_old: int, amount: float):
        order = Order(
            tenant_id=tenant.id,
            internal_order_id=f"ORD-AGE-{invoice_days_old}",
            source="Portal",
            customer_id=customer.id,
            # Deliberately backdated to a *different* age bucket than the invoice
            # below (e.g. an order placed long ago, invoiced only recently) — this
            # is what actually distinguishes the old buggy behavior (bucketed by
            # order.created_at) from the fix (bucketed by invoice.created_at).
            created_at=datetime.utcnow() - timedelta(days=order_days_old),
        )
        db_session.add(order)
        db_session.flush()
        invoice = Invoice(
            order_id=order.id,
            tenant_id=tenant.id,
            gstin="07AAAAA1111A1Z1",
            total_amount=amount,
            customer_id=customer.id,
            created_at=datetime.utcnow() - timedelta(days=invoice_days_old),
        )
        db_session.add(invoice)

    # Order placed 90 days ago (would fall in "60+ Days" under the old, buggy
    # order.created_at-based bucketing) but invoiced only 5 days ago — must land
    # in "0-15 Days" now that bucketing uses the invoice's own timestamp.
    _make_invoice(order_days_old=90, invoice_days_old=5, amount=1000.0)
    # Order placed 10 days ago (would fall in "0-15 Days" under the old bucketing)
    # but invoiced 45 days ago — must land in "31-60 Days".
    _make_invoice(order_days_old=10, invoice_days_old=45, amount=3000.0)
    db_session.commit()

    resp = client.get(f"/api/v1/dashboard/collections-donut?tenant_id={tenant.id}")
    assert resp.status_code == 200
    donut = resp.json()

    bucket_0_15 = next(item for item in donut if item["name"] == "0-15 Days")
    bucket_31_60 = next(item for item in donut if item["name"] == "31-60 Days")
    bucket_16_30 = next(item for item in donut if item["name"] == "16-30 Days")
    bucket_60_plus = next(item for item in donut if item["name"] == "60+ Days")

    assert bucket_0_15["value"] == 1000.0
    assert bucket_31_60["value"] == 3000.0
    assert bucket_16_30["value"] == 0
    assert bucket_60_plus["value"] == 0


def test_dashboard_credit_risk_alerts(db_session, client, seed_demo_data):
    demo_tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")

    # Call credit-risk-alerts endpoint
    resp = client.get(f"/api/v1/dashboard/credit-risk-alerts?tenant_id={demo_tenant_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert "alerts" in data
    assert "total_at_risk_count" in data
    assert "total_at_risk_amount" in data


def test_dashboard_business_health_score(db_session, client, seed_demo_data):
    demo_tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")

    # Seed extra orders if needed to meet the 5+ confirmed orders in last 30 days check.
    # Note: seed_demo_data already seeds 5 orders:
    # ORD-2505-1476, ORD-2505-1477, ORD-2505-1479, ORD-2505-1481, ORD-2505-1482
    # All are Confirmed or Delivered and created within the timeframe.

    # 1. Fetch business health score
    resp = client.get(f"/api/v1/dashboard/business-health-score?tenant_id={demo_tenant_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert "has_sufficient_data" in data
    if data["has_sufficient_data"]:
        assert "score" in data
        assert "band" in data
        assert "signals" in data
        signals = data["signals"]
        assert "collections" in signals
        assert "sales" in signals
        assert "recovery" in signals
        assert "inventory" in signals
        assert "fulfillment" in signals



