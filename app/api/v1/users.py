import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database import get_db, tenant_context
from app.models.user import User
from app.api.v1.dashboard import ensure_demo_data

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("")
def get_users(
    role: str | None = None,
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db)
):
    ensure_demo_data(db)
    if tenant_id:
        tenant_context.set(tenant_id)

    query = db.query(User)
    filters = []
    
    if tenant_id:
        filters.append(User.tenant_id == tenant_id)
    if role:
        filters.append(User.role == role)
        
    if filters:
        query = query.filter(and_(*filters))
        
    users = query.all()
    return [
        {
            "id": str(u.id),
            "full_name": u.full_name,
            "phone_number": u.phone_number,
            "role": u.role
        }
        for u in users
    ]
