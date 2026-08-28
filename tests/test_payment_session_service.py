"""
Regression tests for PAY-3 and PAY-4 in app/services/payment_session_service.py.
"""
import uuid
from unittest.mock import patch
import pytest
from datetime import datetime, timedelta

from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.order import Order
from app.models.invoice import Invoice
from app.models.payment_session import PaymentSession
from app.services.payment_session_service import get_or_create_payment_session
from app.utils.encryption import encrypt_secret


def _setup_tenant_customer_order_invoice(db_session, total_amount=1000.0, amount_paid=0.0, payment_status="UNPAID"):
    tenant = DistributorTenant(
        name="Payment Session Test Tenant",
        razorpay_key_id="rzp_test_key123",
        razorpay_key_secret_enc=encrypt_secret("secret123")
    )
    db_session.add(tenant)
    db_session.flush()

    cust = Customer(
        tenant_id=tenant.id, retailer_name="Payment Session Retailer", customer_id="C-PAYSESSION-1",
        tax_group="GST", payment_terms="Net 15", credit_limit=10000.0, outstanding_balance=total_amount,
        phone_number="+919876500099"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(tenant_id=tenant.id, internal_order_id="ORD-PAYSESSION-1", source="Portal", customer_id=cust.id, status="Confirmed")
    db_session.add(order)
    db_session.flush()

    invoice = Invoice(
        tenant_id=tenant.id, order_id=order.id, customer_id=cust.id, gstin="29AAAAA1111A1Z1",
        total_amount=total_amount, payment_status=payment_status, amount_paid=amount_paid
    )
    db_session.add(invoice)
    db_session.commit()

    return tenant, cust, order, invoice


def test_stale_session_regenerated_when_invoice_partially_paid_elsewhere(db_session):
    """
    Regression test for PAY-3: the staleness check previously only fired
    when custom_amount was explicitly passed -- but the two live callers
    (GET /payment-link, and the pay_invoice branch of /payment-options)
    never pass it, so an existing ACTIVE session's stored amount was
    trusted forever regardless of what the invoice actually still owes.
    This proves that if the invoice gets partially paid down through a
    DIFFERENT channel after the session was created, a fresh call (still
    with no custom_amount) detects the mismatch and regenerates the link
    with the correct, lower amount -- not the stale original amount.
    """
    tenant, cust, order, invoice = _setup_tenant_customer_order_invoice(db_session, total_amount=1000.0, amount_paid=0.0)

    fake_response_1 = {"id": "plink_original", "short_url": "https://rzp.io/original", "status": "created"}
    with patch("app.services.payment_gateway.PaymentGateway.create_payment_link", return_value=fake_response_1):
        session1 = get_or_create_payment_session(
            db=db_session, invoice=invoice, customer=cust, order_id=order.id, tenant_id=tenant.id
        )
    assert session1.amount == 1000.0
    assert session1.razorpay_payment_link_id == "plink_original"

    # Invoice gets partially paid down through a different channel (e.g. a
    # cash voucher recorded separately) -- the session itself is untouched.
    invoice.amount_paid = 400.0
    invoice.payment_status = "PARTIALLY_PAID"
    db_session.commit()

    fake_response_2 = {"id": "plink_refreshed", "short_url": "https://rzp.io/refreshed", "status": "created"}
    with patch("app.services.payment_gateway.PaymentGateway.create_payment_link", return_value=fake_response_2):
        session2 = get_or_create_payment_session(
            db=db_session, invoice=invoice, customer=cust, order_id=order.id, tenant_id=tenant.id
        )

    assert session2.amount == 600.0, "Must regenerate with the correct remaining amount, not the stale 1000.0"
    assert session2.razorpay_payment_link_id == "plink_refreshed"

    # Fix for PAY-4: this must be the SAME row updated in place, not a
    # second row -- payment_sessions.invoice_id has a hard unique
    # constraint (one session per invoice).
    assert session2.id == session1.id
    session_count = db_session.query(PaymentSession).filter(PaymentSession.invoice_id == invoice.id).count()
    assert session_count == 1, "Regenerating a session must update the existing row, not insert a second one"


def test_fully_settled_invoice_returns_none_not_stale_session(db_session):
    """
    Regression test for PAY-3: if the invoice becomes fully settled through
    a different channel after an ACTIVE session was created, the stale
    session (still quoting the original, now-wrong amount) must not be
    returned at all -- there's nothing left to pay.
    """
    tenant, cust, order, invoice = _setup_tenant_customer_order_invoice(db_session, total_amount=1000.0, amount_paid=0.0)

    fake_response = {"id": "plink_settle_test", "short_url": "https://rzp.io/settletest", "status": "created"}
    with patch("app.services.payment_gateway.PaymentGateway.create_payment_link", return_value=fake_response):
        session1 = get_or_create_payment_session(
            db=db_session, invoice=invoice, customer=cust, order_id=order.id, tenant_id=tenant.id
        )
    assert session1 is not None

    # Invoice becomes fully paid through a different channel.
    invoice.amount_paid = 1000.0
    invoice.payment_status = "PAID"
    db_session.commit()

    result = get_or_create_payment_session(
        db=db_session, invoice=invoice, customer=cust, order_id=order.id, tenant_id=tenant.id
    )
    assert result is None, "A fully-settled invoice must not return a stale (or any) payment session"

    db_session.expire_all()
    refreshed_session = db_session.get(PaymentSession, session1.id)
    assert refreshed_session.status == "EXPIRED"


def test_session_regeneration_survives_repeated_amount_changes(db_session):
    """
    Regression test for PAY-4: repeatedly regenerating a session (amount
    changing each time, e.g. outstanding balance shifting between calls)
    must never raise IntegrityError / PendingRollbackError -- each call
    updates the same row in place.
    """
    tenant, cust, order, invoice = _setup_tenant_customer_order_invoice(db_session, total_amount=2000.0, amount_paid=0.0)

    amounts_and_links = [
        (1500.0, "plink_a"),
        (1800.0, "plink_b"),
        (1200.0, "plink_c"),
    ]
    last_session_id = None
    for custom_amount, link_id in amounts_and_links:
        fake_response = {"id": link_id, "short_url": f"https://rzp.io/{link_id}", "status": "created"}
        with patch("app.services.payment_gateway.PaymentGateway.create_payment_link", return_value=fake_response):
            session = get_or_create_payment_session(
                db=db_session, invoice=invoice, customer=cust, order_id=order.id,
                tenant_id=tenant.id, custom_amount=custom_amount
            )
        assert session is not None
        assert session.amount == custom_amount
        assert session.razorpay_payment_link_id == link_id
        if last_session_id is not None:
            assert session.id == last_session_id
        last_session_id = session.id

    session_count = db_session.query(PaymentSession).filter(PaymentSession.invoice_id == invoice.id).count()
    assert session_count == 1
