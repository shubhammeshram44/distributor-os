"""
test_auth.py — Firebase Authentication Tests
=============================================
Covers POST /auth/firebase-login, POST /auth/signup, and /me, /logout routes.
Firebase Admin SDK calls are fully mocked so no real Firebase project is needed.
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.utils.security import sign_jwt

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_PHONE = "+919876543210"
MOCK_UID = "firebase-uid-abc123"

def _mock_decoded_token(phone: str = MOCK_PHONE, uid: str = MOCK_UID) -> dict:
    """Returns a dict that looks like firebase_auth.verify_id_token() output."""
    return {"uid": uid, "phone_number": phone}


def _seed_existing_user(db_session) -> tuple:
    """Seed a Tenant + User in the test DB and return (tenant, user)."""
    tenant = DistributorTenant(
        id=uuid.uuid4(),
        name="Existing Corp",
        plan_type="FREE",
        monthly_order_count=0,
    )
    db_session.add(tenant)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        full_name="Existing Distributor",
        phone_number=MOCK_PHONE,
        email_or_phone=MOCK_PHONE,
        role="SUPER_ADMIN",
        is_active=True,
        firebase_uid=None,  # not yet stored
    )
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _make_signup_token(
    phone: str = MOCK_PHONE,
    uid: str = MOCK_UID,
    expires_in: int = 3600,
) -> str:
    return sign_jwt(
        {
            "sub": phone,
            "firebase_uid": uid,
            "phone_number": phone,
            "intent": "signup",
        },
        expires_in=expires_in,
    )


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------

def test_signup_valid_token(db_session):
    """
    Valid signup_token must create Tenant + User and return a session payload.
    """
    signup_token = _make_signup_token()

    response = client.post(
        "/api/v1/auth/signup",
        json={"signup_token": signup_token, "full_name": "New Distributor"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["is_new_registration"] is True
    assert "token" in data
    assert data["tenant_name"] == "My B2B Distribution"
    assert data["user"]["full_name"] == "New Distributor"
    assert data["user"]["phone_number"] == MOCK_PHONE
    assert data["user"]["role"] == "SUPER_ADMIN"
    assert "access_token=" in response.headers.get("set-cookie", "")

    assert db_session.query(DistributorTenant).count() == 1
    user = db_session.query(User).first()
    assert user is not None
    assert user.firebase_uid == MOCK_UID
    assert user.phone_number == MOCK_PHONE


def test_signup_expired_token(db_session):
    """
    Expired signup_token must return 401.
    """
    import time

    expired_token = sign_jwt(
        {
            "sub": MOCK_PHONE,
            "firebase_uid": MOCK_UID,
            "phone_number": MOCK_PHONE,
            "intent": "signup",
            "exp": int(time.time()) - 60,
        },
    )

    response = client.post(
        "/api/v1/auth/signup",
        json={"signup_token": expired_token},
    )

    assert response.status_code == 401
    assert db_session.query(User).count() == 0
    assert db_session.query(DistributorTenant).count() == 0


def test_signup_already_registered(db_session):
    """
    If the phone already exists, signup must return 409 without creating rows.
    """
    _seed_existing_user(db_session)
    signup_token = _make_signup_token()

    response = client.post(
        "/api/v1/auth/signup",
        json={"signup_token": signup_token},
    )

    assert response.status_code == 409
    assert db_session.query(DistributorTenant).count() == 1
    assert db_session.query(User).count() == 1


# ---------------------------------------------------------------------------
# POST /auth/firebase-login — new user path
# ---------------------------------------------------------------------------

def test_firebase_login_new_user(db_session):
    """
    When Firebase verifies the token but the phone isn't in our DB:
    - No User or DistributorTenant must be written.
    - Response must carry is_new_user=True, phone_number, and a signup_token.
    """
    with patch("app.api.v1.auth._get_firebase_app") as mock_init:
        mock_fb_auth = MagicMock()
        mock_fb_auth.verify_id_token.return_value = _mock_decoded_token()
        mock_init.return_value = mock_fb_auth

        response = client.post(
            "/api/v1/auth/firebase-login",
            json={"firebase_token": "mock.firebase.token.xyz"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["is_new_user"] is True
    assert data["phone_number"] == MOCK_PHONE
    assert "signup_token" in data
    assert len(data["signup_token"]) > 10  # is a real JWT string

    # Critical: zero DB rows created
    assert db_session.query(User).count() == 0
    assert db_session.query(DistributorTenant).count() == 0


# ---------------------------------------------------------------------------
# POST /auth/firebase-login — existing user path
# ---------------------------------------------------------------------------

def test_firebase_login_existing_user(db_session):
    """
    When Firebase verifies the token and the phone IS in our DB:
    - firebase_uid must be persisted on the user record.
    - Response must have is_new_user=False and carry the session payload.
    - access_token HttpOnly cookie must be set.
    """
    tenant, user = _seed_existing_user(db_session)

    with patch("app.api.v1.auth._get_firebase_app") as mock_init:
        mock_fb_auth = MagicMock()
        mock_fb_auth.verify_id_token.return_value = _mock_decoded_token()
        mock_init.return_value = mock_fb_auth

        response = client.post(
            "/api/v1/auth/firebase-login",
            json={"firebase_token": "mock.firebase.token.xyz"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["is_new_user"] is False
    assert "token" in data
    assert data["tenant_id"] == str(tenant.id)
    assert data["user"]["phone_number"] == MOCK_PHONE
    assert data["user"]["role"] == "SUPER_ADMIN"

    # Cookie must be present
    assert "access_token=" in response.headers.get("set-cookie", "")
    assert "HttpOnly" in response.headers.get("set-cookie", "")

    # firebase_uid must have been persisted
    db_session.expire_all()
    refreshed_user = db_session.get(User, user.id)
    assert refreshed_user.firebase_uid == MOCK_UID


def test_firebase_login_existing_user_already_has_uid(db_session):
    """
    When the user already has a firebase_uid stored, no extra DB write occurs
    but the login still succeeds normally.
    """
    tenant, user = _seed_existing_user(db_session)
    user.firebase_uid = MOCK_UID
    db_session.commit()

    with patch("app.api.v1.auth._get_firebase_app") as mock_init:
        mock_fb_auth = MagicMock()
        mock_fb_auth.verify_id_token.return_value = _mock_decoded_token()
        mock_init.return_value = mock_fb_auth

        response = client.post(
            "/api/v1/auth/firebase-login",
            json={"firebase_token": "mock.firebase.token.xyz"},
        )

    assert response.status_code == 200
    assert response.json()["is_new_user"] is False


# ---------------------------------------------------------------------------
# POST /auth/firebase-login — invalid / expired token
# ---------------------------------------------------------------------------

def test_firebase_login_invalid_token(db_session):
    """
    When verify_id_token raises (invalid/expired token), must return 401.
    """
    with patch("app.api.v1.auth._get_firebase_app") as mock_init:
        mock_fb_auth = MagicMock()
        mock_fb_auth.verify_id_token.side_effect = ValueError("Token expired")
        mock_init.return_value = mock_fb_auth

        response = client.post(
            "/api/v1/auth/firebase-login",
            json={"firebase_token": "bad.token.value"},
        )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


def test_firebase_login_no_phone_in_token(db_session):
    """
    If the decoded Firebase token contains no phone_number claim, return 400.
    """
    with patch("app.api.v1.auth._get_firebase_app") as mock_init:
        mock_fb_auth = MagicMock()
        mock_fb_auth.verify_id_token.return_value = {"uid": MOCK_UID}  # no phone_number
        mock_init.return_value = mock_fb_auth

        response = client.post(
            "/api/v1/auth/firebase-login",
            json={"firebase_token": "mock.firebase.token.no.phone"},
        )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /auth/logout  (unchanged — kept to prevent regression)
# ---------------------------------------------------------------------------

def test_logout_success():
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["message"] == "Session logged out successfully"
    # Verify cookie deletion instruction
    cookie_header = response.headers.get("set-cookie", "")
    assert 'access_token=""' in cookie_header or 'access_token=;' in cookie_header
