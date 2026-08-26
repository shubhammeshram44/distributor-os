"""Regression tests for canonical Indian phone identity in Firebase auth."""
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.utils.security import sign_jwt
from app.api.v1.auth import normalize_indian_phone

client = TestClient(app)
PHONE_LOCAL = "9876543210"
PHONE_E164 = "+919876543210"
UID = "firebase-phone-identity-uid"


def _seed(db_session, phone=PHONE_LOCAL, uid=None):
    tenant = DistributorTenant(id=uuid.uuid4(), name="Legacy Tenant", plan_type="FREE", monthly_order_count=0)
    db_session.add(tenant)
    db_session.flush()
    user = User(id=uuid.uuid4(), tenant_id=tenant.id, full_name="Legacy User",
                phone_number=phone, email_or_phone=phone, role="SUPER_ADMIN",
                is_active=True, firebase_uid=uid)
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _login(phone=PHONE_E164, uid=UID):
    with patch("app.api.v1.auth._get_firebase_app") as mock_init:
        fb = MagicMock()
        fb.verify_id_token.return_value = {"uid": uid, "phone_number": phone}
        mock_init.return_value = fb
        return client.post("/api/v1/auth/firebase-login", json={"firebase_token": "mock.firebase.token.xyz"})


def test_normalize_indian_phone_accepts_local_and_e164():
    assert normalize_indian_phone(PHONE_LOCAL) == PHONE_E164
    assert normalize_indian_phone(PHONE_E164) == PHONE_E164
    assert normalize_indian_phone("91" + PHONE_LOCAL) == PHONE_E164


def test_legacy_10_digit_user_logs_into_existing_tenant_and_self_heals(db_session):
    tenant, user = _seed(db_session, PHONE_LOCAL)
    response = _login()
    assert response.status_code == 200
    data = response.json()
    assert data["is_new_user"] is False
    assert data["tenant_id"] == str(tenant.id)
    assert db_session.query(DistributorTenant).count() == 1
    db_session.expire_all()
    healed = db_session.get(User, user.id)
    assert healed.phone_number == PHONE_E164
    assert healed.email_or_phone == PHONE_E164
    assert healed.firebase_uid == UID


def test_existing_matching_uid_logs_in(db_session):
    tenant, _ = _seed(db_session, PHONE_E164, UID)
    response = _login()
    assert response.status_code == 200
    assert response.json()["tenant_id"] == str(tenant.id)


def test_existing_phone_with_different_uid_is_blocked(db_session):
    _seed(db_session, PHONE_E164, "different-existing-uid")
    response = _login(uid=UID)
    assert response.status_code == 409
    assert db_session.query(DistributorTenant).count() == 1
    assert db_session.query(User).count() == 1


def test_new_phone_still_enters_signup(db_session):
    response = _login()
    assert response.status_code == 200
    assert response.json()["is_new_user"] is True
    assert response.json()["phone_number"] == PHONE_E164
    assert db_session.query(User).count() == 0


def test_signup_cannot_create_second_workspace_for_legacy_phone(db_session):
    _seed(db_session, PHONE_LOCAL)
    signup_token = sign_jwt({"sub": PHONE_E164, "firebase_uid": UID,
                             "phone_number": PHONE_E164, "intent": "signup"}, expires_in=3600)
    response = client.post("/api/v1/auth/signup",
                           json={"signup_token": signup_token, "full_name": "Duplicate"})
    assert response.status_code == 409
    assert db_session.query(DistributorTenant).count() == 1
    assert db_session.query(User).count() == 1


def test_signup_stores_new_phone_canonically(db_session):
    signup_token = sign_jwt({"sub": PHONE_LOCAL, "firebase_uid": UID,
                             "phone_number": PHONE_LOCAL, "intent": "signup"}, expires_in=3600)
    response = client.post("/api/v1/auth/signup",
                           json={"signup_token": signup_token, "full_name": "New User"})
    assert response.status_code == 200
    user = db_session.query(User).first()
    assert user.phone_number == PHONE_E164
    assert user.email_or_phone == PHONE_E164
