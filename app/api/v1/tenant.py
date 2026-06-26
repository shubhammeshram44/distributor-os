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
            "category": tenant.category
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

