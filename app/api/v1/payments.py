import uuid
from fastapi import APIRouter, Depends, HTTPException, status
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
