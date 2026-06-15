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
