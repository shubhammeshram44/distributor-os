import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product, ProductAlias
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.ingestion import IngestionJob, IngestionStaging
from app.services.whatsapp_service import WhatsAppService
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_whatsapp_ingestion_success(db_session):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Tata Distributors Ltd")
    db_session.add(tenant)
    db_session.commit()

    # Bind active tenant context
    tenant_context.set(tenant.id)

    # 2. Setup Customer with WhatsApp Phone Alias
    customer = Customer(
        retailer_name="Aggarwal Kirana Store",
        customer_id="CUST-101",
        address_text="Shop 14, Sector 5, Rohini, Delhi",
        gstin="07AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="Net 15"
    )
    db_session.add(customer)
    db_session.flush()

    cust_alias = CustomerAlias(
        customer_id=customer.id,
        alias_value="+919999888877"
    )
    db_session.add(cust_alias)

    # 3. Setup Products and their Aliases
    p1 = Product(sku_id="PROD-HUL-SOAP", brand="HUL", category="Soap", pack_size="100g", base_price=45.00)
    p2 = Product(sku_id="PROD-ITC-AATA", brand="ITC", category="Flour", pack_size="5kg", base_price=260.00)
    db_session.add_all([p1, p2])
    db_session.flush()

    alias_soap = ProductAlias(product_id=p1.id, alias_name="HUL Soap")
    alias_aata = ProductAlias(product_id=p2.id, alias_name="ITC Aashirvaad Aata")
    db_session.add_all([alias_soap, alias_aata])
    db_session.commit()

    # 4. Trigger WhatsApp Ingestion
    service = WhatsAppService()
    message = "Bhaiya, please send 50 HUL Soap and 12 ITC Aashirvaad Aata immediately"
    
    job = service.process_whatsapp_message(
        db=db_session,
        tenant_id=tenant.id,
        phone_number="+919999888877",
        message_text=message
    )

    # 5. Assertions on Ingestion Job
    assert job.status == "Completed"
    assert job.successful_rows == 1
    assert job.failed_rows == 0

    # Assertions on Staging
    staging = db_session.query(IngestionStaging).filter_by(job_id=job.id).one()
    assert staging.status == "Validated"
    assert staging.error_message is None

    # Assertions on Canonical Tables (Order & Ledger)
    orders = db_session.query(Order).all()
    assert len(orders) == 1
    order = orders[0]
    assert order.source == "WhatsApp"
    assert order.customer_id == customer.id
    # Check current status dynamic property
    assert order.current_status == "Draft"

    # Verify line items
    items = db_session.query(OrderLineItem).filter_by(order_id=order.id).all()
    assert len(items) == 2
    
    soap_item = next(it for it in items if it.product_id == p1.id)
    assert soap_item.quantity == 50
    assert float(soap_item.unit_price) == 45.00

    aata_item = next(it for it in items if it.product_id == p2.id)
    assert aata_item.quantity == 12
    assert float(aata_item.unit_price) == 260.00

    # Verify state ledger entry
    ledger_entries = db_session.query(OrderStateLedger).filter_by(order_id=order.id).all()
    assert len(ledger_entries) == 1
    ledger = ledger_entries[0]
    assert ledger.from_status is None
    assert ledger.to_status == "Draft"
    assert ledger.updated_by == "system_whatsapp_agent"


def test_whatsapp_ingestion_unknown_customer(db_session):
    # Setup Tenant
    tenant = DistributorTenant(name="Tata Distributors Ltd")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product only
    p1 = Product(sku_id="PROD-HUL-SOAP", brand="HUL", category="Soap", pack_size="100g", base_price=45.00)
    db_session.add(p1)
    db_session.flush()
    alias_soap = ProductAlias(product_id=p1.id, alias_name="HUL Soap")
    db_session.add(alias_soap)
    db_session.commit()

    # Call with unregistered phone number
    service = WhatsAppService()
    job = service.process_whatsapp_message(
        db=db_session,
        tenant_id=tenant.id,
        phone_number="+910000000000",  # Unknown
        message_text="Need 50 HUL Soap"
    )

    # Check status
    assert job.status == "Completed"
    assert job.successful_rows == 0
    assert job.failed_rows == 1

    # Check staging error
    staging = db_session.query(IngestionStaging).filter_by(job_id=job.id).one()
    assert staging.status == "Failed"
    assert "Unknown customer phone number" in staging.error_message

    # Ensure no Order was generated
    assert db_session.query(Order).count() == 0


def test_whatsapp_ingestion_unmapped_product(db_session):
    # Setup Tenant
    tenant = DistributorTenant(name="Tata Distributors Ltd")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Customer
    customer = Customer(
        retailer_name="Aggarwal Kirana Store",
        customer_id="CUST-101",
        address_text="Shop 14, Sector 5, Rohini, Delhi",
        gstin="07AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="Net 15"
    )
    db_session.add(customer)
    db_session.flush()
    cust_alias = CustomerAlias(customer_id=customer.id, alias_value="+919999888877")
    db_session.add(cust_alias)
    db_session.commit()

    # Call with message referencing unknown product SKU
    service = WhatsAppService()
    job = service.process_whatsapp_message(
        db=db_session,
        tenant_id=tenant.id,
        phone_number="+919999888877",
        message_text="Send 10 boxes of Nestle Maggi"  # "Nestle Maggi" is unmapped
    )

    assert job.status == "Completed"
    assert job.successful_rows == 0
    assert job.failed_rows == 1

    staging = db_session.query(IngestionStaging).filter_by(job_id=job.id).one()
    assert staging.status == "Failed"
    assert "Unmapped product aliases" in staging.error_message
    assert "maggi" in staging.error_message.lower()

    # Verify no order is created
    assert db_session.query(Order).count() == 0


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


def test_whatsapp_webhook_dynamic_routing(db_session, client):
    # 1. Setup Tenant with custom phone ID
    tenant = DistributorTenant(name="Dynamic Routing Tenant", whatsapp_phone_id="bot-phone-555")
    db_session.add(tenant)
    db_session.commit()
    
    # Setup Customer
    customer = Customer(
        tenant_id=tenant.id,
        retailer_name="Dynamic Retailer",
        customer_id="CUST-DYN",
        address_text="Delhi",
        gstin="07AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="Net 15"
    )
    db_session.add(customer)
    db_session.flush()
    
    alias = CustomerAlias(tenant_id=tenant.id, customer_id=customer.id, alias_value="+919999888877")
    db_session.add(alias)
    
    product = Product(tenant_id=tenant.id, sku_id="PROD-HUL-SOAP", brand="HUL", category="Soap", pack_size="100g", base_price=45.00)
    db_session.add(product)
    db_session.flush()
    
    prod_alias = ProductAlias(tenant_id=tenant.id, product_id=product.id, alias_name="HUL Soap")
    db_session.add(prod_alias)
    db_session.commit()


    # 2. Trigger webhook with Meta payload containing bot_phone_id
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15555555555",
                                "phone_number_id": "bot-phone-555"
                            },
                            "contacts": [
                                {
                                    "profile": { "name": "Dynamic Retailer" },
                                    "wa_id": "919999888877"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919999888877",
                                    "id": "wamid.id123",
                                    "timestamp": "1718873099",
                                    "text": { "body": "Need 50 HUL Soap" },
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    # Verify order is routed to Dynamic Routing Tenant
    order = db_session.query(Order).filter_by(customer_id=customer.id).first()
    assert order is not None
    assert order.tenant_id == tenant.id


def test_whatsapp_webhook_dynamic_routing_unmapped_dropped(db_session, client):
    # 1. Trigger webhook with unmapped phone ID and no explicit tenant ID
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15555555555",
                                "phone_number_id": "bot-phone-unmapped"
                            },
                            "contacts": [
                                {
                                    "profile": { "name": "Dynamic Retailer" },
                                    "wa_id": "919999888877"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919999888877",
                                    "id": "wamid.id123",
                                    "timestamp": "1718873099",
                                    "text": { "body": "Need 50 HUL Soap" },
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert "No tenant found for phone_number_id" in data["message"]


def test_whatsapp_outgoing_adapter_mocked(db_session, monkeypatch):
    from app.services.whatsapp_adapter import send_whatsapp_message
    
    # Setup Tenant with custom credentials
    tenant = DistributorTenant(
        name="Adapter Test Tenant",
        whatsapp_phone_id="phone-id-99",
        whatsapp_access_token="token-99"
    )
    db_session.add(tenant)
    db_session.commit()
    
    # Mock requests.post to capture the call details
    called_url = None
    called_headers = None
    called_json = None
    
    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"messaging_product": "whatsapp", "messages": [{"id": "wamid.test"}]}

    def mock_post(url, json, headers, timeout):
        nonlocal called_url, called_headers, called_json
        called_url = url
        called_headers = headers
        called_json = json
        return MockResponse()

    import requests
    monkeypatch.setattr(requests, "post", mock_post)
    
    res = send_whatsapp_message(
        db=db_session,
        tenant_id=tenant.id,
        to_phone="+919999999999",
        message_text="Hello adapter test"
    )
    
    assert res == {"messaging_product": "whatsapp", "messages": [{"id": "wamid.test"}]}
    assert called_url == "https://graph.facebook.com/v18.0/phone-id-99/messages"
    assert called_headers["Authorization"] == "Bearer token-99"
    assert called_json["to"] == "+919999999999"
    assert called_json["text"]["body"] == "Hello adapter test"


