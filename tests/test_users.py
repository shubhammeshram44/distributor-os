import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.user import User
from app.database import tenant_context
from app.utils.security import verify_password, sign_jwt

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)


def _admin_headers(tenant_id, user_id=None):
    """Builds an Authorization header for a SUPER_ADMIN of the given tenant."""
    return {
        "Authorization": f"Bearer {sign_jwt({'user_id': str(user_id or uuid.uuid4()), 'tenant_id': str(tenant_id), 'role': 'SUPER_ADMIN'})}"
    }


def _seed_admin(db_session, tenant_id):
    admin = User(
        tenant_id=tenant_id,
        full_name="Seed Admin",
        email_or_phone=f"admin-{uuid.uuid4()}@tenant.com",
        hashed_password="hashed",
        role="SUPER_ADMIN",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def test_get_users_list(db_session, client):
    tenant = DistributorTenant(name="Users List Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    u1 = User(
        full_name="Alice Super",
        email_or_phone="alice@tenant.com",
        hashed_password="hashed_pwd_1",
        role="SUPER_ADMIN",
        is_active=True
    )
    u2 = User(
        full_name="Bob Driver",
        email_or_phone="bob@tenant.com",
        hashed_password="hashed_pwd_2",
        role="DRIVER",
        is_active=True
    )
    db_session.add_all([u1, u2])
    db_session.commit()

    # Query all users
    response = client.get(f"/api/v1/users?tenant_id={tenant.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    
    names = [u["full_name"] for u in data]
    assert "Alice Super" in names
    assert "Bob Driver" in names

    # Query by role Driver (case-insensitive check)
    response_driver = client.get(f"/api/v1/users?role=Driver&tenant_id={tenant.id}")
    assert response_driver.status_code == 200
    data_driver = response_driver.json()
    assert len(data_driver) == 1
    assert data_driver[0]["full_name"] == "Bob Driver"


def test_get_users_without_any_identity_is_rejected(client):
    """
    Regression test for AUTH-1: GET /users with neither an authenticated
    session NOR a tenant_id query param must be rejected, not silently
    return every user across every tenant in the database.
    """
    response = client.get("/api/v1/users")
    assert response.status_code == 401


def test_invite_user_success(db_session, client):
    tenant = DistributorTenant(name="Invite User Tenant")
    db_session.add(tenant)
    db_session.commit()
    admin = _seed_admin(db_session, tenant.id)

    response = client.post(
        f"/api/v1/users/invite?tenant_id={tenant.id}",
        json={
            "full_name": "Charlie Finance",
            "email_or_phone": "charlie@tenant.com",
            "role": "FINANCE",
            "password": "SecurePassword123"
        },
        headers=_admin_headers(tenant.id, admin.id)
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["full_name"] == "Charlie Finance"
    assert data["email_or_phone"] == "charlie@tenant.com"
    assert data["role"] == "FINANCE"
    assert data["is_active"] is True

    # Verify Database entry & secure password hashing
    db_session.expire_all()
    user_db = db_session.get(User, uuid.UUID(data["id"]))
    assert user_db is not None
    assert user_db.full_name == "Charlie Finance"
    assert verify_password("SecurePassword123", user_db.hashed_password) is True


def test_invite_user_without_auth_is_rejected(db_session, client):
    """
    Regression test for AUTH-1: POST /users/invite must reject callers with
    no authenticated session at all -- previously any unauthenticated caller
    could invite a brand-new SUPER_ADMIN into any tenant they could name.
    """
    tenant = DistributorTenant(name="Unauthed Invite Tenant")
    db_session.add(tenant)
    db_session.commit()

    response = client.post(
        f"/api/v1/users/invite?tenant_id={tenant.id}",
        json={
            "full_name": "Intruder Admin",
            "email_or_phone": "intruder@tenant.com",
            "role": "SUPER_ADMIN",
            "password": "SecurePassword123"
        }
    )
    assert response.status_code == 401
    db_session.expire_all()
    assert db_session.query(User).filter(User.email_or_phone == "intruder@tenant.com").first() is None


def test_invite_user_by_non_admin_is_rejected(db_session, client):
    """
    Regression test for AUTH-1: a valid, authenticated but non-admin user
    (e.g. OPERATOR) must not be able to invite new users / grant SUPER_ADMIN.
    """
    tenant = DistributorTenant(name="Non Admin Invite Tenant")
    db_session.add(tenant)
    db_session.commit()
    operator = User(
        tenant_id=tenant.id, full_name="Operator Joe", email_or_phone="joe@tenant.com",
        hashed_password="hashed", role="OPERATOR", is_active=True
    )
    db_session.add(operator)
    db_session.commit()

    token = sign_jwt({"user_id": str(operator.id), "tenant_id": str(tenant.id), "role": "OPERATOR"})
    response = client.post(
        f"/api/v1/users/invite?tenant_id={tenant.id}",
        json={
            "full_name": "Escalated Admin",
            "email_or_phone": "escalated@tenant.com",
            "role": "SUPER_ADMIN",
            "password": "SecurePassword123"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_invite_user_cross_tenant_is_rejected(db_session, client):
    """
    Regression test for AUTH-1: an authenticated SUPER_ADMIN of Tenant A must
    not be able to invite a user into Tenant B just by changing the tenant_id
    query parameter.
    """
    tenant_a = DistributorTenant(name="Tenant A")
    tenant_b = DistributorTenant(name="Tenant B")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()
    admin_a = _seed_admin(db_session, tenant_a.id)

    response = client.post(
        f"/api/v1/users/invite?tenant_id={tenant_b.id}",
        json={
            "full_name": "Cross Tenant Injection",
            "email_or_phone": "crosstenant@tenant.com",
            "role": "OPERATOR",
            "password": "SecurePassword123"
        },
        headers=_admin_headers(tenant_a.id, admin_a.id)
    )
    assert response.status_code == 403


def test_invite_user_duplicate_credential(db_session, client):
    tenant = DistributorTenant(name="Duplicate User Tenant")
    db_session.add(tenant)
    db_session.commit()
    admin = _seed_admin(db_session, tenant.id)

    tenant_context.set(tenant.id)

    u1 = User(
        full_name="Duplicate Target",
        email_or_phone="duplicate@tenant.com",
        hashed_password="hashed_pwd_1",
        role="OPERATOR",
        is_active=True
    )
    db_session.add(u1)
    db_session.commit()

    # Try to invite with the same email/phone
    response = client.post(
        f"/api/v1/users/invite?tenant_id={tenant.id}",
        json={
            "full_name": "Another Duplicate Target",
            "email_or_phone": "duplicate@tenant.com",
            "role": "OPERATOR",
            "password": "SecurePassword123"
        },
        headers=_admin_headers(tenant.id, admin.id)
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_invite_user_invalid_role(db_session, client):
    tenant = DistributorTenant(name="Invalid Role Tenant")
    db_session.add(tenant)
    db_session.commit()
    admin = _seed_admin(db_session, tenant.id)

    response = client.post(
        f"/api/v1/users/invite?tenant_id={tenant.id}",
        json={
            "full_name": "Invalid Role Guy",
            "email_or_phone": "guy@tenant.com",
            "role": "CEO",
            "password": "SecurePassword123"
        },
        headers=_admin_headers(tenant.id, admin.id)
    )
    assert response.status_code == 400
    assert "Invalid role" in response.json()["detail"]


def test_update_user_role_and_status(db_session, client):
    tenant = DistributorTenant(name="Update User Tenant")
    db_session.add(tenant)
    db_session.commit()
    admin = _seed_admin(db_session, tenant.id)

    tenant_context.set(tenant.id)
    user = User(
        tenant_id=tenant.id,
        full_name="Danny Operator",
        email_or_phone="danny@tenant.com",
        hashed_password="hashed_password",
        role="OPERATOR",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    # Update role to FINANCE and deactivate user
    response = client.patch(
        f"/api/v1/users/{user.id}?tenant_id={tenant.id}",
        json={
            "role": "FINANCE",
            "is_active": False
        },
        headers=_admin_headers(tenant.id, admin.id)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "FINANCE"
    assert data["is_active"] is False

    # Check database
    db_session.expire_all()
    user_db = db_session.get(User, user.id)
    assert user_db.role == "FINANCE"
    assert user_db.is_active is False


def test_update_user_without_auth_is_rejected(db_session, client):
    """
    Regression test for AUTH-1: PATCH /users/{id} must reject callers with no
    authenticated session -- previously any unauthenticated caller could
    escalate any user to SUPER_ADMIN or deactivate any account.
    """
    tenant = DistributorTenant(name="Unauthed Update Tenant")
    db_session.add(tenant)
    db_session.commit()
    user = User(
        tenant_id=tenant.id, full_name="Target User", email_or_phone="target@tenant.com",
        hashed_password="hashed", role="OPERATOR", is_active=True
    )
    db_session.add(user)
    db_session.commit()

    response = client.patch(
        f"/api/v1/users/{user.id}?tenant_id={tenant.id}",
        json={"role": "SUPER_ADMIN"}
    )
    assert response.status_code == 401
    db_session.expire_all()
    assert db_session.get(User, user.id).role == "OPERATOR"


def test_update_user_not_found(db_session, client):
    tenant = DistributorTenant(name="Not Found Tenant")
    db_session.add(tenant)
    db_session.commit()
    admin = _seed_admin(db_session, tenant.id)
    fake_user_id = uuid.uuid4()
    response = client.patch(
        f"/api/v1/users/{fake_user_id}?tenant_id={tenant.id}",
        json={
            "role": "OPERATOR"
        },
        headers=_admin_headers(tenant.id, admin.id)
    )
    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


def test_update_user_invalid_role(db_session, client):
    tenant = DistributorTenant(name="Update User Invalid Role Tenant")
    db_session.add(tenant)
    db_session.commit()
    admin = _seed_admin(db_session, tenant.id)

    tenant_context.set(tenant.id)
    user = User(
        tenant_id=tenant.id,
        full_name="Danny Operator",
        email_or_phone="danny2@tenant.com",
        hashed_password="hashed_password",
        role="OPERATOR",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    response = client.patch(
        f"/api/v1/users/{user.id}?tenant_id={tenant.id}",
        json={
            "role": "CTO"
        },
        headers=_admin_headers(tenant.id, admin.id)
    )
    assert response.status_code == 400
    assert "Invalid role" in response.json()["detail"]
