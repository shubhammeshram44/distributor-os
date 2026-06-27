import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.models.customer import Customer, CustomerAlias
from app.models.order import Order
from app.models.tenant import DistributorTenant
from app.utils.phone import normalize_phone_number
from app.services.whatsapp_adapter import adapt_to_canonical, CanonicalWhatsAppMessage
from app.api.v1.whatsapp import WebhookPayload

client = TestClient(app)

def test_phone_normalization():
    # 10 digits
    assert normalize_phone_number("9876543210") == "+919876543210"
    # 12 digits starting with 91
    assert normalize_phone_number("919876543210") == "+919876543210"
    # Already E.164
    assert normalize_phone_number("+919876543210") == "+919876543210"
    # Formatting characters
    assert normalize_phone_number("+91 (987) 654-3210") == "+919876543210"
    # Fallbacks / empty
    assert normalize_phone_number("") == ""

def test_model_write_normalization(db_session):
    # Retrieve tenant
    tenant = db_session.query(DistributorTenant).first()
    if not tenant:
        tenant = DistributorTenant(id=uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"), name="Test Tenant")
        db_session.add(tenant)
        db_session.commit()

    # Create customer with unnormalized phone
    customer = Customer(
        tenant_id=tenant.id,
        customer_id="CUST-NORM-1",
        retailer_name="Norm Retailer",
        phone_number="9999888877"
    )
    db_session.add(customer)
    db_session.flush()

    # Verify normalization on insert
    assert customer.phone_number == "+919999888877"

    # Create alias with unnormalized value
    alias = CustomerAlias(
        tenant_id=tenant.id,
        customer_id=customer.id,
        alias_value=" 919999888877 "
    )
    db_session.add(alias)
    db_session.flush()

    # Verify alias normalization
    assert alias.alias_value == "+919999888877"

    # Verify update triggers validation
    customer.phone_number = "918888888888"
    db_session.flush()
    assert customer.phone_number == "+918888888888"

    db_session.rollback()

def test_adapter_flat_and_nested():
    # 1. Flat WebhookPayload
    flat_payload = WebhookPayload(
        tenant_id=uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"),
        sender_phone="+919999888877",
        message_text="Need 10 boxes of HUL Soap"
    )
    canonical_flat = adapt_to_canonical(flat_payload)
    assert canonical_flat.tenant_id == uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    assert canonical_flat.sender_phone == "+919999888877"
    assert canonical_flat.message_text == "Need 10 boxes of HUL Soap"

    # 2. Nested Meta/Simulator Dict Payload
    nested_payload = {
        "tenant_id": "d3b07384-d113-4956-a5d2-64be7357c11d",
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15555555555",
                                "phone_number_id": "PN_ID"
                            },
                            "contacts": [
                                {
                                    "profile": { "name": "Kaveri Provision Store" },
                                    "wa_id": "919999888877"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919999888877",
                                    "id": "wamid.id",
                                    "timestamp": "123456789",
                                    "text": { "body": "Bhaiya, send 10 cases of Britannia Marie Gold" },
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

    canonical_nested = adapt_to_canonical(nested_payload)
    assert canonical_nested.tenant_id == uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    assert canonical_nested.sender_phone == "919999888877"
    assert canonical_nested.message_text == "Bhaiya, send 10 cases of Britannia Marie Gold"
    assert canonical_nested.receiver_phone == "15555555555"

def test_webhook_nested_simulator_ingestion(db_session, setup_test_catalog):
    # Ensure client-side phone aliases exist in db with standard +91 prefix
    customer = db_session.query(Customer).filter_by(customer_id="CUST-1").first()
    assert customer is not None

    nested_payload = {
        "tenant_id": "d3b07384-d113-4956-a5d2-64be7357c11d",
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
                                "phone_number_id": "BUSINESS_PHONE_NUMBER_ID"
                            },
                            "contacts": [
                                {
                                    "profile": { "name": "Kaveri Provision Store" },
                                    "wa_id": "919999888877"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919999888877",
                                    "id": "wamid.HBgLOTE5OTk5ODg4ODc3FQIAERgSQjRDQzhCQzNDQzRFQzVGMDVCAA==",
                                    "timestamp": "1718873099",
                                    "text": { "body": "Bhaiya, send 10 cases of PatanjaliDantKanti" },
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

    # Fire the webhook simulator
    response = client.post("/api/v1/whatsapp/webhook", json=nested_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["successful_rows"] == 1

    # Verify order is committed to DB
    order = db_session.query(Order).filter(Order.customer_id == customer.id).first()
    assert order is not None
    assert order.source == "WhatsApp"

    # Query Orders list API to verify presence
    orders_resp = client.get(f"/api/v1/orders?tenant_id=d3b07384-d113-4956-a5d2-64be7357c11d")
    assert orders_resp.status_code == 200
    orders_list = orders_resp.json()
    assert len(orders_list) > 0
    assert any(o["order_id"] == order.internal_order_id for o in orders_list)

    # Query Dashboard recent orders API
    dashboard_resp = client.get(f"/api/v1/dashboard/recent-orders?tenant_id=d3b07384-d113-4956-a5d2-64be7357c11d")
    assert dashboard_resp.status_code == 200
    recent_list = dashboard_resp.json()
    assert len(recent_list) > 0
    assert any(o["order_id"] == order.internal_order_id for o in recent_list)


def test_phone_variants_matching(db_session, setup_test_catalog):
    # 1. Verify get_phone_number_variants outputs correctly
    from app.utils.phone import get_phone_number_variants
    assert "9999111122" in get_phone_number_variants("+919999111122")
    assert "919999111122" in get_phone_number_variants("+919999111122")
    assert "+919999111122" in get_phone_number_variants("9999111122")

    # 2. Verify that a webhook call with a raw 10-digit number matches Kaveri Provision Store (alias "+919999888877")
    response = client.post("/api/v1/whatsapp/webhook", json={
        "tenant_id": "d3b07384-d113-4956-a5d2-64be7357c11d",
        "phone_number": "9999888877",  # Send 10 digits
        "message_text": "Bhaiya, send 10 cases of PatanjaliDantKanti"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_conversational_invoice_preference_extraction(db_session, setup_test_catalog):
    # Setup / Webhook call for RETAIL_INVOICE
    response = client.post("/api/v1/whatsapp/webhook", json={
        "tenant_id": "d3b07384-d113-4956-a5d2-64be7357c11d",
        "phone_number": "9999888877",
        "message_text": "Maggi 50 cases urgent, bina GST bill ke bhej do"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    orders = db_session.query(Order).filter(
        Order.tenant_id == uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    ).order_by(Order.created_at.desc()).all()
    
    retail_order = None
    for o in orders:
        if o.invoice_type == "RETAIL_INVOICE":
            retail_order = o
            break
    assert retail_order is not None

    # Setup / Webhook call for GST_TAX_INVOICE
    response = client.post("/api/v1/whatsapp/webhook", json={
        "tenant_id": "d3b07384-d113-4956-a5d2-64be7357c11d",
        "phone_number": "9999888877",
        "message_text": "Stayfree 100 boxes, full tax GST invoice lagana"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    orders = db_session.query(Order).filter(
        Order.tenant_id == uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    ).order_by(Order.created_at.desc()).all()

    gst_order = None
    for o in orders:
        if o.invoice_type == "GST_TAX_INVOICE":
            gst_order = o
            break
    assert gst_order is not None

    # Setup / Webhook call for GST_TAX_INVOICE via "Company ka bill"
    response = client.post("/api/v1/whatsapp/webhook", json={
        "tenant_id": "d3b07384-d113-4956-a5d2-64be7357c11d",
        "phone_number": "9999888877",
        "message_text": "Stayfree 100 boxes, Company ka bill bhej dena"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    orders = db_session.query(Order).filter(
        Order.tenant_id == uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    ).order_by(Order.created_at.desc()).all()

    company_bill_order = None
    for o in orders:
        if o.invoice_type == "GST_TAX_INVOICE":
            company_bill_order = o
            break
    assert company_bill_order is not None

    # Setup / Webhook call for GST_TAX_INVOICE via "GST number"
    response = client.post("/api/v1/whatsapp/webhook", json={
        "tenant_id": "d3b07384-d113-4956-a5d2-64be7357c11d",
        "phone_number": "9999888877",
        "message_text": "Maggi 50 cases, standard GST number bill lagana"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    orders = db_session.query(Order).filter(
        Order.tenant_id == uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    ).order_by(Order.created_at.desc()).all()

    gst_num_order = None
    for o in orders:
        if o.invoice_type == "GST_TAX_INVOICE":
            gst_num_order = o
            break
    assert gst_num_order is not None


