import logging
from sqlalchemy.orm import Session
from app.models.payment_session import PaymentSession
from app.models.invoice import Invoice
from app.models.customer import Customer
from app.models.tenant import DistributorTenant
from app.utils.encryption import decrypt_secret
from app.services.payment_gateway import PaymentGateway
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger("uvicorn.error")

def get_or_create_payment_session(
    db: Session,
    invoice: Invoice,
    customer: Customer,
    order_id: uuid.UUID,
    tenant_id: uuid.UUID,
    custom_amount: float | None = None  # NEW
) -> PaymentSession | None:
    """
    Returns existing ACTIVE session if valid link exists and amount matches.
    Creates new session + Razorpay link if none exists, amount differs, or link is expired.
    This is the single entry point for all payment link generation.
    """
    # Razorpay test mode limit is ₹5,00,000
    # In production with live keys this limit is much higher
    RAZORPAY_TEST_MAX_AMOUNT = 499999.0

    # Fix for PAY-3: compute the CURRENT correct amount_due up front (from
    # live invoice state) regardless of whether custom_amount was passed,
    # so a stale existing session can be detected even when the caller
    # didn't explicitly ask for a specific amount. Previously the
    # staleness check only ever fired when custom_amount was explicitly
    # supplied, but the two live callers of get_payment_link/pay_invoice
    # never pass it -- meaning an invoice that was partially/fully paid
    # down elsewhere since the session was created kept returning the
    # OLD, now-wrong amount indefinitely (or, if fully settled, a payment
    # link for an invoice that no longer owes anything at all).
    current_amount_due = custom_amount if custom_amount is not None else (
        float(invoice.total_amount) - float(invoice.amount_paid or 0)
    )

    # Check for existing active session
    existing = db.query(PaymentSession).filter(
        PaymentSession.invoice_id == invoice.id,
        PaymentSession.status == "ACTIVE"
    ).first()

    if existing:
        amount_mismatch = abs(float(existing.amount) - current_amount_due) > 0.01
        is_settled = current_amount_due <= 0

        # Check if link is still valid (not expired), amount matches, and
        # the invoice hasn't been settled out from under this session.
        if not amount_mismatch and not is_settled and existing.payment_link_expires_at and existing.payment_link_expires_at > datetime.utcnow():
            return existing

        # Fix for PAY-4: previously this marked the old row EXPIRED and
        # then INSERTed a brand-new PaymentSession row further down --
        # but payment_sessions.invoice_id has a hard, global UNIQUE
        # constraint (one session per invoice, by design), so that insert
        # always failed with IntegrityError whenever a session actually
        # needed regenerating (e.g. the amount changed). The two callers'
        # exception-handling fallback queries then also failed with
        # PendingRollbackError, since the session's transaction was never
        # rolled back after the failed insert -- surfacing as an
        # unhandled 500 on every regeneration, not just an edge case.
        # Fix: UPDATE this same row in place instead of expiring +
        # inserting a second one -- a payment session has a natural 1:1
        # relationship with its invoice (that's exactly what the unique
        # constraint enforces), so regeneration should mean "replace this
        # session's Razorpay link/amount/expiry", not "create a second
        # session for the same invoice".
        if is_settled:
            existing.status = "EXPIRED"
            db.flush()
            logger.info("PaymentSession expired (invoice %s settled, no regeneration needed)", invoice.id)
            return None
        return _refresh_payment_session_in_place(
            db, existing, invoice, customer, tenant_id, current_amount_due, RAZORPAY_TEST_MAX_AMOUNT
        )

    amount_due = current_amount_due
    if amount_due <= 0:
        logger.warning("PaymentSession skipped: zero or negative amount_due for invoice %s", invoice.id)
        return None  # caller must handle None

    amount_due = min(amount_due, RAZORPAY_TEST_MAX_AMOUNT)

    # Fetch tenant keys before instantiating
    tenant = db.get(DistributorTenant, tenant_id)
    if not tenant or not tenant.razorpay_key_id or not tenant.razorpay_key_secret_enc:
        raise ValueError(
            "Razorpay not connected. Please connect your Razorpay account in Settings → Payments."
        )

    gateway = PaymentGateway(
        key_id=tenant.razorpay_key_id,
        key_secret=decrypt_secret(tenant.razorpay_key_secret_enc)
    )
    
    expire_by = int((datetime.utcnow() + timedelta(days=7)).timestamp())
    
    # Clean phone number (remove leading + if exists)
    phone = customer.phone_number or ""
    if phone.startswith("+"):
        phone = phone[1:]
        
    result = gateway.create_payment_link(
        amount_inr=amount_due,
        customer_name=customer.retailer_name,
        customer_phone=phone,
        customer_email=None,
        description=f"Payment for Invoice {invoice.id}",
        reference_id=str(invoice.id),
        expire_by_unix=expire_by
    )
    
    session = PaymentSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        invoice_id=invoice.id,
        customer_id=customer.id,
        order_id=order_id,
        razorpay_payment_link_id=result["id"],
        payment_link_url=result.get("short_url") or result.get("url"),
        payment_link_short_url=result.get("short_url"),
        payment_link_expires_at=datetime.utcfromtimestamp(expire_by),
        status="ACTIVE",
        amount=amount_due
    )
    db.add(session)
    db.flush()
    return session


def _refresh_payment_session_in_place(
    db: Session,
    existing: PaymentSession,
    invoice: Invoice,
    customer: Customer,
    tenant_id: uuid.UUID,
    amount_due: float,
    max_amount: float,
) -> PaymentSession:
    """
    Regenerates the Razorpay payment link for an already-existing
    PaymentSession row and updates it in place (see PAY-4 for why this must
    not insert a second row for the same invoice).
    """
    amount_due = min(amount_due, max_amount)

    tenant = db.get(DistributorTenant, tenant_id)
    if not tenant or not tenant.razorpay_key_id or not tenant.razorpay_key_secret_enc:
        raise ValueError(
            "Razorpay not connected. Please connect your Razorpay account in Settings → Payments."
        )

    gateway = PaymentGateway(
        key_id=tenant.razorpay_key_id,
        key_secret=decrypt_secret(tenant.razorpay_key_secret_enc)
    )

    expire_by = int((datetime.utcnow() + timedelta(days=7)).timestamp())

    phone = customer.phone_number or ""
    if phone.startswith("+"):
        phone = phone[1:]

    result = gateway.create_payment_link(
        amount_inr=amount_due,
        customer_name=customer.retailer_name,
        customer_phone=phone,
        customer_email=None,
        description=f"Payment for Invoice {invoice.id}",
        reference_id=str(invoice.id),
        expire_by_unix=expire_by
    )

    existing.razorpay_payment_link_id = result["id"]
    existing.payment_link_url = result.get("short_url") or result.get("url")
    existing.payment_link_short_url = result.get("short_url")
    existing.payment_link_expires_at = datetime.utcfromtimestamp(expire_by)
    existing.status = "ACTIVE"
    existing.amount = amount_due
    db.flush()
    return existing
