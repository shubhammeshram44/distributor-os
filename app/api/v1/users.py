import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database import get_db, tenant_context
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.api.v1.dashboard import ensure_demo_data
from app.utils.security import hash_password, verify_jwt

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("")
def get_users(
    role: str | None = None,
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db)
):
    ensure_demo_data(db, tenant_id)
    if tenant_id:
        tenant_context.set(tenant_id)

    query = db.query(User)
    filters = []
    
    if tenant_id:
        filters.append(User.tenant_id == tenant_id)
    if role:
        # Case-insensitive mapping to maintain driver dropdown compatibility
        if role.upper() == "DRIVER":
            filters.append(User.role.in_(["DRIVER", "Driver"]))
        else:
            filters.append(User.role == role)
        
    if filters:
        query = query.filter(and_(*filters))
        
    users = query.all()
    return [
        {
            "id": str(u.id),
            "full_name": u.full_name,
            "phone_number": u.phone_number,
            "email_or_phone": u.email_or_phone,
            "role": u.role,
            "is_active": u.is_active
        }
        for u in users
    ]

class UserInvitePayload(BaseModel):
    full_name: str = Field(..., min_length=1)
    email_or_phone: str = Field(..., min_length=3)
    role: str
    password: str = Field(..., min_length=6)

@router.post("/invite", status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: UserInvitePayload,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    tenant_context.set(tenant_id)
    
    valid_roles = {"SUPER_ADMIN", "FINANCE", "OPERATOR", "DRIVER"}
    role_upper = payload.role.upper()
    if role_upper not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of {valid_roles}"
        )
        
    # Check duplicate
    existing_user = db.query(User).filter(User.email_or_phone == payload.email_or_phone).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with identifier '{payload.email_or_phone}' already exists."
        )
        
    new_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        full_name=payload.full_name,
        email_or_phone=payload.email_or_phone,
        hashed_password=hash_password(payload.password),
        role=role_upper,
        is_active=True
    )
    
    # Populate phone_number column if the credential locator matches phone patterns
    if payload.email_or_phone.startswith("+") or payload.email_or_phone.replace("-", "").isdigit():
        new_user.phone_number = payload.email_or_phone
        
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "status": "success",
        "id": str(new_user.id),
        "full_name": new_user.full_name,
        "email_or_phone": new_user.email_or_phone,
        "role": new_user.role,
        "is_active": new_user.is_active
    }

class UserUpdatePayload(BaseModel):
    role: str | None = None
    is_active: bool | None = None

@router.patch("/{user_id}", status_code=status.HTTP_200_OK)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdatePayload,
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Modifies user roles and status parameters strictly under tenant context.
    """
    tenant_context.set(tenant_id)
    
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    if payload.role is not None:
        valid_roles = {"SUPER_ADMIN", "FINANCE", "OPERATOR", "DRIVER"}
        role_upper = payload.role.upper()
        if role_upper not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of {valid_roles}"
            )
        user.role = role_upper
        
    if payload.is_active is not None:
        user.is_active = payload.is_active
        
    db.commit()
    db.refresh(user)
    
    return {
        "status": "success",
        "id": str(user.id),
        "full_name": user.full_name,
        "email_or_phone": user.email_or_phone,
        "role": user.role,
        "is_active": user.is_active
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
