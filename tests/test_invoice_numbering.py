"""
Regression test for ORD-9: generate_invoice_number() derives the next
sequential invoice number by counting existing rows for a tenant+financial-
year and incrementing -- a classic count-then-insert race. Under concurrent
order confirmations (or two reconciliation backfill runs) for the same
tenant, two transactions could compute the same number; the DB-level
unique index on (tenant_id, invoice_number) prevents a duplicate number
from ever actually being *persisted*, but previously the LOSING
transaction's plain db.add()+db.flush() would crash outright with an
unhandled IntegrityError -- an otherwise perfectly valid order confirmation
(credit check passed, stock already deducted) failing purely because of an
invoice-numbering collision unrelated to its own data.

create_invoice_with_unique_number() retries the generate-and-insert inside
a per-attempt SAVEPOINT, so a race resolves transparently instead of
crashing.
"""
import uuid
from datetime import datetime

from app.services import invoice_gst_utils
from app.models.invoice import Invoice
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.order import Order


def _seed_tenant_and_customer(db_session, name):
    tenant = DistributorTenant(name=name)
    db_session.add(tenant)
    db_session.commit()

    cust = Customer(
        tenant_id=tenant.id, retailer_name=f"{name} Store", customer_id=f"C-{name}",
        address_text="Address", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()
    return tenant, cust


def _seed_order(db_session, tenant, cust, suffix):
    order = Order(tenant_id=tenant.id, internal_order_id=f"ORD-{suffix}", source="Portal", customer_id=cust.id)
    db_session.add(order)
    db_session.flush()
    return order


def test_create_invoice_with_unique_number_retries_on_collision(db_session, monkeypatch):
    tenant, cust = _seed_tenant_and_customer(db_session, "InvRaceTenant")
    order_1 = _seed_order(db_session, tenant, cust, "InvRace1")
    order_2 = _seed_order(db_session, tenant, cust, "InvRace2")
    dt = datetime(2026, 6, 15)

    # Pre-seed an invoice that already claims the number the race below will
    # simulate colliding on (as if a concurrent transaction won it first).
    existing = Invoice(
        tenant_id=tenant.id, order_id=order_1.id, customer_id=cust.id, gstin="PENDING", total_amount=100.0,
        irn_status="NOT_APPLICABLE", qr_code_status="NOT_APPLICABLE", payment_status="UNPAID",
        amount_paid=0.0, created_at=dt, cgst_amount=9.0, sgst_amount=9.0,
        invoice_number="INV/2026-27/001",
    )
    db_session.add(existing)
    db_session.commit()

    call_count = {"n": 0}
    original_generate = invoice_gst_utils.generate_invoice_number

    def _colliding_then_correct(db, tenant_id, dt_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Simulate a stale count read: return the number that's already
            # taken instead of the genuinely-next one.
            return "INV/2026-27/001"
        return original_generate(db, tenant_id, dt_)

    monkeypatch.setattr(invoice_gst_utils, "generate_invoice_number", _colliding_then_correct)

    invoice = invoice_gst_utils.create_invoice_with_unique_number(
        db_session, tenant.id, dt,
        {
            "order_id": order_2.id, "customer_id": cust.id, "gstin": "PENDING", "total_amount": 200.0,
            "irn_status": "NOT_APPLICABLE", "qr_code_status": "NOT_APPLICABLE",
            "payment_status": "UNPAID", "amount_paid": 0.0, "created_at": dt,
            "cgst_amount": 18.0, "sgst_amount": 18.0,
        },
    )

    assert call_count["n"] >= 2, "must have retried at least once after the simulated collision"
    assert invoice.invoice_number != "INV/2026-27/001"

    db_session.commit()
    numbers = [
        i.invoice_number for i in
        db_session.query(Invoice).filter(Invoice.tenant_id == tenant.id).all()
    ]
    assert len(numbers) == len(set(numbers)), "must never end up with duplicate invoice numbers"


def test_plain_insert_without_retry_would_crash_on_the_same_collision(db_session):
    """
    Sanity check proving the premise: a plain db.add()+db.flush() (the OLD
    behavior, without create_invoice_with_unique_number's retry) genuinely
    raises IntegrityError on this exact collision -- confirming the retry
    wrapper is fixing a real, reproducible crash and not a hypothetical one.
    """
    from sqlalchemy.exc import IntegrityError
    import pytest

    tenant, cust = _seed_tenant_and_customer(db_session, "InvRaceCrashTenant")
    order_1 = _seed_order(db_session, tenant, cust, "InvRaceCrash1")
    order_2 = _seed_order(db_session, tenant, cust, "InvRaceCrash2")
    dt = datetime(2026, 6, 15)

    existing = Invoice(
        tenant_id=tenant.id, order_id=order_1.id, customer_id=cust.id, gstin="PENDING", total_amount=100.0,
        irn_status="NOT_APPLICABLE", qr_code_status="NOT_APPLICABLE", payment_status="UNPAID",
        amount_paid=0.0, created_at=dt, cgst_amount=9.0, sgst_amount=9.0,
        invoice_number="INV/2026-27/001",
    )
    db_session.add(existing)
    db_session.commit()

    duplicate = Invoice(
        tenant_id=tenant.id, order_id=order_2.id, customer_id=cust.id, gstin="PENDING", total_amount=200.0,
        irn_status="NOT_APPLICABLE", qr_code_status="NOT_APPLICABLE", payment_status="UNPAID",
        amount_paid=0.0, created_at=dt, cgst_amount=18.0, sgst_amount=18.0,
        invoice_number="INV/2026-27/001",
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
