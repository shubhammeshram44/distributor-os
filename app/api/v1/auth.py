"""
Authentication Router — Firebase Admin SDK
==========================================
Identity verification is now fully delegated to Firebase Phone Auth.
The client obtains a Firebase ID token after the user passes OTP verification
on the Firebase side, then submits that token here for cryptographic validation.

Endpoints:
  POST /auth/firebase-login — verify Firebase token, return session or new-user flag
  GET  /auth/me             — return current session user (unchanged)
  POST /auth/logout         — clear session cookie (unchanged)
"""
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.utils.security import sign_jwt, verify_jwt
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class FirebaseLoginPayload(BaseModel):
    firebase_token: str = Field(..., min_length=10)


# ---------------------------------------------------------------------------
# Firebase SDK initialisation helper (lazy, singleton-guarded)
# ---------------------------------------------------------------------------

def _get_firebase_app():
    """
    Lazily initialise the Firebase Admin SDK from the FIREBASE_CREDENTIALS_JSON
    environment variable. Guards against double-initialisation.
    Returns the firebase_auth module ready to call verify_id_token().
    Raises RuntimeError if credentials are not configured.
    """
    import firebase_admin
    from firebase_admin import credentials as fb_credentials, auth as fb_auth

    if not settings.FIREBASE_CREDENTIALS_JSON:
        raise RuntimeError(
            "FIREBASE_CREDENTIALS_JSON is not configured. "
            "Set this environment variable to your Firebase service account JSON string."
        )

    try:
        # Return existing app if already initialised
        firebase_admin.get_app()
    except ValueError:
        # App not yet initialised — parse JSON string and create credentials
        try:
            cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"FIREBASE_CREDENTIALS_JSON is not valid JSON: {exc}") from exc

        cred = fb_credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)

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
    Accepts a Firebase ID token issued after the user passes Phone OTP verification
    on the client side (Firebase Phone Auth flow).

    Flow:
      1. Verify the ID token cryptographically using the Firebase Admin SDK.
      2. Extract uid and phone_number from the decoded token.
      3. If the phone number is not found in our database → new user path:
         Return is_new_user=True so the frontend can route to the Company Name
         registration step. No DB writes occur here.
      4. If the user already exists → existing user path:
         Persist firebase_uid if not already stored, sign an internal JWT,
         set the access_token HttpOnly cookie, and return the session payload.
    """
    # Step 1: Verify Firebase token
    try:
        fb_auth = _get_firebase_app()
        decoded_token = fb_auth.verify_id_token(payload.firebase_token)
    except RuntimeError as exc:
        # SDK not configured — surface as 503
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception:
        # Any Firebase verification failure → 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token is invalid or has expired. Please re-authenticate.",
        )

    uid: str = decoded_token.get("uid", "")
    phone_number: str = decoded_token.get("phone_number", "")

    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase token does not contain a verified phone_number claim.",
        )

    # Step 2: Look up existing user by phone number or firebase_uid
    user = db.query(User).filter(
        (User.phone_number == phone_number)
        | (User.email_or_phone == phone_number)
        | (User.firebase_uid == uid)
    ).first()

    # Step 3: New user path — no DB writes, return flag + short-lived signup token
    # The signup_token encodes the verified phone/uid so the frontend can complete
    # the Company Name registration step without a second Firebase round-trip.
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

    # Step 5: Sign internal JWT
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
# GET /auth/me  (unchanged)
# ---------------------------------------------------------------------------

@router.get("/me", status_code=status.HTTP_200_OK)
def get_me(
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
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
# POST /auth/logout  (unchanged)
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
