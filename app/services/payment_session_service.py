import logging
from sqlalchemy.orm import Session
from app.models.payment_session import PaymentSession
from app.models.invoice import Invoice
from app.models.customer import Customer
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
    # Check for existing active session
    existing = db.query(PaymentSession).filter(
        PaymentSession.invoice_id == invoice.id,
        PaymentSession.status == "ACTIVE"
    ).first()
    
    if existing:
        # Check if amount matches if custom_amount is passed
        amount_mismatch = False
        if custom_amount is not None:
            amount_mismatch = abs(float(existing.amount) - custom_amount) > 0.01

        # Check if link is still valid (not expired) and amount matches
        if not amount_mismatch and existing.payment_link_expires_at and existing.payment_link_expires_at > datetime.utcnow():
            return existing
        else:
            # Mark expired
            existing.status = "EXPIRED"
            db.flush()
    
    # Razorpay test mode limit is ₹5,00,000
    # In production with live keys this limit is much higher
    RAZORPAY_TEST_MAX_AMOUNT = 499999.0

    amount_due = custom_amount if custom_amount is not None else (float(invoice.total_amount) - float(invoice.amount_paid or 0))
    if amount_due <= 0:
        logger.warning("PaymentSession skipped: zero or negative amount_due for invoice %s", invoice.id)
        return None  # caller must handle None

    amount_due = min(amount_due, RAZORPAY_TEST_MAX_AMOUNT)

    # Create new payment link via Razorpay
    gateway = PaymentGateway()
    
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
