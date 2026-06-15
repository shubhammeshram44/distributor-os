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
            status_code=status.HTTP_440_NOT_FOUND,
            detail="Tenant not found."
        )
        
    tenant.name = payload.name
    tenant.category = payload.category
    db.commit()
    
    return {
        "status": "success",
        "message": "Tenant profile updated successfully",
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "category": tenant.category
        }
    }
