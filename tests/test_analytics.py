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

def test_analytics_endpoints(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Analytics Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    prod = Product(
        sku_id="ANALYTICS-SKU", brand="TestBrand", category="TestCategory", pack_size="1", base_price=10.0
    )
    db_session.add(prod)
    
    # Setup Customer
    cust = Customer(
        retailer_name="Analytics Store", customer_id="C-ANALYTICS", address_text="St",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=50000.0, outstanding_balance=2500.0
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        internal_order_id="ORD-ANALYTICS", source="Portal", customer_id=cust.id, tenant_id=tenant.id
    )
    db_session.add(order)
    db_session.flush()

    # Line Item
    item = OrderLineItem(
        tenant_id=tenant.id, order_id=order.id, product_id=prod.id, quantity=5, unit_price=100.0
    )
    db_session.add(item)

    # Ledger transition to Confirmed
    ledger1 = OrderStateLedger(
        tenant_id=tenant.id, order_id=order.id, from_status=None, to_status="Confirmed", updated_by="test"
    )
    db_session.add(ledger1)
    db_session.commit()

    # Call sales analytics
    response = client.get(f"/api/v1/analytics/sales?tenant_id={tenant.id}")
    assert response.status_code == 200
    sales_data = response.json()
    assert sales_data["status"] == "success"
    assert sales_data["total_orders"] == 1
    assert sales_data["status_distribution"]["Confirmed"] == 1
    assert len(sales_data["top_moving_skus"]) == 1
    assert sales_data["top_moving_skus"][0]["sku_code"] == "ANALYTICS-SKU"
    assert sales_data["top_moving_skus"][0]["total_quantity"] == 5

    # Call revenue analytics
    response = client.get(f"/api/v1/analytics/revenue?tenant_id={tenant.id}")
    assert response.status_code == 200
    rev_data = response.json()
    assert rev_data["status"] == "success"
    assert rev_data["total_revenue"] == 500.0
    assert rev_data["total_receivables"] == 2500.0
    assert len(rev_data["time_series"]) == 1
    assert rev_data["time_series"][0]["sales"] == 500.0
