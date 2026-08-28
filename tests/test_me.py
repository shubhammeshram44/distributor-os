import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.utils.security import sign_jwt

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_get_me_endpoints(db_session, client):
    # 1. Create a dummy tenant and user
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    tenant = DistributorTenant(id=tenant_id, name="Test Tenant", category="FMCG")
    db_session.add(tenant)
    db_session.flush()
    
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        full_name="Jane Doe",
        phone_number="+1234567890",
        email_or_phone="jane@example.com",
        hashed_password=None,
        role="SUPER_ADMIN",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    
    # 2. Sign JWT token
    token_payload = {
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "role": "SUPER_ADMIN"
    }
    token = sign_jwt(token_payload)
    
    # Test unauthorized access
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 401
    
    # Test access with header
    headers = {"Authorization": f"Bearer {token}"}
    
    resp_auth_me = client.get("/api/v1/auth/me", headers=headers)
    assert resp_auth_me.status_code == 200
    data = resp_auth_me.json()
    assert data["id"] == str(user_id)
    assert data["full_name"] == "Jane Doe"
    assert data["role"] == "SUPER_ADMIN"
    assert data["tenant"]["id"] == str(tenant_id)
    assert data["tenant"]["name"] == "Test Tenant"
    assert data["tenant"]["category"] == "FMCG"
    
    resp_users_me = client.get("/api/v1/users/me", headers=headers)
    assert resp_users_me.status_code == 200
    data2 = resp_users_me.json()
    assert data2["id"] == str(user_id)
    assert data2["full_name"] == "Jane Doe"
    
    # Test access with cookie
    client.cookies.set("access_token", token)
    resp_cookie = client.get("/api/v1/auth/me")
    assert resp_cookie.status_code == 200
    assert resp_cookie.json()["id"] == str(user_id)


def test_get_me_rejects_deactivated_user(db_session, client):
    """
    Regression test for AUTH-2: /auth/me and /users/me previously never
    checked user.is_active -- a still-valid JWT (issued before deactivation,
    default 24h lifetime, no revocation list) continued to work for the
    rest of its lifetime even after an admin deactivated the account. This
    proves both endpoints now reject a deactivated user's still-valid token.
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    tenant = DistributorTenant(id=tenant_id, name="Deactivation Test Tenant", category="FMCG")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        id=user_id,
        tenant_id=tenant_id,
        full_name="Deactivated Dan",
        phone_number="+1234567891",
        email_or_phone="dan@example.com",
        hashed_password=None,
        role="SUPER_ADMIN",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    token = sign_jwt({"user_id": str(user_id), "tenant_id": str(tenant_id), "role": "SUPER_ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    # While active, the token works normally.
    resp_active = client.get("/api/v1/auth/me", headers=headers)
    assert resp_active.status_code == 200

    # Admin deactivates the user -- the JWT itself is untouched/still valid
    # (no revocation list exists), simulating the real-world "disable this
    # account" action.
    user.is_active = False
    db_session.commit()

    resp_deactivated_auth_me = client.get("/api/v1/auth/me", headers=headers)
    assert resp_deactivated_auth_me.status_code == 401

    resp_deactivated_users_me = client.get("/api/v1/users/me", headers=headers)
    assert resp_deactivated_users_me.status_code == 401


def test_admin_action_rejects_deactivated_super_admin(db_session, client):
    """
    Regression test for AUTH-2: get_current_admin_user (gating
    /admin/payment-reminders/run) previously never checked is_active either
    -- a deactivated SUPER_ADMIN's still-valid token could keep executing
    admin-only actions.
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    tenant = DistributorTenant(id=tenant_id, name="Admin Deactivation Tenant", category="FMCG")
    db_session.add(tenant)
    db_session.flush()

    admin_user = User(
        id=user_id,
        tenant_id=tenant_id,
        full_name="Deactivated Admin",
        phone_number="+1234567892",
        email_or_phone="deactivated-admin@example.com",
        hashed_password=None,
        role="SUPER_ADMIN",
        is_active=False
    )
    db_session.add(admin_user)
    db_session.commit()

    token = sign_jwt({"user_id": str(user_id), "tenant_id": str(tenant_id), "role": "SUPER_ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/admin/payment-reminders/run", headers=headers)
    assert resp.status_code == 401
