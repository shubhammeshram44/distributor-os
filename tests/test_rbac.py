import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.user import User
from app.models.permission import Permission, RolePermission
from app.services.permission_service import (
    seed_permissions,
    seed_role_permissions_for_tenant,
    check_permission,
    get_user_permissions
)
from app.utils.security import sign_jwt

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_permissions_seeding_and_retrieval(db_session):
    # 1. Seed master list of permissions
    seed_permissions(db_session)
    perms = db_session.query(Permission).all()
    assert len(perms) > 0
    
    # Check specific permission key exists
    keys = [p.key for p in perms]
    assert "users.invite" in keys
    assert "orders.view" in keys

    # 2. Seed role permissions for a tenant
    tenant = DistributorTenant(name="RBAC Tenant")
    db_session.add(tenant)
    db_session.commit()

    seed_role_permissions_for_tenant(db_session, tenant.id)

    # Check database maps
    role_perms = db_session.query(RolePermission).filter(
        RolePermission.tenant_id == tenant.id
    ).all()
    assert len(role_perms) > 0

    # Test duplicate seeding is optimized/skipped
    initial_count = db_session.query(RolePermission).filter(
        RolePermission.tenant_id == tenant.id
    ).count()
    
    # Try seeding again
    seed_role_permissions_for_tenant(db_session, tenant.id)
    new_count = db_session.query(RolePermission).filter(
        RolePermission.tenant_id == tenant.id
    ).count()
    assert initial_count == new_count

def test_permission_checking_helpers(db_session):
    seed_permissions(db_session)
    tenant = DistributorTenant(name="Helper Tenant")
    db_session.add(tenant)
    db_session.commit()
    seed_role_permissions_for_tenant(db_session, tenant.id)

    # SUPER_ADMIN gets access to everything
    assert check_permission(db_session, tenant.id, "SUPER_ADMIN", "users.invite") is True
    assert check_permission(db_session, tenant.id, "SUPER_ADMIN", "non_existent_permission") is True

    # OPERATOR has users.invite = False, but orders.view = True
    assert check_permission(db_session, tenant.id, "OPERATOR", "orders.view") is True
    assert check_permission(db_session, tenant.id, "OPERATOR", "users.invite") is False

    # Check user permissions list retrieval
    operator_perms = get_user_permissions(db_session, tenant.id, "OPERATOR")
    assert "orders.view" in operator_perms
    assert "users.invite" not in operator_perms

    admin_perms = get_user_permissions(db_session, tenant.id, "SUPER_ADMIN")
    assert "users.invite" in admin_perms

def test_my_permissions_endpoint(db_session, client):
    seed_permissions(db_session)
    tenant = DistributorTenant(name="API Permissions Tenant")
    db_session.add(tenant)
    db_session.commit()
    seed_role_permissions_for_tenant(db_session, tenant.id)

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        full_name="Danny Operator",
        email_or_phone="danny@rbac.com",
        role="OPERATOR",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    # Generate token
    token = sign_jwt({
        "user_id": str(user.id),
        "tenant_id": str(tenant.id),
        "role": "OPERATOR"
    })
    headers = {"Authorization": f"Bearer {token}"}

    # Request permissions
    response = client.get("/api/v1/users/permissions", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "OPERATOR"
    assert "orders.view" in data["permissions"]
    assert "users.invite" not in data["permissions"]

def test_invite_user_endpoint_rbac(db_session, client):
    seed_permissions(db_session)
    tenant = DistributorTenant(name="API Invite RBAC Tenant")
    db_session.add(tenant)
    db_session.commit()
    seed_role_permissions_for_tenant(db_session, tenant.id)

    # 1. Invite using SUPER_ADMIN -> should succeed
    admin_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        full_name="Admin",
        email_or_phone="admin@rbac.com",
        role="SUPER_ADMIN",
        is_active=True
    )
    db_session.add(admin_user)
    db_session.commit()

    token_admin = sign_jwt({
        "user_id": str(admin_user.id),
        "tenant_id": str(tenant.id),
        "role": "SUPER_ADMIN"
    })
    
    response = client.post(
        "/api/v1/users/invite",
        json={
            "full_name": "Charlie Operator",
            "email_or_phone": "charlie@rbac.com",
            "role": "OPERATOR",
            "password": "SecurePassword123"
        },
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert response.status_code == 201

    # 2. Invite using DRIVER (who does not have users.invite permission) -> should return 403
    driver_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        full_name="Driver User",
        email_or_phone="driver@rbac.com",
        role="DRIVER",
        is_active=True
    )
    db_session.add(driver_user)
    db_session.commit()

    token_driver = sign_jwt({
        "user_id": str(driver_user.id),
        "tenant_id": str(tenant.id),
        "role": "DRIVER"
    })

    response_denied = client.post(
        "/api/v1/users/invite",
        json={
            "full_name": "Failed Operator",
            "email_or_phone": "failed@rbac.com",
            "role": "OPERATOR",
            "password": "SecurePassword123"
        },
        headers={"Authorization": f"Bearer {token_driver}"}
    )
    assert response_denied.status_code == 403
    assert "does not have permission: users.invite" in response_denied.json()["detail"]
