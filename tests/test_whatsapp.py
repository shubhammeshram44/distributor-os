import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product, ProductAlias
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)


def test_whatsapp_webhook_success(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Customer
    customer = Customer(
        retailer_name="Kaveri Provision Store",
        customer_id="CUST-101",
        address_text="Bengaluru",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days"
    )
    db_session.add(customer)
    db_session.flush()

    cust_alias = CustomerAlias(customer_id=customer.id, alias_value="+919999888877")
    db_session.add(cust_alias)

    # Setup Product & Alias
    product = Product(sku_id="PROD-HUL-SOAP", brand="HUL", category="Soap", pack_size="100g", base_price=45.00)
    db_session.add(product)
    db_session.flush()

    alias = ProductAlias(product_id=product.id, alias_name="HUL Soap")
    db_session.add(alias)
    db_session.commit()

    response = client.post("/api/v1/whatsapp/webhook", json={
        "tenant_id": str(tenant.id),
        "phone_number": "+919999888877",
        "message_text": "Need 50 HUL Soap"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["failed_rows"] == 0
    assert data["successful_rows"] == 1


def test_whatsapp_integrations_endpoints(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Integration Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    # 2. Call PATCH endpoint
    patch_payload = {
        "whatsapp_phone_id": "test-phone-id-12345",
        "whatsapp_access_token": "super-secret-token-value-999"
    }
    response = client.patch(
        f"/api/v1/tenant/integrations/whatsapp?tenant_id={tenant.id}",
        json=patch_payload
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify DB update
    db_session.refresh(tenant)
    assert tenant.whatsapp_phone_id == "test-phone-id-12345"
    assert tenant.whatsapp_access_token == "super-secret-token-value-999"

    # 3. Call GET endpoint
    response = client.get(f"/api/v1/tenant/integrations/whatsapp?tenant_id={tenant.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["whatsapp_phone_id"] == "test-phone-id-12345"
    # Token must be masked (Correction 1)
    assert data["whatsapp_access_token"].startswith("•")
    assert data["whatsapp_access_token"].endswith("-999")

    # 4. Call PATCH again with masked token (Correction 1)
    patch_payload_masked = {
        "whatsapp_phone_id": "test-phone-id-modified",
        "whatsapp_access_token": data["whatsapp_access_token"]
    }
    response = client.patch(
        f"/api/v1/tenant/integrations/whatsapp?tenant_id={tenant.id}",
        json=patch_payload_masked
    )
    assert response.status_code == 200

    # Verify that phone ID is updated, but access token is NOT updated or overwritten by mask
    db_session.refresh(tenant)
    assert tenant.whatsapp_phone_id == "test-phone-id-modified"
    assert tenant.whatsapp_access_token == "super-secret-token-value-999"


def test_whatsapp_webhook_validation_handshake(client):
    for event in ["connection.update", "webhook.test", "webhook.verify"]:
        payload = {"event": event}
        response = client.post("/api/v1/whatsapp/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert "Handshake verified" in data["message"]
