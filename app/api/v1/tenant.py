from fastapi import APIRouter, Depends, HTTPException, status, Header, Cookie
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import uuid
from app.database import get_db
from app.models.tenant import DistributorTenant
from app.utils.security import verify_jwt

router = APIRouter(prefix="/tenant", tags=["Tenant"])

class TenantProfileUpdate(BaseModel):
    name: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    gstin: str | None = Field(None, max_length=15)

@router.put("/profile", status_code=status.HTTP_200_OK)
def update_tenant_profile(
    payload: TenantProfileUpdate,
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    tenant_id_query: str | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    """
    Updates the active tenant's profile details (Business Name and Primary Category).
    """
    # 1. Resolve tenant_id
    resolved_tenant_id = None
    
    # Check X-Tenant-ID header
    if x_tenant_id:
        try:
            resolved_tenant_id = uuid.UUID(x_tenant_id)
        except ValueError:
            pass
            
    # Check query param
    if not resolved_tenant_id and tenant_id_query:
        try:
            resolved_tenant_id = uuid.UUID(tenant_id_query)
        except ValueError:
            pass
            
    # Check JWT from cookie or authorization header
    if not resolved_tenant_id:
        token = access_token
        if not token and authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
        if token:
            token_payload = verify_jwt(token)
            if token_payload and "tenant_id" in token_payload:
                try:
                    resolved_tenant_id = uuid.UUID(token_payload["tenant_id"])
                except ValueError:
                    pass
                    
    if not resolved_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not resolve active Tenant ID from session or headers."
        )
        
    tenant = db.get(DistributorTenant, resolved_tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found."
        )
        
    tenant.name = payload.name
    tenant.category = payload.category
    if payload.gstin is not None:
        tenant.gstin = payload.gstin.strip().upper() or None
    db.commit()
    
    # Invalidate cache for the tenant
    from app.services.ingestion_service import IngestionService
    IngestionService.invalidate_tenant_cache(resolved_tenant_id)
    
    return {
        "status": "success",
        "message": "Tenant profile updated successfully",
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "category": tenant.category,
            "gstin": tenant.gstin
        }
    }

@router.get("/profile", status_code=status.HTTP_200_OK)
def get_tenant_profile(
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    from app.services.tenant_service import resolve_tenant_id
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)

    tenant = db.get(DistributorTenant, resolved_tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found."
        )

    return {
        "status": "success",
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "category": tenant.category,
            "gstin": tenant.gstin
        }
    }

class WhatsAppConfigPayload(BaseModel):
    whatsapp_phone_id: str = Field(..., min_length=1)
    whatsapp_access_token: str = Field(..., min_length=1)
    whatsapp_order_phone: str | None = None

@router.get("/integrations/whatsapp", status_code=status.HTTP_200_OK)
def get_whatsapp_integration(
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    from app.services.tenant_service import resolve_tenant_id
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    
    tenant = db.get(DistributorTenant, resolved_tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found."
        )
        
    masked_token = ""
    if tenant.whatsapp_access_token:
        if len(tenant.whatsapp_access_token) >= 4:
            masked_token = "•" * 12 + tenant.whatsapp_access_token[-4:]
        else:
            masked_token = "•" * 12
            
    return {
        "status": "success",
        "whatsapp_phone_id": tenant.whatsapp_phone_id or "",
        "whatsapp_access_token": masked_token,
        "whatsapp_order_phone": tenant.whatsapp_order_phone or ""
    }

@router.patch("/integrations/whatsapp", status_code=status.HTTP_200_OK)
def update_whatsapp_integration(
    payload: WhatsAppConfigPayload,
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    from app.services.tenant_service import resolve_tenant_id
    from app.services.ingestion_service import IngestionService
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    
    tenant = db.get(DistributorTenant, resolved_tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found."
        )
        
    tenant.whatsapp_phone_id = payload.whatsapp_phone_id
    
    if not payload.whatsapp_access_token.startswith("•"):
        tenant.whatsapp_access_token = payload.whatsapp_access_token
        
    if payload.whatsapp_order_phone is not None:
        tenant.whatsapp_order_phone = payload.whatsapp_order_phone
        
    db.commit()
    
    # Invalidate cache for the tenant
    IngestionService.invalidate_tenant_cache(resolved_tenant_id)
    
    return {
        "status": "success",
        "message": "WhatsApp integration details updated successfully"
    }


from fastapi import Query

@router.get("/notification-prefs", status_code=status.HTTP_200_OK)
def get_notification_prefs(
    tenant_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db)
):
    tenant = db.get(DistributorTenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found."
        )
    return tenant.notification_prefs


@router.patch("/notification-prefs", status_code=status.HTTP_200_OK)
def update_notification_prefs(
    payload: dict,
    tenant_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db)
):
    tenant = db.get(DistributorTenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found."
        )
        
    current_prefs = dict(tenant.notification_prefs or {})
    for key, value in payload.items():
        current_prefs[key] = value
        
    tenant.notification_prefs = current_prefs
    db.commit()
    
    from app.services.ingestion_service import IngestionService
    IngestionService.invalidate_tenant_cache(tenant_id)
    
    return tenant.notification_prefs


class RazorpayConnectPayload(BaseModel):
    key_id: str = Field(..., min_length=1)
    key_secret: str = Field(..., min_length=1)

@router.get("/razorpay-status", status_code=status.HTTP_200_OK)
def get_razorpay_status(
    tenant_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db)
):
    tenant = db.get(DistributorTenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found."
        )
    
    connected = tenant.razorpay_key_id is not None and tenant.razorpay_key_secret_enc is not None
    key_id_masked = None
    if tenant.razorpay_key_id:
        if len(tenant.razorpay_key_id) >= 13:
            key_id_masked = tenant.razorpay_key_id[:13] + "•" * 8
        else:
            key_id_masked = tenant.razorpay_key_id + "•" * 8
            
    return {
        "connected": connected,
        "key_id_masked": key_id_masked,
        "account_name": tenant.razorpay_account_name,
        "mode": tenant.razorpay_mode
    }

@router.post("/razorpay-connect", status_code=status.HTTP_200_OK)
def connect_razorpay(
    payload: RazorpayConnectPayload,
    tenant_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db)
):
    tenant = db.get(DistributorTenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found."
        )
        
    key_id = payload.key_id.strip()
    key_secret = payload.key_secret.strip()
    
    # 1. Detect mode from key prefix
    if key_id.startswith("rzp_live_"):
        mode = "live"
    elif key_id.startswith("rzp_test_"):
        mode = "test"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Razorpay credentials"
        )
        
    # 2. Validate keys by making a real Razorpay API call
    import logging
    logger = logging.getLogger("uvicorn.error")
    try:
        import razorpay
        client = razorpay.Client(auth=(key_id, key_secret))
        # Use orders API — available on all Razorpay accounts including test mode
        client.order.all({"count": 1})
        account_name = "Razorpay Merchant"
    except razorpay.errors.BadRequestError as e:
        logger.warning("Razorpay BadRequestError: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Razorpay credentials. Please check your Key ID and Secret."
        )
    except Exception as e:
        logger.warning("Razorpay validation failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not validate Razorpay credentials: {str(e)}"
        )
    
    from app.utils.encryption import encrypt_secret
    # 3. Encrypt and save keys
    tenant.razorpay_key_id = key_id
    tenant.razorpay_key_secret_enc = encrypt_secret(key_secret)
    tenant.razorpay_account_name = account_name
    tenant.razorpay_mode = mode
    
    db.commit()
    
    # Return success + masked key ID
    if len(key_id) >= 13:
        key_id_masked = key_id[:13] + "•" * 8
    else:
        key_id_masked = key_id + "•" * 8
        
    return {
        "status": "success",
        "key_id_masked": key_id_masked,
        "account_name": account_name,
        "mode": mode
    }

@router.delete("/razorpay-disconnect", status_code=status.HTTP_200_OK)
def disconnect_razorpay(
    tenant_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db)
):
    tenant = db.get(DistributorTenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found."
        )
        
    tenant.razorpay_key_id = None
    tenant.razorpay_key_secret_enc = None
    tenant.razorpay_account_name = None
    tenant.razorpay_mode = "test"
    
    db.commit()
    return {
        "status": "success",
        "message": "Razorpay account disconnected successfully"
    }


