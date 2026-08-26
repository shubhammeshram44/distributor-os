import uuid

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db, tenant_context
from app.models.tenant import DistributorTenant
from app.models.user import User
from app.services.tenant_service import resolve_tenant_id
from app.utils.security import verify_jwt

router = APIRouter(prefix="/customer-defaults", tags=["Customer Defaults"])


class CustomerDefaultsUpdate(BaseModel):
    credit_limit: float = Field(..., ge=0, le=100000000)
    payment_terms: str = Field(..., min_length=1, max_length=50)


def _current_user(
    db: Session,
    access_token: str | None,
    authorization: str | None,
) -> User:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        token = access_token
    payload = verify_jwt(token) if token else None
    if not payload or not payload.get("user_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        user = db.get(User, uuid.UUID(payload["user_id"]))
    except (ValueError, TypeError):
        user = None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Active user not found")
    return user


@router.get("", status_code=status.HTTP_200_OK)
def get_customer_defaults(
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)
    tenant_context.set(resolved_tenant_id)
    tenant = db.get(DistributorTenant, resolved_tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "credit_limit": float(tenant.default_customer_credit_limit or 5000),
        "payment_terms": tenant.default_customer_payment_terms or "Net 30",
        "applies_to": "new_customers_only",
    }


@router.patch("", status_code=status.HTTP_200_OK)
def update_customer_defaults(
    payload: CustomerDefaultsUpdate,
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    user = _current_user(db, access_token, authorization)
    resolved_tenant_id = resolve_tenant_id(tenant_id, access_token, authorization)

    if user.tenant_id != resolved_tenant_id:
        raise HTTPException(status_code=403, detail="You cannot update another workspace's defaults")
    if user.role not in {"SUPER_ADMIN", "FINANCE"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin or Finance users can change customer defaults",
        )

    tenant_context.set(resolved_tenant_id)
    tenant = db.get(DistributorTenant, resolved_tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.default_customer_credit_limit = payload.credit_limit
    tenant.default_customer_payment_terms = payload.payment_terms.strip()
    db.commit()

    return {
        "status": "success",
        "credit_limit": float(tenant.default_customer_credit_limit),
        "payment_terms": tenant.default_customer_payment_terms,
        "message": "Defaults saved. Existing customers were not changed.",
    }
