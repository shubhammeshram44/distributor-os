"""
Promise-to-pay tracking: detects payment promises in inbound WhatsApp replies
that don't look like new orders (e.g. "I'll pay by Friday"), records them,
and later checks whether they were actually kept.
"""
import logging
from datetime import date, datetime
from sqlalchemy.orm import Session

from app.models.payment_promise import PaymentPromise
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.services.gemini_service import GeminiService

logger = logging.getLogger("uvicorn.error")

_gemini_service_instance: GeminiService | None = None


def _get_gemini_service() -> GeminiService:
    global _gemini_service_instance
    if _gemini_service_instance is None:
        _gemini_service_instance = GeminiService()
    return _gemini_service_instance


def detect_and_record_promise(
    db: Session,
    tenant_id,
    customer: Customer,
    message_text: str,
) -> PaymentPromise | None:
    """
    Best-effort: extracts a payment promise from an inbound message and
    persists it if found. Returns the created PaymentPromise, or None if the
    message wasn't a promise (or extraction failed). Never raises — a failure
    here must never affect the caller's ability to process the inbound
    WhatsApp message otherwise.
    """
    try:
        extraction = _get_gemini_service().extract_payment_promise(message_text, datetime.utcnow())
        if not extraction.is_payment_promise or not extraction.promised_date:
            return None

        promised_date = date.fromisoformat(extraction.promised_date)

        promise = PaymentPromise(
            tenant_id=tenant_id,
            customer_id=customer.id,
            invoice_id=None,  # general promise; not tied to one specific invoice
            promised_date=promised_date,
            promised_amount=extraction.promised_amount,
            raw_message=message_text,
            status="pending",
        )
        db.add(promise)
        db.commit()
        db.refresh(promise)
        logger.info(
            "Payment promise recorded for customer %s: promised_date=%s amount=%s",
            customer.id, promised_date, extraction.promised_amount,
        )
        return promise
    except Exception as exc:
        logger.warning("Payment promise detection failed silently: %s", str(exc))
        db.rollback()
        return None


def refresh_promise_fulfillment(db: Session, tenant_id) -> dict:
    """
    For all "pending" promises whose promised_date has passed, mark them
    "fulfilled" if the customer's outstanding balance has since cleared (or
    the linked invoice, if any, is PAID), otherwise "broken".

    Returns a summary dict: {checked, fulfilled, broken}.
    """
    summary = {"checked": 0, "fulfilled": 0, "broken": 0}
    today = datetime.utcnow().date()

    pending_promises = (
        db.query(PaymentPromise)
        .filter(
            PaymentPromise.tenant_id == tenant_id,
            PaymentPromise.status == "pending",
            PaymentPromise.promised_date <= today,
        )
        .all()
    )

    for promise in pending_promises:
        summary["checked"] += 1

        if promise.invoice_id:
            invoice = db.get(Invoice, promise.invoice_id)
            fulfilled = bool(invoice and invoice.payment_status == "PAID")
        else:
            customer = db.get(Customer, promise.customer_id)
            fulfilled = bool(customer and float(customer.outstanding_balance or 0) <= 0)

        promise.status = "fulfilled" if fulfilled else "broken"
        summary["fulfilled" if fulfilled else "broken"] += 1

    db.commit()
    return summary
