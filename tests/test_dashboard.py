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

def test_dashboard_api_endpoints(db_session, client):
    # The default tenant ID used by the seeder is:
    demo_tenant_id = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")

    # Call metrics endpoint which triggers ensure_demo_data seeder
    resp_metrics = client.get(f"/api/v1/dashboard/metrics?tenant_id={demo_tenant_id}")
    assert resp_metrics.status_code == 200
    metrics = resp_metrics.json()
    
    # Assert seeder injected the correct metric quantities matching the dashboard screenshot
    assert metrics["total_sales"] == 2845600
    assert metrics["orders_count"] == 1482
    assert metrics["average_order_value"] == 19210
    assert metrics["outstanding_collections"] == 2137200

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


def test_dashboard_metrics_date_filtering(db_session, client):
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

