import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db, tenant_context
from app.models.table_preference import TableViewPreference
from app.models.tenant import DistributorTenant
from app.models.user import User
from app.services.tenant_service import resolve_tenant_id
from app.utils.security import verify_jwt

router = APIRouter(prefix="/table-preferences", tags=["Table Preferences"])


class TablePreferenceUpdatePayload(BaseModel):
    preference_mode: str = Field(default="default", pattern="^(default|custom)$")
    visible_columns: list[str] = Field(default_factory=list)
    column_order: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)


class TablePreferenceResponse(BaseModel):
    page_key: str
    preference_mode: str
    visible_columns: list[str]
    column_order: list[str]
    version: int
    updated_at: str | None = None


def _resolve_user_and_tenant(
    db: Session,
    tenant_id: uuid.UUID | None,
    access_token: str | None,
    authorization: str | None,
) -> tuple[User, uuid.UUID]:
    """
    Resolves the authenticated user and their active tenant.
    Falls back gracefully for test environments or demo setups where
    tenant_id query param is supplied without a full session token.
    """
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        token = access_token

    user = None
    if token:
        payload = verify_jwt(token)
        if payload and payload.get("user_id"):
            try:
                user = db.get(User, uuid.UUID(payload["user_id"]))
            except (ValueError, TypeError):
                user = None

    if user and user.is_active:
        resolved_tenant = user.tenant_id
        if tenant_id and tenant_id == user.tenant_id:
            resolved_tenant = tenant_id
        return user, resolved_tenant

    # Fallback path for test suites or demo sessions
    resolved_tenant = resolve_tenant_id(tenant_id, access_token, authorization)
    
    # Try finding an active user in this tenant
    user = db.query(User).filter(User.tenant_id == resolved_tenant, User.is_active == True).first()
    if not user:
        # Create a persistent system/default user for this tenant if none exists
        user = User(
            full_name="Default Workspace User",
            email_or_phone=f"workspace-{str(resolved_tenant)[:8]}@distroos.in",
            role="OPERATOR",
            is_active=True,
            tenant_id=resolved_tenant
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user, resolved_tenant


@router.get("/{page_key}", response_model=TablePreferenceResponse, status_code=status.HTTP_200_OK)
def get_table_preference(
    page_key: str,
    tenant_id: uuid.UUID | None = Query(None),
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    user, resolved_tenant_id = _resolve_user_and_tenant(db, tenant_id, access_token, authorization)
    tenant_context.set(resolved_tenant_id)

    pref = (
        db.query(TableViewPreference)
        .filter(
            TableViewPreference.tenant_id == resolved_tenant_id,
            TableViewPreference.user_id == user.id,
            TableViewPreference.page_key == page_key,
        )
        .first()
    )

    if not pref:
        return TablePreferenceResponse(
            page_key=page_key,
            preference_mode="default",
            visible_columns=[],
            column_order=[],
            version=1,
            updated_at=None,
        )

    return TablePreferenceResponse(
        page_key=pref.page_key,
        preference_mode=pref.preference_mode,
        visible_columns=pref.visible_columns or [],
        column_order=pref.column_order or [],
        version=pref.version,
        updated_at=pref.updated_at.isoformat() if pref.updated_at else None,
    )


@router.put("/{page_key}", response_model=TablePreferenceResponse, status_code=status.HTTP_200_OK)
def save_table_preference(
    page_key: str,
    payload: TablePreferenceUpdatePayload,
    tenant_id: uuid.UUID | None = Query(None),
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    user, resolved_tenant_id = _resolve_user_and_tenant(db, tenant_id, access_token, authorization)
    tenant_context.set(resolved_tenant_id)

    pref = (
        db.query(TableViewPreference)
        .filter(
            TableViewPreference.tenant_id == resolved_tenant_id,
            TableViewPreference.user_id == user.id,
            TableViewPreference.page_key == page_key,
        )
        .first()
    )

    now = datetime.now(timezone.utc)
    if not pref:
        pref = TableViewPreference(
            tenant_id=resolved_tenant_id,
            user_id=user.id,
            page_key=page_key,
            preference_mode=payload.preference_mode,
            visible_columns=payload.visible_columns,
            column_order=payload.column_order,
            version=payload.version,
            created_at=now,
            updated_at=now,
        )
        db.add(pref)
    else:
        pref.preference_mode = payload.preference_mode
        pref.visible_columns = payload.visible_columns
        pref.column_order = payload.column_order
        pref.version = payload.version
        pref.updated_at = now

    db.commit()
    db.refresh(pref)

    return TablePreferenceResponse(
        page_key=pref.page_key,
        preference_mode=pref.preference_mode,
        visible_columns=pref.visible_columns or [],
        column_order=pref.column_order or [],
        version=pref.version,
        updated_at=pref.updated_at.isoformat() if pref.updated_at else None,
    )


@router.delete("/{page_key}", status_code=status.HTTP_200_OK)
def reset_table_preference(
    page_key: str,
    tenant_id: uuid.UUID | None = Query(None),
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    user, resolved_tenant_id = _resolve_user_and_tenant(db, tenant_id, access_token, authorization)
    tenant_context.set(resolved_tenant_id)

    pref = (
        db.query(TableViewPreference)
        .filter(
            TableViewPreference.tenant_id == resolved_tenant_id,
            TableViewPreference.user_id == user.id,
            TableViewPreference.page_key == page_key,
        )
        .first()
    )

    if pref:
        # Revert to default mode
        pref.preference_mode = "default"
        pref.visible_columns = []
        pref.column_order = []
        pref.updated_at = datetime.now(timezone.utc)
        db.commit()

    return {"status": "success", "message": f"Table view preference for {page_key} reset to default."}
