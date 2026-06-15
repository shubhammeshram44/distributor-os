import uuid
import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.auth import WhatsAppVerification
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.services.whatsapp_service import WhatsAppService
from app.utils.security import sign_jwt

router = APIRouter(prefix="/auth", tags=["Authentication"])

class RequestOTPPayload(BaseModel):
    mobile_number: str = Field(..., min_length=10, max_length=15)

class VerifyOTPPayload(BaseModel):
    mobile_number: str = Field(..., min_length=10, max_length=15)
    otp_code: str = Field(..., min_length=6, max_length=6)

@router.post("/request-otp", status_code=status.HTTP_200_OK)
def request_otp(
    payload: RequestOTPPayload,
    db: Session = Depends(get_db)
):
    """
    Generates a 6-digit OTP code, saves it to database, and pushes it via WhatsApp.
    """
    # Clean/normalize mobile number
    mobile = payload.mobile_number.strip()
    
    # Generate random 6-digit code
    otp = f"{random.randint(100000, 999999)}"
    
    # Create verification record with 5-minute window
    expiry = datetime.utcnow() + timedelta(minutes=5)
    verification = WhatsAppVerification(
        id=uuid.uuid4(),
        mobile_number=mobile,
        otp_code=otp,
        expires_at=expiry,
        is_verified=False
    )
    db.add(verification)
    db.commit()
    
    # Trigger simulation to push OTP message
    try:
        whatsapp = WhatsAppService()
        whatsapp.send_otp_message(mobile, otp)
    except Exception as e:
        # Log error but don't fail transaction
        print(f"Failed to push OTP: {e}")
        
    return {
        "status": "success",
        "message": "OTP sent successfully"
    }

@router.post("/verify-otp", status_code=status.HTTP_200_OK)
def verify_otp(
    payload: VerifyOTPPayload,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Verifies OTP code and issues JWT access token in an HttpOnly cookie.
    Creates new Tenant/User if registering for the first time.
    """
    mobile = payload.mobile_number.strip()
    code = payload.otp_code.strip()
    
    # Check verification record
    now = datetime.utcnow()
    record = db.query(WhatsAppVerification).filter(
        WhatsAppVerification.mobile_number == mobile,
        WhatsAppVerification.otp_code == code,
        WhatsAppVerification.is_verified == False,
        WhatsAppVerification.expires_at > now
    ).order_by(WhatsAppVerification.expires_at.desc()).first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code"
        )
        
    # Mark as verified
    record.is_verified = True
    db.flush()
    
    # Lookup User by mobile
    user = db.query(User).filter(
        (User.phone_number == mobile) | (User.email_or_phone == mobile)
    ).first()
    
    is_new_registration = False
    if not user:
        # Create brand-new DistributorTenant for clean-slate setup
        is_new_registration = True
        new_tenant = DistributorTenant(
            id=uuid.uuid4(),
            name="My B2B Distribution"
        )
        db.add(new_tenant)
        db.flush()
        
        # Create user
        user = User(
            id=uuid.uuid4(),
            tenant_id=new_tenant.id,
            full_name="Mobile User",
            phone_number=mobile,
            email_or_phone=mobile,
            hashed_password=None,
            role="SUPER_ADMIN",
            is_active=True
        )
        db.add(user)
        db.flush()
        
    db.commit()
    
    # Sign JWT token
    token_payload = {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role
    }
    token = sign_jwt(token_payload)
    
    # Return access token in HttpOnly response cookie wrapper
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=3600 * 24
    )
    
    return {
        "status": "success",
        "is_new_registration": is_new_registration,
        "token": token,
        "user": {
            "id": str(user.id),
            "tenant_id": str(user.tenant_id),
            "role": user.role,
            "full_name": user.full_name,
            "phone_number": user.phone_number
        }
    }
