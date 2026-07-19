import uuid
from fastapi import Cookie, Header, HTTPException, status
from app.utils.security import verify_jwt

# Static Tenant ID for demo/default distributor
DEMO_TENANT_ID = uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d")

def get_validated_tenant_id(current_tenant_str: str | uuid.UUID | None) -> uuid.UUID:
    """
    Scalable validation guardrail to intercept malformed or missing tenant strings
    BEFORE they trigger downstream Postgres casting compilation errors.
    """
    if not current_tenant_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or token missing. Please log in again."
        )
    
    try:
        # Enforce local micro-validation check
        return uuid.UUID(str(current_tenant_str))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid workspace session context token formatting."
        )

def resolve_tenant_id(
    tenant_id: uuid.UUID | None = None,
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None)
) -> uuid.UUID:
    """
    Resolves the tenant ID by checking the JWT cookie or Authorization header first.
    Falls back to query parameter if not authenticated (preserving tests compatibility).
    """
    # Prefer the explicit Authorization header over the httponly cookie. The
    # frontend actively manages its session via localStorage + this header
    # (see dashboard/layout.tsx's auth guard), refreshing it on every login.
    # The cookie, by contrast, is invisible to and unmanaged by the frontend's
    # JS, and can legitimately go stale (e.g. it survives independently of
    # localStorage across multiple logins/logouts on the same browser). If a
    # stale-but-present cookie were preferred, a perfectly valid, freshly
    # issued session (header) would get wrongly rejected — this is the exact
    # bug behind "already logged in, but a fresh tab asks me to log in again".
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ")[1]
    if not token:
        token = access_token

    resolved_tenant = None
    if token:
        payload = verify_jwt(token)
        if payload and "tenant_id" in payload:
            resolved_tenant = payload["tenant_id"]
            
    if not resolved_tenant and tenant_id:
        resolved_tenant = tenant_id
        
    return get_validated_tenant_id(resolved_tenant)

