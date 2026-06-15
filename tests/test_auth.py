import uuid
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.models.auth import WhatsAppVerification
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_request_otp_success(db_session, client):
    payload = {"mobile_number": "+919999999999"}
    response = client.post("/api/v1/auth/request-otp", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["message"] == "OTP sent successfully"
    
    # Verify DB entry
    db_session.expire_all()
    record = db_session.query(WhatsAppVerification).filter_by(mobile_number="+919999999999").first()
    assert record is not None
    assert len(record.otp_code) == 6
    assert record.is_verified is False
    assert record.expires_at > datetime.utcnow()

def test_verify_otp_new_registration(db_session, client):
    mobile = "+919888888888"
    
    # 1. Create a verification OTP record directly
    otp_code = "123456"
    expiry = datetime.utcnow() + timedelta(minutes=5)
    verification = WhatsAppVerification(
        id=uuid.uuid4(),
        mobile_number=mobile,
        otp_code=otp_code,
        expires_at=expiry,
        is_verified=False
    )
    db_session.add(verification)
    db_session.commit()
    
    # 2. Call verify endpoint
    payload = {"mobile_number": mobile, "otp_code": otp_code}
    response = client.post("/api/v1/auth/verify-otp", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["is_new_registration"] is True
    assert "token" in data
    assert data["user"]["phone_number"] == mobile
    assert data["user"]["role"] == "SUPER_ADMIN"
    
    # Verify HttpOnly cookie header
    assert "access_token=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    
    # Verify DB: verification marked as verified
    db_session.expire_all()
    rec = db_session.get(WhatsAppVerification, verification.id)
    assert rec.is_verified is True
    
    # Verify new user and tenant created
    new_user = db_session.query(User).filter_by(phone_number=mobile).first()
    assert new_user is not None
    assert new_user.role == "SUPER_ADMIN"
    
    new_tenant = db_session.get(DistributorTenant, new_user.tenant_id)
    assert new_tenant is not None
    assert new_tenant.name == "My B2B Distribution"

def test_verify_otp_existing_user(db_session, client):
    mobile = "+919777777777"
    
    # 1. Seed Tenant and User
    tenant = DistributorTenant(id=uuid.uuid4(), name="Existing Tenant")
    db_session.add(tenant)
    db_session.flush()
    
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        full_name="Existing Ramesh",
        phone_number=mobile,
        email_or_phone=mobile,
        role="OPERATOR",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    
    # 2. Create verification OTP record
    otp_code = "654321"
    expiry = datetime.utcnow() + timedelta(minutes=5)
    verification = WhatsAppVerification(
        id=uuid.uuid4(),
        mobile_number=mobile,
        otp_code=otp_code,
        expires_at=expiry,
        is_verified=False
    )
    db_session.add(verification)
    db_session.commit()
    
    # 3. Call verify endpoint
    payload = {"mobile_number": mobile, "otp_code": otp_code}
    response = client.post("/api/v1/auth/verify-otp", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["is_new_registration"] is False
    assert data["user"]["id"] == str(user.id)
    assert data["user"]["tenant_id"] == str(tenant.id)
    assert data["user"]["role"] == "OPERATOR"

def test_verify_otp_invalid_or_expired(db_session, client):
    mobile = "+919666666666"
    
    # Seed verification OTP record that is already expired
    otp_code = "111111"
    expiry = datetime.utcnow() - timedelta(minutes=1)
    verification = WhatsAppVerification(
        id=uuid.uuid4(),
        mobile_number=mobile,
        otp_code=otp_code,
        expires_at=expiry,
        is_verified=False
    )
    db_session.add(verification)
    db_session.commit()
    
    # Verify with wrong OTP
    payload = {"mobile_number": mobile, "otp_code": "222222"}
    response = client.post("/api/v1/auth/verify-otp", json=payload)
    assert response.status_code == 400
    assert "Invalid or expired OTP" in response.json()["detail"]
    
    # Verify with expired OTP
    payload = {"mobile_number": mobile, "otp_code": otp_code}
    response = client.post("/api/v1/auth/verify-otp", json=payload)
    assert response.status_code == 400
    assert "Invalid or expired OTP" in response.json()["detail"]
