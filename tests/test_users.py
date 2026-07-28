import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.user import User
from app.database import tenant_context
from app.utils.security import verify_password

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

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

def test_invite_user_success(db_session, client):
    tenant = DistributorTenant(name="Invite User Tenant")
    db_session.add(tenant)
    db_session.commit()

    response = client.post(
        f"/api/v1/users/invite?tenant_id={tenant.id}",
        json={
            "full_name": "Charlie Finance",
            "email_or_phone": "charlie@tenant.com",
            "role": "FINANCE",
            "password": "SecurePassword123"
        }
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

def test_invite_user_duplicate_credential(db_session, client):
    tenant = DistributorTenant(name="Duplicate User Tenant")
    db_session.add(tenant)
    db_session.commit()

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
        }
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

def test_invite_user_invalid_role(db_session, client):
    tenant = DistributorTenant(name="Invalid Role Tenant")
    db_session.add(tenant)
    db_session.commit()

    response = client.post(
        f"/api/v1/users/invite?tenant_id={tenant.id}",
        json={
            "full_name": "Invalid Role Guy",
            "email_or_phone": "guy@tenant.com",
            "role": "CEO",
            "password": "SecurePassword123"
        }
    )
    assert response.status_code == 400
    assert "Invalid role" in response.json()["detail"]

def test_update_user_role_and_status(db_session, client):
    tenant = DistributorTenant(name="Update User Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)
    user = User(
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
        }
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

def test_update_user_not_found(client):
    fake_tenant_id = uuid.uuid4()
    fake_user_id = uuid.uuid4()
    response = client.patch(
        f"/api/v1/users/{fake_user_id}?tenant_id={fake_tenant_id}",
        json={
            "role": "OPERATOR"
        }
    )
    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]

def test_update_user_invalid_role(db_session, client):
    tenant = DistributorTenant(name="Update User Invalid Role Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)
    user = User(
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
        }
    )
    assert response.status_code == 400
    assert "Invalid role" in response.json()["detail"]
