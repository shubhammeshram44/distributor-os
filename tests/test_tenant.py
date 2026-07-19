import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.utils.security import sign_jwt

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_update_tenant_profile_success(db_session, client):
    # 1. Create a dummy tenant
    tenant_id = uuid.uuid4()
    tenant = DistributorTenant(id=tenant_id, name="Original Name", category=None)
    db_session.add(tenant)
    db_session.commit()
    
    # 2. Issue a JWT token for this tenant
    token_payload = {
        "user_id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "role": "SUPER_ADMIN"
    }
    token = sign_jwt(token_payload)
    
    # 3. Call profile update endpoint
    payload = {
        "name": "Updated Distributors LLC",
        "category": "FMCG"
    }
    
    # Send via Authorization Header
    response = client.put(
        "/api/v1/tenant/profile",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["tenant"]["name"] == "Updated Distributors LLC"
    assert data["tenant"]["category"] == "FMCG"
    
    # Verify DB update
    db_session.expire_all()
    updated_tenant = db_session.get(DistributorTenant, tenant_id)
    assert updated_tenant.name == "Updated Distributors LLC"
    assert updated_tenant.category == "FMCG"

def test_update_tenant_profile_unauthorized(client):
    payload = {
        "name": "Failed LLC",
        "category": "Beverages"
    }
    response = client.put("/api/v1/tenant/profile", json=payload)
    assert response.status_code == 401


def test_get_tenant_profile_prefers_header_over_stale_cookie(db_session, client):
    """
    Regression test for resolve_tenant_id (app/services/tenant_service.py),
    the shared tenant-resolution function used by nearly every authenticated
    endpoint (dashboard, orders, tenant, evolution, shipments, admin, etc.):
    a stale/garbage `access_token` cookie must never take precedence over a
    valid, freshly-issued Authorization Bearer token. This is the root cause
    behind "I'm already logged in, but a fresh tab asks me to log in again".
    """
    tenant_id = uuid.uuid4()
    tenant = DistributorTenant(id=tenant_id, name="Cookie Precedence Tenant", category="FMCG")
    db_session.add(tenant)
    db_session.commit()

    token = sign_jwt({
        "user_id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "role": "SUPER_ADMIN"
    })

    client.cookies.set("access_token", "garbage-stale-cookie-value")
    response = client.get(
        "/api/v1/tenant/profile",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["tenant"]["id"] == str(tenant_id)


def test_update_tenant_profile_prefers_header_over_stale_cookie(db_session, client):
    """
    Regression test for update_tenant_profile (PUT /api/v1/tenant/profile):
    unlike every other endpoint in this router, this one previously carried
    its OWN separate, unfixed copy of the cookie-first precedence bug (it
    resolves the JWT inline instead of delegating to the already-fixed
    resolve_tenant_id() helper). A stale/garbage access_token cookie must
    never shadow a valid, freshly-issued Authorization header here either —
    otherwise saving your business profile could wrongly 401 you out on a
    fresh tab/session even though your login is perfectly valid.
    """
    tenant_id = uuid.uuid4()
    tenant = DistributorTenant(id=tenant_id, name="Original Name", category=None)
    db_session.add(tenant)
    db_session.commit()

    token = sign_jwt({
        "user_id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "role": "SUPER_ADMIN"
    })

    client.cookies.set("access_token", "garbage-stale-cookie-value")
    response = client.put(
        "/api/v1/tenant/profile",
        json={"name": "Updated Via Header", "category": "FMCG"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["tenant"]["name"] == "Updated Via Header"
