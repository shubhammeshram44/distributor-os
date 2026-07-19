"""
Tests for promise-to-pay tracking: Gemini-based (and regex-fallback) promise
detection, persistence, fulfilment-check, and the customer payment-promises
endpoint.
"""
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import tenant_context
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.payment_promise import PaymentPromise
from app.services.gemini_service import GeminiService, PaymentPromiseExtraction
from app.services.payment_promise_service import detect_and_record_promise, refresh_promise_fulfillment
from app.services.ingestion_service import IngestionService

client = TestClient(app)


def test_regex_fallback_detects_tomorrow_promise():
    """The regex fallback parser should catch an unambiguous 'pay tomorrow'
    message, independent of whether Gemini is configured."""
    service = GeminiService(api_key=None)

    ref = datetime(2026, 7, 15)  # a Wednesday
    result = service._fallback_regex_promise_parser("I'll pay tomorrow for sure", ref)

    assert result.is_payment_promise is True
    assert result.promised_date == "2026-07-16"


def test_regex_fallback_detects_weekday_promise_with_amount():
    service = GeminiService(api_key=None)
    ref = datetime(2026, 7, 15)  # Wednesday
    result = service._fallback_regex_promise_parser("will clear rs 5000 by friday", ref)

    assert result.is_payment_promise is True
    assert result.promised_date == "2026-07-17"  # next Friday
    assert result.promised_amount == 5000.0


def test_regex_fallback_ignores_non_payment_messages():
    service = GeminiService(api_key=None)
    result = service._fallback_regex_promise_parser("Thanks, order received!", datetime.utcnow())
    assert result.is_payment_promise is False
    assert result.promised_date is None


def test_detect_and_record_promise_persists_row(db_session):
    tenant = DistributorTenant(name="Promise Detection Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    customer = Customer(
        tenant_id=tenant.id, retailer_name="Promise Kirana", customer_id="C-PROMISE",
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        phone_number="+919999888877",
    )
    db_session.add(customer)
    db_session.commit()

    # Force the deterministic regex fallback path rather than attempting a
    # real network call to Gemini with whatever key happens to be configured
    # in this environment (this matches typical CI, which has no real key).
    fallback_only_service = GeminiService(api_key=None)
    fallback_only_service.enabled = False
    with patch("app.services.payment_promise_service._get_gemini_service", return_value=fallback_only_service):
        promise = detect_and_record_promise(db_session, tenant.id, customer, "paisa kal de dunga")

    assert promise is not None
    assert promise.customer_id == customer.id
    assert promise.status == "pending"
    assert promise.raw_message == "paisa kal de dunga"

    stored = db_session.query(PaymentPromise).filter_by(customer_id=customer.id).one()
    assert stored.id == promise.id


def test_detect_and_record_promise_returns_none_for_non_promise(db_session):
    tenant = DistributorTenant(name="No Promise Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    customer = Customer(
        tenant_id=tenant.id, retailer_name="No Promise Kirana", customer_id="C-NOPROMISE",
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        phone_number="+919999888866",
    )
    db_session.add(customer)
    db_session.commit()

    fallback_only_service = GeminiService(api_key=None)
    fallback_only_service.enabled = False
    with patch("app.services.payment_promise_service._get_gemini_service", return_value=fallback_only_service):
        promise = detect_and_record_promise(db_session, tenant.id, customer, "Hi, how are you?")
    assert promise is None
    assert db_session.query(PaymentPromise).filter_by(customer_id=customer.id).first() is None


def test_refresh_promise_fulfillment_marks_fulfilled_and_broken(db_session):
    tenant = DistributorTenant(name="Fulfilment Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    paid_customer = Customer(
        tenant_id=tenant.id, retailer_name="Paid Up Kirana", customer_id="C-PAIDUP",
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        outstanding_balance=0.0,
    )
    unpaid_customer = Customer(
        tenant_id=tenant.id, retailer_name="Still Owing Kirana", customer_id="C-OWING",
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        outstanding_balance=500.0,
    )
    future_customer = Customer(
        tenant_id=tenant.id, retailer_name="Future Promise Kirana", customer_id="C-FUTURE",
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        outstanding_balance=500.0,
    )
    db_session.add_all([paid_customer, unpaid_customer, future_customer])
    db_session.flush()

    yesterday = date.today() - timedelta(days=1)
    tomorrow = date.today() + timedelta(days=1)

    fulfilled_promise = PaymentPromise(
        tenant_id=tenant.id, customer_id=paid_customer.id, invoice_id=None,
        promised_date=yesterday, promised_amount=None, raw_message="will pay", status="pending",
    )
    broken_promise = PaymentPromise(
        tenant_id=tenant.id, customer_id=unpaid_customer.id, invoice_id=None,
        promised_date=yesterday, promised_amount=None, raw_message="will pay", status="pending",
    )
    not_yet_due_promise = PaymentPromise(
        tenant_id=tenant.id, customer_id=future_customer.id, invoice_id=None,
        promised_date=tomorrow, promised_amount=None, raw_message="will pay later", status="pending",
    )
    db_session.add_all([fulfilled_promise, broken_promise, not_yet_due_promise])
    db_session.commit()

    summary = refresh_promise_fulfillment(db_session, tenant.id)

    assert summary["checked"] == 2  # only the two past-due promises
    assert summary["fulfilled"] == 1
    assert summary["broken"] == 1

    db_session.refresh(fulfilled_promise)
    db_session.refresh(broken_promise)
    db_session.refresh(not_yet_due_promise)
    assert fulfilled_promise.status == "fulfilled"
    assert broken_promise.status == "broken"
    assert not_yet_due_promise.status == "pending"  # untouched, not yet due


def test_customer_payment_promises_endpoint(db_session):
    tenant = DistributorTenant(name="Endpoint Promise Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    customer = Customer(
        tenant_id=tenant.id, retailer_name="Endpoint Kirana", customer_id="C-ENDPOINT",
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        outstanding_balance=0.0,
    )
    db_session.add(customer)
    db_session.flush()

    db_session.add(PaymentPromise(
        tenant_id=tenant.id, customer_id=customer.id, invoice_id=None,
        promised_date=date.today() - timedelta(days=1), promised_amount=1000.0,
        raw_message="will pay yesterday's promise", status="pending",
    ))
    db_session.commit()

    resp = client.get(f"/api/v1/customers/{customer.id}/payment-promises?tenant_id={tenant.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["resolved_count"] == 1
    assert data["fulfilled_count"] == 1  # outstanding_balance is 0 -> fulfilled
    assert data["items"][0]["status"] == "fulfilled"


def test_ingestion_records_promise_for_non_order_message_from_known_customer(db_session, setup_test_catalog):
    """A non-order reply from a whitelisted customer should be classified as
    non-order intent (Layer 4) and, if it's a payment promise, recorded --
    without ever creating an order."""
    intent_response = MagicMock()
    intent_response.text = '{"is_order": false}'

    mock_intent_model = MagicMock()
    mock_intent_model.generate_content.return_value = intent_response

    service = IngestionService()
    service.enabled = True  # force Layer 4 to actually run instead of bypassing

    fallback_only_service = GeminiService(api_key=None)
    fallback_only_service.enabled = False

    with patch("app.services.ingestion_service.genai.GenerativeModel", return_value=mock_intent_model), \
         patch("app.services.payment_promise_service._get_gemini_service", return_value=fallback_only_service):
        result = service.ingest_message(
            db=db_session,
            tenant_id=uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"),
            sender_phone="+919999888877",  # whitelisted alias from setup_test_catalog
            message_text="I'll pay tomorrow, sorry for the delay",
        )

    assert result["status"] == "ignored"
    assert result["reason"] == "non_order_intent"

    customer = db_session.query(Customer).filter_by(customer_id="CUST-1").first()
    promise = db_session.query(PaymentPromise).filter_by(customer_id=customer.id).first()
    assert promise is not None
    assert promise.status == "pending"
