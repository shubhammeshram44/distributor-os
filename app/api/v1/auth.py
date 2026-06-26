"""
Authentication Router — Firebase Admin SDK
==========================================
Identity verification is now fully delegated to Firebase Phone Auth.
The client obtains a Firebase ID token after the user passes OTP verification
on the Firebase side, then submits that token here for cryptographic validation.

Endpoints:
  POST /auth/firebase-login — verify Firebase token, return session or new-user flag
  POST /auth/signup          — complete registration using signup_token
  GET  /auth/me             — return current session user
  POST /auth/logout         — clear session cookie
"""
import os
import json
import uuid
import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Firebase Imports
import firebase_admin
from firebase_admin import credentials as fb_credentials, auth as fb_auth

from app.database import get_db
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.utils.security import sign_jwt, verify_jwt, verify_signup_token
from app.config import settings

# Setup standard enterprise logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class FirebaseLoginPayload(BaseModel):
    firebase_token: str = Field(..., min_length=10)


class SignupPayload(BaseModel):
    signup_token: str = Field(..., min_length=10)
    full_name: str = Field(default="Mobile User", min_length=1)


# ---------------------------------------------------------------------------
# Firebase SDK initialisation helper (lazy, singleton-guarded)
# ---------------------------------------------------------------------------

def _get_firebase_app():
    """
    Lazily initialise the Firebase Admin SDK. 
    Prefers FIREBASE_CREDENTIALS_PATH (Render Secret File) but falls back 
    to FIREBASE_CREDENTIALS_JSON string if present.
    """
    try:
        # Return existing app if already initialised
        firebase_admin.get_app()
        return fb_auth
    except ValueError:
        pass  # App not yet initialised, proceed below

    # 1. Prefer the Secure File Path (Render Secret Files)
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    # 2. Fallback to Environment JSON string
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON") or getattr(settings, "FIREBASE_CREDENTIALS_JSON", None)

    if cred_path and os.path.exists(cred_path):
        logger.info(f"Initializing Firebase from Secret File Path: {cred_path}")
        cred = fb_credentials.Certificate(cred_path)
    elif cred_json:
        logger.info("Initializing Firebase from JSON string environment variable.")
        try:
            cred_dict = json.loads(cred_json)
            if "private_key" in cred_dict:
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = fb_credentials.Certificate(cred_dict)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"FIREBASE_CREDENTIALS_JSON is not valid JSON: {exc}") from exc
    else:
        raise RuntimeError(
            "Firebase credentials are not configured. Set either "
            "FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON."
        )

    try:
        firebase_admin.initialize_app(cred)
    except ValueError:
        # Catch highly unlikely thread race-condition where it initialized in the last millisecond
        pass 

    return fb_auth


# ---------------------------------------------------------------------------
# POST /auth/firebase-login
# ---------------------------------------------------------------------------

@router.post("/firebase-login", status_code=status.HTTP_200_OK)
def firebase_login(
    payload: FirebaseLoginPayload,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Accepts a Firebase ID token, verifies it securely, and establishes a session.
    """
    # Step 1: Verify Firebase token with explicit exception granularity
    try:
        firebase_auth_module = _get_firebase_app()
        decoded_token = firebase_auth_module.verify_id_token(payload.firebase_token)
        
    except RuntimeError as exc:
        logger.error(f"Firebase Config Error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is currently misconfigured on the server."
        )
    except fb_auth.ExpiredIdTokenError:
        logger.warning("Rejected expired Firebase token.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token expired. Please request a new OTP."
        )
    except fb_auth.InvalidIdTokenError:
        logger.warning("Rejected invalid Firebase token signature.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token. Please re-authenticate."
        )
    except ValueError as ve:
        logger.error(f"Firebase Initialization/Value Error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token is invalid or has expired. Please request a new OTP."
        )
    except Exception as e:
        logger.error(f"Unexpected Auth Error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during cryptographic authentication."
        )

    uid: str = decoded_token.get("uid", "")
    phone_number: str = decoded_token.get("phone_number", "")

    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase token does not contain a verified phone_number claim.",
        )

    # Step 2: Extract trailing 10 digits to normalize against varying country prefixes
    clean_10_digits = phone_number[-10:] if phone_number else ""

    user = db.query(User).filter(
        (User.firebase_uid == uid) | 
        (User.phone_number.like(f"%{clean_10_digits}")) | 
        (User.email_or_phone.like(f"%{clean_10_digits}"))
    ).first()

    # Step 3: New user path — Return signup token to advance to company registration
    if not user:
        signup_token = sign_jwt(
            {
                "sub": phone_number,
                "firebase_uid": uid,
                "phone_number": phone_number,
                "intent": "signup",
            },
            expires_in=3600,  # 1-hour window to complete registration
        )
        return {
            "status": "success",
            "is_new_user": True,
            "phone_number": phone_number,
            "signup_token": signup_token,
        }

    # Step 4: Existing user path — update firebase_uid if not yet stored
    if not user.firebase_uid:
        user.firebase_uid = uid
        db.commit()

    # Step 5: Sign internal session JWT
    token_payload = {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "sub": user.email_or_phone or phone_number,
        "role": user.role,
    }
    token = sign_jwt(token_payload)

    # Step 6: Set HttpOnly session cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=3600 * 24,
    )

    tenant = db.get(DistributorTenant, user.tenant_id) if user.tenant_id else None

    return {
        "status": "success",
        "is_new_user": False,
        "is_new_registration": False,
        "token": token,
        "access_token": token,
        "token_type": "bearer",
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "tenant_name": tenant.name if tenant else "My Workspace",
        "user": {
            "id": str(user.id),
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "role": user.role,
            "full_name": user.full_name,
            "phone_number": user.phone_number or phone_number,
        },
    }


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------

def _issue_session_response(
    user: User,
    tenant: DistributorTenant | None,
    phone_number: str,
    response: Response,
) -> dict:
    """Helper to sign session JWT, set cookie, and return the standard login payload."""
    token_payload = {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "sub": user.email_or_phone or phone_number,
        "role": user.role,
    }
    token = sign_jwt(token_payload)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=3600 * 24,
    )

    return {
        "status": "success",
        "is_new_user": False,
        "is_new_registration": True,
        "token": token,
        "access_token": token,
        "token_type": "bearer",
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "tenant_name": tenant.name if tenant else "My Workspace",
        "user": {
            "id": str(user.id),
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "role": user.role,
            "full_name": user.full_name,
            "phone_number": user.phone_number or phone_number,
        },
    }


@router.post("/signup", status_code=status.HTTP_200_OK)
def complete_signup(
    payload: SignupPayload,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Completes registration for a new user who passed Firebase Phone Auth.
    Consumes the short-lived signup_token from firebase-login.
    """
    signup_payload = verify_signup_token(payload.signup_token)
    if not signup_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signup token is invalid, expired, or missing required claims.",
        )

    phone_number: str = signup_payload["phone_number"]
    firebase_uid: str = signup_payload["firebase_uid"]

    # Normalize trailing digits check during new signup to prevent race-condition duplicates
    clean_10_digits = phone_number[-10:] if phone_number else ""

    existing_user = db.query(User).filter(
        (User.phone_number.like(f"%{clean_10_digits}"))
        | (User.email_or_phone.like(f"%{clean_10_digits}"))
        | (User.firebase_uid == firebase_uid)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this phone number already exists. Please log in.",
        )

    # Provision standard initial workspace layout
    new_tenant = DistributorTenant(
        id=uuid.uuid4(),
        name="My B2B Distribution",
        plan_type="FREE",
        monthly_order_count=0,
    )
    db.add(new_tenant)
    db.flush()

    user = User(
        id=uuid.uuid4(),
        tenant_id=new_tenant.id,
        full_name=payload.full_name,
        phone_number=phone_number,
        email_or_phone=phone_number,
        hashed_password=None,
        role="SUPER_ADMIN",
        is_active=True,
        firebase_uid=firebase_uid,
    )
    db.add(user)
    db.commit()

    return _issue_session_response(user, new_tenant, phone_number, response)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get("/me", status_code=status.HTTP_200_OK)
def get_me(
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Retrieves session profile data from the active JWT."""
    token = access_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token_payload = verify_jwt(token)
    if not token_payload or "user_id" not in token_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
        )

    user = db.get(User, uuid.UUID(token_payload["user_id"]))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
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
            "category": tenant.category if tenant else None,
        },
    }


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(response: Response):
    """
    Clears the secure HttpOnly session access cookie across cross-origin domains.
    """
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=True,
        samesite="none",
    )
    return {"status": "success", "message": "Session logged out successfully"}
