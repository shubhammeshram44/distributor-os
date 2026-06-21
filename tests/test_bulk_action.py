import io
import os
import uuid
import zipfile
import pytest
import time
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

def test_bulk_action_success(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Bulk Success Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-BULK-1", brand="BulkBrand", category="TestCategory", pack_size="100ml", base_price=50.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Bulk Stores", customer_id="C-BULK-1", address_text="Bulk Street",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order 1
    order1 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-B1",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="GST_TAX_INVOICE"
    )
    db_session.add(order1)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order1.id, product_id=p.id, quantity=5, unit_price=50.0))
    db_session.add(OrderStateLedger(order_id=order1.id, from_status=None, to_status="Confirmed", updated_by="admin"))

    # Setup Order 2
    order2 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-B2",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="RETAIL_CASH_INVOICE"
    )
    db_session.add(order2)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order2.id, product_id=p.id, quantity=10, unit_price=50.0))
    db_session.add(OrderStateLedger(order_id=order2.id, from_status=None, to_status="Confirmed", updated_by="admin"))

    db_session.commit()

    # Trigger bulk action
    response = client.post(f"/api/v1/orders/bulk-action?tenant_id={tenant.id}", json={
        "order_ids": [str(order1.id), str(order2.id)]
    })
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    job_id = data["job_id"]
    assert job_id is not None

    # Fetch status (FastAPI TestClient runs background tasks synchronously before return)
    status_resp = client.get(f"/api/v1/orders/bulk-action/{job_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "COMPLETED"
    assert status_data["progress"] == 100
    result_link = status_data["result_link"]
    assert result_link.startswith("/static/bulk_")

    # Assert zip file exists and contains PDFs
    zip_path = result_link.lstrip("/")
    assert os.path.exists(zip_path)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        namelist = zf.namelist()
        assert f"invoice_ORD-B1.pdf" in namelist
        assert f"invoice_ORD-B2.pdf" in namelist

    # Test TTL File Cleanup Target directly
    from app.api.v1.orders import cleanup_zip_file_after_delay
    assert os.path.exists(zip_path)
    cleanup_zip_file_after_delay(zip_path, delay_seconds=0)
    assert not os.path.exists(zip_path)


def test_bulk_action_partial_failure(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Bulk Fail Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-BULK-2", brand="BulkBrand", category="TestCategory", pack_size="100ml", base_price=50.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Bulk Stores 2", customer_id="C-BULK-2", address_text="Bulk Street 2",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order 1 (Confirmed)
    order1 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-BF1",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="GST_TAX_INVOICE"
    )
    db_session.add(order1)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order1.id, product_id=p.id, quantity=5, unit_price=50.0))
    db_session.add(OrderStateLedger(order_id=order1.id, from_status=None, to_status="Confirmed", updated_by="admin"))
    db_session.commit()

    # Trigger bulk action with one valid and one non-existent UUID
    invalid_uuid = str(uuid.uuid4())
    response = client.post(f"/api/v1/orders/bulk-action?tenant_id={tenant.id}", json={
        "order_ids": [str(order1.id), invalid_uuid]
    })
    assert response.status_code == 202
    data = response.json()
    job_id = data["job_id"]

    # Fetch status
    status_resp = client.get(f"/api/v1/orders/bulk-action/{job_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "PARTIALLY_COMPLETED"
    assert status_data["progress"] == 100
    assert status_data["result_link"] is not None
    
    # Assert zip file contains only valid order pdf
    zip_path = status_data["result_link"].lstrip("/")
    assert os.path.exists(zip_path)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        namelist = zf.namelist()
        assert "invoice_ORD-BF1.pdf" in namelist
        assert len(namelist) == 1

    # Verify failure details are logged in metadata
    failed = status_data["failed_orders"]
    assert len(failed) == 1
    assert failed[0]["order_id"] == invalid_uuid
    assert "Order not found" in failed[0]["error"]

    # Cleanup zip
    os.remove(zip_path)
