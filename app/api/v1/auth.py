"""
Authentication Router — Firebase Admin SDK
==========================================
Identity verification is delegated to Firebase Phone Auth. DistributorOS keeps
one canonical phone identity per user and links the verified Firebase UID to it.
"""
import os
import json
import uuid
import logging
import traceback
import secrets
import hashlib
import re
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

import firebase_admin
from firebase_admin import credentials as fb_credentials, auth as fb_auth

from app.database import get_db
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.models.auth import RefreshSession
from app.utils.security import sign_jwt, verify_jwt, verify_signup_token
from app.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/auth", tags=["Authentication"])

ALLOWED_ORIGINS = [
    "https://distributor-os-ui.onrender.com",
    "https://distroos.in",
    "https://www.distroos.in"
]


def normalize_indian_phone(value: str) -> str:
    """Return an Indian mobile number in canonical E.164 form (+91XXXXXXXXXX)."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return f"+{digits}"
    raise ValueError("A valid 10-digit Indian mobile number is required.")


def _phone_identity_variants(canonical_phone: str) -> set[str]:
    """Exact legacy representations accepted while old rows self-heal."""
    local = canonical_phone[-10:]
    return {canonical_phone, local, f"91{local}"}


def _find_user_by_phone(db: Session, canonical_phone: str) -> User | None:
    variants = _phone_identity_variants(canonical_phone)
    return db.query(User).filter(
        or_(User.phone_number.in_(variants), User.email_or_phone.in_(variants))
    ).first()


def _canonicalize_user_phone(user: User, canonical_phone: str) -> bool:
    changed = False
    if user.phone_number != canonical_phone:
        user.phone_number = canonical_phone
        changed = True
    # Keep the legacy combined login field aligned only when it currently holds a phone.
    if user.email_or_phone and "@" not in user.email_or_phone and user.email_or_phone != canonical_phone:
        user.email_or_phone = canonical_phone
        changed = True
    return changed


def _validate_origin(request: Request):
    origin = request.headers.get("origin")
    if origin:
        _is_prod = os.getenv("ENVIRONMENT", "development") == "production"
        if _is_prod:
            if origin not in ALLOWED_ORIGINS:
                raise HTTPException(status_code=400, detail="CORS validation failed: Origin not allowed.")
        elif not (origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:") or origin in ALLOWED_ORIGINS):
            raise HTTPException(status_code=400, detail="CORS validation failed: Origin not allowed in development.")


def _ensure_utc(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _set_refresh_cookie(response: Response, refresh_token: str):
    _is_prod = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True,
                        secure=_is_prod, samesite="none" if _is_prod else "lax",
                        max_age=604800, path="/api/v1/auth")


def _delete_refresh_cookie(response: Response):
    _is_prod = os.getenv("ENVIRONMENT", "development") == "production"
    response.delete_cookie(key="refresh_token", httponly=True, secure=_is_prod,
                           samesite="none" if _is_prod else "lax", path="/api/v1/auth")


def _delete_access_cookie(response: Response):
    _is_prod = os.getenv("ENVIRONMENT", "development") == "production"
    response.delete_cookie(key="access_token", httponly=True, secure=_is_prod,
                           samesite="none" if _is_prod else "lax", path="/")


def _unauthorized_response(detail: str) -> JSONResponse:
    resp = JSONResponse(status_code=401, content={"detail": detail})
    _delete_access_cookie(resp)
    _delete_refresh_cookie(resp)
    return resp


def _create_refresh_session(db: Session, user_id: uuid.UUID) -> str:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    db.add(RefreshSession(id=uuid.uuid4(), user_id=user_id, token_hash=token_hash,
                          previous_token_hash=None, previous_token_valid_until=None,
                          created_at=now, last_used_at=now,
                          expires_at=now + timedelta(days=7),
                          absolute_expires_at=now + timedelta(days=30), revoked_at=None))
    db.commit()
    return raw_token


class FirebaseLoginPayload(BaseModel):
    firebase_token: str = Field(..., min_length=10)


class SignupPayload(BaseModel):
    signup_token: str = Field(..., min_length=10)
    full_name: str = Field(default="Mobile User", min_length=1)


def _get_firebase_app():
    try:
        firebase_admin.get_app()
        return fb_auth
    except ValueError:
        pass
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON") or getattr(settings, "FIREBASE_CREDENTIALS_JSON", None)
    if cred_path and os.path.exists(cred_path):
        cred = fb_credentials.Certificate(cred_path)
    elif cred_json:
        try:
            cred_dict = json.loads(cred_json)
            if "private_key" in cred_dict:
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = fb_credentials.Certificate(cred_dict)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"FIREBASE_CREDENTIALS_JSON is not valid JSON: {exc}") from exc
    else:
        raise RuntimeError("Firebase credentials are not configured.")
    try:
        firebase_admin.initialize_app(cred)
    except ValueError:
        pass
    return fb_auth


def _issue_session_response(user: User, tenant: DistributorTenant | None, phone_number: str,
                            response: Response, db: Session, is_new_registration: bool) -> dict:
    token = sign_jwt({"user_id": str(user.id),
                      "tenant_id": str(user.tenant_id) if user.tenant_id else None,
                      "sub": user.email_or_phone or phone_number, "role": user.role})
    _is_prod = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(key="access_token", value=token, httponly=True, secure=_is_prod,
                        samesite="none" if _is_prod else "lax", max_age=3600 * 24, path="/")
    refresh_token = _create_refresh_session(db, user.id)
    _set_refresh_cookie(response, refresh_token)
    return {
        "status": "success", "is_new_user": False,
        "is_new_registration": is_new_registration,
        "token": token, "access_token": token, "token_type": "bearer",
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "tenant_name": tenant.name if tenant else "My Workspace",
        "user": {"id": str(user.id), "tenant_id": str(user.tenant_id) if user.tenant_id else None,
                 "role": user.role, "full_name": user.full_name,
                 "phone_number": user.phone_number or phone_number},
    }


@router.post("/firebase-login", status_code=status.HTTP_200_OK)
def firebase_login(payload: FirebaseLoginPayload, response: Response, db: Session = Depends(get_db)):
    try:
        decoded_token = _get_firebase_app().verify_id_token(payload.firebase_token)
    except RuntimeError as exc:
        logger.error("Firebase Config Error: %s", exc)
        raise HTTPException(status_code=503, detail="Authentication service is currently misconfigured on the server.")
    except fb_auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Firebase token expired. Please request a new OTP.")
    except fb_auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid Firebase token. Please re-authenticate.")
    except ValueError:
        raise HTTPException(status_code=401, detail="Firebase token is invalid or has expired. Please request a new OTP.")
    except Exception:
        logger.error("Unexpected Auth Error: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error during cryptographic authentication.")

    uid = decoded_token.get("uid", "")
    raw_phone = decoded_token.get("phone_number", "")
    if not raw_phone:
        raise HTTPException(status_code=400, detail="Firebase token does not contain a verified phone_number claim.")
    try:
        phone_number = normalize_indian_phone(raw_phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # UID is strongest when already linked. Otherwise exact normalized phone identity is used.
    uid_user = db.query(User).filter(User.firebase_uid == uid).first() if uid else None
    phone_user = _find_user_by_phone(db, phone_number)

    if uid_user and phone_user and uid_user.id != phone_user.id:
        raise HTTPException(status_code=409, detail="This verified phone is linked to a different account. Contact support.")
    user = uid_user or phone_user

    if not user:
        signup_token = sign_jwt({"sub": phone_number, "firebase_uid": uid,
                                 "phone_number": phone_number, "intent": "signup"}, expires_in=3600)
        return {"status": "success", "is_new_user": True,
                "phone_number": phone_number, "signup_token": signup_token}

    # Never silently overwrite an existing Firebase identity.
    if user.firebase_uid and user.firebase_uid != uid:
        raise HTTPException(status_code=409, detail="This phone number is already linked to another login identity. Contact support.")

    changed = _canonicalize_user_phone(user, phone_number)
    if not user.firebase_uid:
        user.firebase_uid = uid
        changed = True
    if changed:
        db.commit()

    tenant = db.get(DistributorTenant, user.tenant_id) if user.tenant_id else None
    return _issue_session_response(user, tenant, phone_number, response, db, False)


@router.post("/signup", status_code=status.HTTP_200_OK)
def complete_signup(payload: SignupPayload, response: Response, db: Session = Depends(get_db)):
    signup_payload = verify_signup_token(payload.signup_token)
    if not signup_payload:
        raise HTTPException(status_code=401, detail="Signup token is invalid, expired, or missing required claims.")
    try:
        phone_number = normalize_indian_phone(signup_payload["phone_number"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail="Signup token contains an invalid phone number.") from exc
    firebase_uid = signup_payload["firebase_uid"]

    # Defence in depth: signup must never provision another workspace for an existing identity.
    existing_phone_user = _find_user_by_phone(db, phone_number)
    existing_uid_user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if existing_phone_user or existing_uid_user:
        raise HTTPException(status_code=409, detail="An account with this phone number already exists. Please log in.")

    new_tenant = DistributorTenant(id=uuid.uuid4(), name="My B2B Distribution",
                                    plan_type="FREE", monthly_order_count=0)
    db.add(new_tenant)
    db.flush()
    user = User(id=uuid.uuid4(), tenant_id=new_tenant.id, full_name=payload.full_name,
                phone_number=phone_number, email_or_phone=phone_number, hashed_password=None,
                role="SUPER_ADMIN", is_active=True, firebase_uid=firebase_uid)
    db.add(user)
    # Fix for AUTH-5: the existence checks above are a plain check-then-insert
    # with no lock -- a classic TOCTOU race. Two near-simultaneous signup
    # requests for the same phone/firebase_uid could both pass those checks
    # before either commits. The DB-level unique constraint on
    # users.firebase_uid is the actual backstop; catch the resulting
    # IntegrityError here and turn it into the same clean 409 the upfront
    # check already returns, instead of an unhandled 500.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this phone number already exists. Please log in.")
    return _issue_session_response(user, new_tenant, phone_number, response, db, True)


@router.get("/me", status_code=status.HTTP_200_OK)
def get_me(access_token: str | None = Cookie(None), authorization: str | None = Header(None),
           db: Session = Depends(get_db)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    if not token:
        token = access_token
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token_payload = verify_jwt(token)
    if not token_payload or "user_id" not in token_payload:
        raise HTTPException(status_code=401, detail="Invalid session token")
    user = db.get(User, uuid.UUID(token_payload["user_id"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # Fix for AUTH-2: previously the still-valid JWT alone was sufficient
    # for the rest of the token's lifetime (up to 24h), even after an admin
    # deactivated the user -- is_active was never re-checked here, unlike
    # /auth/refresh (see below) which already does. /auth/me is the exact
    # endpoint the frontend's dashboard auth guard calls on every fresh
    # page/tab load, so this is the most consequential place to close it.
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account has been deactivated")
    tenant = db.get(DistributorTenant, user.tenant_id)
    return {"id": str(user.id), "full_name": user.full_name,
            "phone_number": user.phone_number or "", "role": user.role,
            "tenant": {"id": str(tenant.id) if tenant else None,
                       "name": tenant.name if tenant else None,
                       "category": tenant.category if tenant else None}}


@router.post("/refresh", status_code=status.HTTP_200_OK)
def refresh_session(request: Request, response: Response,
                    refresh_token: str | None = Cookie(None), db: Session = Depends(get_db)):
    _validate_origin(request)
    if not refresh_token:
        return _unauthorized_response("Refresh token is missing. Please log in again.")
    token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    
    # Lookup by current token_hash or previous_token_hash
    session_row = db.query(RefreshSession).filter(
        or_(
            RefreshSession.token_hash == token_hash,
            RefreshSession.previous_token_hash == token_hash
        )
    ).with_for_update().first()
    
    if not session_row:
        return _unauthorized_response("Invalid refresh session context.")
        
    is_expired = (_ensure_utc(session_row.expires_at) < now or
                  _ensure_utc(session_row.absolute_expires_at) < now)
    if session_row.revoked_at is not None or is_expired:
        if is_expired and session_row.revoked_at is None:
            session_row.revoked_at = now
            db.commit()
        return _unauthorized_response("Session has expired or has been revoked. Please verify your phone to continue.")
        
    user = db.get(User, session_row.user_id)
    if not user or not user.is_active:
        return _unauthorized_response("Authenticated user is inactive or not found.")
        
    matched_previous = (session_row.previous_token_hash == token_hash)
    if matched_previous:
        # Check if the previous token's grace window is still valid
        grace_valid = (session_row.previous_token_valid_until is not None and
                       _ensure_utc(session_row.previous_token_valid_until) >= now)
        if not grace_valid:
            return _unauthorized_response("Previous refresh token has expired. Please log in again.")
        
        # CRITICAL CONCURRENCY FIX: Do NOT rotate the token again.
        # Return a new access token, and do NOT set/overwrite the refresh_token cookie.
        new_access_token = sign_jwt({"user_id": str(user.id),
                                     "tenant_id": str(user.tenant_id) if user.tenant_id else None,
                                     "sub": user.email_or_phone, "role": user.role})
        _is_prod = os.getenv("ENVIRONMENT", "development") == "production"
        response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=_is_prod,
                            samesite="none" if _is_prod else "lax", max_age=3600 * 24, path="/")
        return {"status": "success", "token": new_access_token,
                "access_token": new_access_token, "token_type": "bearer"}
            
    new_raw_token = secrets.token_urlsafe(32)
    new_hash = hashlib.sha256(new_raw_token.encode("utf-8")).hexdigest()
    
    # Shift current token to previous, and set grace period
    session_row.previous_token_hash = session_row.token_hash
    session_row.previous_token_valid_until = now + timedelta(seconds=60)
    session_row.token_hash = new_hash
    session_row.last_used_at = now
    session_row.expires_at = min(now + timedelta(days=7), _ensure_utc(session_row.absolute_expires_at))
    db.commit()
    
    new_access_token = sign_jwt({"user_id": str(user.id),
                                 "tenant_id": str(user.tenant_id) if user.tenant_id else None,
                                 "sub": user.email_or_phone, "role": user.role})
    _is_prod = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=_is_prod,
                        samesite="none" if _is_prod else "lax", max_age=3600 * 24, path="/")
    _set_refresh_cookie(response, new_raw_token)
    return {"status": "success", "token": new_access_token,
            "access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(request: Request, response: Response,
           refresh_token: str | None = Cookie(None), db: Session = Depends(get_db)):
    _validate_origin(request)
    if refresh_token:
        token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        session_row = db.query(RefreshSession).filter(
            or_(
                RefreshSession.token_hash == token_hash,
                RefreshSession.previous_token_hash == token_hash
            )
        ).with_for_update().first()
        if session_row and session_row.revoked_at is None:
            session_row.revoked_at = datetime.now(timezone.utc)
            db.commit()
    _delete_access_cookie(response)
    _delete_refresh_cookie(response)
    return {"status": "success", "message": "Session logged out successfully"}
