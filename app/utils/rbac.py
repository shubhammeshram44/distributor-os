"""
RBAC middleware for FastAPI endpoints.
Use require_permission() decorator on any endpoint that needs access control.
"""

import uuid
from functools import wraps
from fastapi import HTTPException, Cookie, Header, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.security import verify_jwt
from app.models.user import User
from app.services.permission_service import check_permission


def get_current_user_with_permission(permission_key: str):
    """
    FastAPI dependency that:
    1. Validates JWT token
    2. Loads current user
    3. Checks if user has required permission
    4. Raises 403 if not
    
    Usage:
        @router.delete("/products/{id}")
        def delete_product(
            _: None = Depends(get_current_user_with_permission("products.delete")),
            ...
        ):
    """
    def dependency(
        access_token: str | None = Cookie(None),
        authorization: str | None = Header(None),
        db: Session = Depends(get_db)
    ):
        # Extract token
        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ")[1]
        if not token:
            token = access_token

        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")

        payload = verify_jwt(token)
        if not payload or "user_id" not in payload:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.get(User, uuid.UUID(payload["user_id"]))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")

        # Check permission
        if not check_permission(db, user.tenant_id, user.role, permission_key):
            raise HTTPException(
                status_code=403,
                detail=f"Your role ({user.role}) does not have permission: {permission_key}"
            )

        return user

    return dependency
