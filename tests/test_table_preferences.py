import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.user import User
from app.utils.security import sign_jwt

client = TestClient(app)

@pytest.fixture
def setup_tenants_and_users(db_engine):
    from sqlalchemy.orm import Session
    with Session(db_engine) as session:
        t1 = DistributorTenant(
            id=uuid.uuid4(),
            name="Tenant 1",
            category="FMCG",
        )
        t2 = DistributorTenant(
            id=uuid.uuid4(),
            name="Tenant 2",
            category="Pharma",
        )
        session.add_all([t1, t2])
        session.flush()

        u1_t1 = User(
            id=uuid.uuid4(),
            tenant_id=t1.id,
            full_name="User 1 Tenant 1",
            email_or_phone="+919876543210",
            role="OPERATOR",
            is_active=True
        )
        u2_t1 = User(
            id=uuid.uuid4(),
            tenant_id=t1.id,
            full_name="User 2 Tenant 1",
            email_or_phone="+919876543212",
            role="OPERATOR",
            is_active=True
        )
        u1_t2 = User(
            id=uuid.uuid4(),
            tenant_id=t2.id,
            full_name="User 1 Tenant 2",
            email_or_phone="+919876543211",
            role="OPERATOR",
            is_active=True
        )
        session.add_all([u1_t1, u2_t1, u1_t2])
        session.commit()

        return {
            "t1_id": t1.id,
            "t2_id": t2.id,
            "u1_t1_id": u1_t1.id,
            "u2_t1_id": u2_t1.id,
            "u1_t2_id": u1_t2.id,
        }

def make_auth_headers(user_id: uuid.UUID, tenant_id: uuid.UUID) -> dict:
    token = sign_jwt({
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "sub": "test@distroos.in",
        "role": "OPERATOR"
    })
    return {"Authorization": f"Bearer {token}"}

def test_default_preference_when_none_stored(setup_tenants_and_users):
    data = setup_tenants_and_users
    headers = make_auth_headers(data["u1_t1_id"], data["t1_id"])
    
    resp = client.get("/api/v1/table-preferences/orders", headers=headers)
    assert resp.status_code == 200
    res = resp.json()
    assert res["page_key"] == "orders"
    assert res["preference_mode"] == "default"
    assert res["visible_columns"] == []
    assert res["column_order"] == []
    assert res["version"] == 1

def test_save_and_retrieve_custom_preference(setup_tenants_and_users):
    data = setup_tenants_and_users
    headers = make_auth_headers(data["u1_t1_id"], data["t1_id"])

    custom_payload = {
        "preference_mode": "custom",
        "visible_columns": ["order", "customer", "amount", "payment"],
        "column_order": ["order", "customer", "amount", "payment", "lifecycle", "created_at"],
        "version": 1
    }

    put_resp = client.put("/api/v1/table-preferences/orders", json=custom_payload, headers=headers)
    assert put_resp.status_code == 200
    saved = put_resp.json()
    assert saved["preference_mode"] == "custom"
    assert saved["visible_columns"] == ["order", "customer", "amount", "payment"]
    assert saved["column_order"] == ["order", "customer", "amount", "payment", "lifecycle", "created_at"]

    # Verify retrieval
    get_resp = client.get("/api/v1/table-preferences/orders", headers=headers)
    assert get_resp.status_code == 200
    retrieved = get_resp.json()
    assert retrieved["preference_mode"] == "custom"
    assert retrieved["visible_columns"] == ["order", "customer", "amount", "payment"]
    assert retrieved["column_order"] == ["order", "customer", "amount", "payment", "lifecycle", "created_at"]
    assert retrieved["updated_at"] is not None

def test_user_and_tenant_isolation(setup_tenants_and_users):
    data = setup_tenants_and_users
    h_u1_t1 = make_auth_headers(data["u1_t1_id"], data["t1_id"])
    h_u2_t1 = make_auth_headers(data["u2_t1_id"], data["t1_id"])
    h_u1_t2 = make_auth_headers(data["u1_t2_id"], data["t2_id"])

    # User 1 Tenant 1 saves preference
    client.put("/api/v1/table-preferences/orders", json={
        "preference_mode": "custom",
        "visible_columns": ["order", "amount"],
        "column_order": ["order", "amount"],
        "version": 1
    }, headers=h_u1_t1)

    # User 2 Tenant 1 should still have default
    resp_u2 = client.get("/api/v1/table-preferences/orders", headers=h_u2_t1)
    assert resp_u2.status_code == 200
    assert resp_u2.json()["preference_mode"] == "default"

    # User 1 Tenant 2 should also have default
    resp_t2 = client.get("/api/v1/table-preferences/orders", headers=h_u1_t2)
    assert resp_t2.status_code == 200
    assert resp_t2.json()["preference_mode"] == "default"

def test_reset_preference_to_default(setup_tenants_and_users):
    data = setup_tenants_and_users
    headers = make_auth_headers(data["u1_t1_id"], data["t1_id"])

    # Set custom
    client.put("/api/v1/table-preferences/orders", json={
        "preference_mode": "custom",
        "visible_columns": ["order", "customer"],
        "column_order": ["order", "customer"],
        "version": 1
    }, headers=headers)

    # Reset
    del_resp = client.delete("/api/v1/table-preferences/orders", headers=headers)
    assert del_resp.status_code == 200

    # Verify mode is reset to default
    get_resp = client.get("/api/v1/table-preferences/orders", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["preference_mode"] == "default"
