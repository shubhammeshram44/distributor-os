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
