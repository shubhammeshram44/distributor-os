import uuid
import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.auth import WhatsAppVerification
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.services.whatsapp_service import WhatsAppService
from app.utils.security import sign_jwt, verify_jwt

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
    
    is_new_user = True
    tenant_name = None
    if not user:
        # Create brand-new DistributorTenant for clean-slate setup
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
        tenant_name = new_tenant.name
    else:
        # Enforce Tenant Association Checks
        if user.tenant_id is not None:
            is_new_user = False
            tenant = db.get(DistributorTenant, user.tenant_id)
            if tenant:
                tenant_name = tenant.name
        
    db.commit()
    
    # Sign JWT token
    token_payload = {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "sub": user.email_or_phone,
        "role": user.role
    }
    token = sign_jwt(token_payload)
    
    # Return access token in HttpOnly response cookie wrapper
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",  # MANDATORY for cross-site cookie transmission on decoupled domains
        max_age=3600 * 24
    )
    
    return {
        "status": "success",
        "is_new_user": is_new_user,
        "is_new_registration": is_new_user,
        "token": token,
        "access_token": token,
        "token_type": "bearer",
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "tenant_name": tenant_name or "My Workspace",
        "user": {
            "id": str(user.id),
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "role": user.role,
            "full_name": user.full_name,
            "phone_number": user.phone_number or ""
        }
    }

@router.get("/me", status_code=status.HTTP_200_OK)
def get_me(
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    token = access_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
        
    payload = verify_jwt(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token"
        )
        
    user = db.get(User, uuid.UUID(payload["user_id"]))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
        
    tenant = db.get(DistributorTenant, user.tenant_id)
    
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "phone_number": user.phone_number or "",
        "role": user.role,
        "tenant": {
            "id": str(tenant.id) if tenant else None,
            "name": tenant.name if tenant else None,
            "category": tenant.category if tenant else None
        }
    }

@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(response: Response):
    """
    Clears the secure HttpOnly session access cookie across cross-origin domains.
    """
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=True,
        samesite="none"  # Must match login options footprint exactly
    )
    return {"status": "success", "message": "Session logged out successfully"}

