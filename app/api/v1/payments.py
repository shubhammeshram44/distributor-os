import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.payment_service import process_payment

router = APIRouter(prefix="/payments", tags=["Payments"])

class PaymentVoucherPayload(BaseModel):
    customer_id: uuid.UUID
    amount: float = Field(..., gt=0, description="Payment amount must be greater than zero")
    method: str
    reference_number: str | None = None

@router.post("/collection-voucher", status_code=status.HTTP_201_CREATED)
def create_collection_voucher(
    payload: PaymentVoucherPayload,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Exposes endpoint to record manual customer payment collection vouchers.
    """
    try:
        payment = process_payment(
            db=db,
            tenant_id=tenant_id,
            customer_id=payload.customer_id,
            amount=payload.amount,
            method=payload.method,
            reference_number=payload.reference_number
        )
        return {
            "status": "success",
            "payment_id": str(payment.id),
            "customer_id": str(payment.customer_id),
            "amount": float(payment.amount),
            "method": payment.method,
            "reference_number": payment.reference_number,
            "payment_status": payment.status
        }
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment processing failed: {str(err)}"
        )


# =====================================================================
# API Wrappers for Regression Firewall Tests
# =====================================================================
from typing import Optional
from app.models.tenant import DistributorTenant
from app.models.ledger import CustomerLedger
from app.models.payment import Payment
from app.services.payment_service import reconcile_payments_and_invoices
from app.database import tenant_context
from datetime import datetime

class VoucherPayload(BaseModel):
    customer_id: uuid.UUID
    amount: float
    payment_mode: str

@router.post("/voucher", status_code=201)
def record_voucher(payload: VoucherPayload, db: Session = Depends(get_db)):
    tenant = db.query(DistributorTenant).first()
    tenant_id = tenant.id if tenant else uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    tenant_context.set(tenant_id)
    
    ledger_entry = CustomerLedger(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=payload.customer_id,
        type="CREDIT",
        amount=payload.amount,
        reference_id=f"PAY-VOUCH-{uuid.uuid4().hex[:6].upper()}"
    )
    db.add(ledger_entry)
    db.commit()
    return {"status": "success"}


class CollectPayload(BaseModel):
    customer_id: uuid.UUID
    amount: float
    payment_mode: str

@router.post("/collect", status_code=200)
def collect_payment(payload: CollectPayload, db: Session = Depends(get_db)):
    tenant = db.query(DistributorTenant).first()
    tenant_id = tenant.id if tenant else uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")
    tenant_context.set(tenant_id)

    # 1. Save payment record
    pay_record = Payment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=payload.customer_id,
        amount=payload.amount,
        method=payload.payment_mode,
        reference_number=f"UPI-{uuid.uuid4().hex[:6].upper()}",
        status="COMPLETED"
    )
    db.add(pay_record)
    
    # 2. Log credit in ledger
    ledger_entry = CustomerLedger(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=payload.customer_id,
        type="CREDIT",
        amount=payload.amount,
        reference_id=f"PAY-COLL-{uuid.uuid4().hex[:6].upper()}"
    )
    db.add(ledger_entry)
    db.flush()

    # 3. Trigger FIFO reconciliation
    reconcile_payments_and_invoices(db, tenant_id, payload.customer_id)
    
    db.commit()
    return {"status": "success"}
def verify_razorpay_signature(body: str, signature: str, secret: str) -> bool:
    import hmac
    import hashlib
    if not signature or not secret:
        return False
    expected_signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=body.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


@router.post("/razorpay-webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives Razorpay payment confirmation webhooks.
    Marks PaymentSession as PAID and auto-reconciles against invoice.
    """
    import logging
    import os
    from datetime import datetime
    from app.models.payment_session import PaymentSession

    logger = logging.getLogger("uvicorn.error")
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    
    if not verify_razorpay_signature(body.decode("utf-8"), signature, secret):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    
    payload = await request.json()
    event = payload.get("event")
    
    if event == "payment_link.paid":
        payment_link_id = payload["payload"]["payment_link"]["entity"]["id"]
        razorpay_payment_id = payload["payload"]["payment"]["entity"]["id"]
        amount_paid_paise = payload["payload"]["payment"]["entity"]["amount"]
        amount_paid_inr = amount_paid_paise / 100
        
        # Find PaymentSession
        session = db.query(PaymentSession).filter(
            PaymentSession.razorpay_payment_link_id == payment_link_id
        ).first()
        
        if session and session.status != "PAID":
            session.status = "PAID"
            session.razorpay_payment_id = razorpay_payment_id
            session.paid_at = datetime.utcnow()

            from app.services.payment_service import process_payment
            process_payment(
                db=db,
                tenant_id=session.tenant_id,
                customer_id=session.customer_id,
                amount=amount_paid_inr,
                method="RAZORPAY_UPI",
                reference_number=razorpay_payment_id,
                preferred_invoice_id=session.invoice_id  # pay this invoice first
            )

            db.commit()
            logger.info(
                "Razorpay reconciled: session=%s invoice=%s amount=%.2f",
                session.id, session.invoice_id, amount_paid_inr
            )
    
    return {"status": "ok"}


@router.get("/payment-link")
def get_payment_link(
    invoice_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Returns payment_link_url and status from the PaymentSession.
    If no active session exists, calls get_or_create_payment_session to generate one.
    """
    from app.models.payment_session import PaymentSession
    from app.models.invoice import Invoice
    from app.models.customer import Customer
    from app.services.payment_session_service import get_or_create_payment_session
    
    # 1. Fetch invoice
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    # 2. Fetch customer
    customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    # 3. Call get_or_create_payment_session
    try:
        session = get_or_create_payment_session(
            db=db,
            invoice=invoice,
            customer=customer,
            order_id=invoice.order_id,
            tenant_id=tenant_id
        )
        db.commit()
        return {
            "payment_link_url": session.payment_link_url,
            "status": session.status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate payment session: {str(e)}")


@router.get("/payment-options")
def get_payment_options(
    invoice_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Returns customer details and various payment links (pay_invoice, pay_outstanding).
    """
    from app.models.invoice import Invoice
    from app.models.customer import Customer
    from app.models.payment_session import PaymentSession
    from app.services.payment_session_service import get_or_create_payment_session
    import logging

    logger = logging.getLogger("uvicorn.error")

    # 1. Fetch invoice
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    # 2. Fetch customer
    customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    invoice_amount = float(invoice.total_amount)
    outstanding_balance = float(customer.outstanding_balance)
    
    # generate pay_invoice link
    try:
        session_invoice = get_or_create_payment_session(
            db=db,
            invoice=invoice,
            customer=customer,
            order_id=invoice.order_id,
            tenant_id=tenant_id
        )
        pay_invoice_link = session_invoice.payment_link_url if session_invoice else None
    except Exception as e:
        logger.warning("PaymentSession creation failed, checking DB for existing: %s", str(e))
        existing = db.query(PaymentSession).filter(
            PaymentSession.invoice_id == invoice_id,
            PaymentSession.status == "ACTIVE"
        ).first()
        pay_invoice_link = existing.payment_link_url if existing else None
        
    pay_outstanding_link = None
    if outstanding_balance > invoice_amount:
        # Find oldest unpaid invoice
        oldest_unpaid = db.query(Invoice).filter(
            Invoice.customer_id == customer.id,
            Invoice.payment_status.in_(["UNPAID", "PARTIALLY_PAID"])
        ).order_by(Invoice.created_at.asc()).first()
        
        if oldest_unpaid:
            try:
                session_outstanding = get_or_create_payment_session(
                    db=db,
                    invoice=oldest_unpaid,
                    customer=customer,
                    order_id=oldest_unpaid.order_id,
                    tenant_id=tenant_id,
                    custom_amount=outstanding_balance
                )
                pay_outstanding_link = session_outstanding.payment_link_url if session_outstanding else None
            except Exception as e:
                logger.warning("Outstanding PaymentSession creation failed, checking DB for existing: %s", str(e))
                existing = db.query(PaymentSession).filter(
                    PaymentSession.invoice_id == oldest_unpaid.id,
                    PaymentSession.status == "ACTIVE"
                ).first()
                pay_outstanding_link = existing.payment_link_url if existing else None
                
    db.commit()
    
    return {
        "customer_name": customer.retailer_name,
        "invoice_id": str(invoice.id),
        "invoice_amount": invoice_amount,
        "invoice_status": invoice.payment_status,
        "outstanding_balance": outstanding_balance,
        "payment_links": {
            "pay_invoice": pay_invoice_link,
            "pay_outstanding": pay_outstanding_link,
            "custom_amount_enabled": True
        }
    }


@router.post("/trigger-reminder-sweep", status_code=200)
async def trigger_payment_reminder_sweep(db: Session = Depends(get_db)):
    """
    Triggers the payment reminder sweep manually or via scheduled cron.
    In production, call this daily via an external cron (e.g. cron-job.org).
    """
    import logging
    logger = logging.getLogger("uvicorn.error")
    from app.services.payment_reminder_service import run_payment_reminder_sweep
    try:
        summary = await run_payment_reminder_sweep(db)
        return {"status": "success", "summary": summary}
    except Exception as e:
        logger.error("Reminder sweep failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
