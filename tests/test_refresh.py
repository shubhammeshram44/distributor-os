import uuid
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
import concurrent.futures
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db
from app.models.user import User
from app.models.tenant import DistributorTenant
from app.models.auth import RefreshSession
from app.api.v1.auth import _create_refresh_session

client = TestClient(app)

def _ensure_utc(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _seed_user_and_tenant(db: Session):
    tenant = DistributorTenant(
        id=uuid.uuid4(),
        name="Test Refresh Tenant",
        plan_type="FREE",
        monthly_order_count=0
    )
    db.add(tenant)
    db.flush()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        full_name="Refresh User",
        phone_number="+919999988888",
        email_or_phone="+919999988888",
        role="SUPER_ADMIN",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return tenant, user


def test_refresh_session_creation_and_cookies(db_session):
    tenant, user = _seed_user_and_tenant(db_session)
    
    # 1. Login should create session and set cookies
    # Fix: this test previously patched "firebase_admin.auth.verify_id_token"
    # directly, but firebase_login() actually calls _get_firebase_app()
    # first, which -- when no real Firebase app is registered and no
    # FIREBASE_CREDENTIALS_PATH/FIREBASE_CREDENTIALS_JSON env var is set (as
    # in this test environment/CI) -- raises RuntimeError before
    # verify_id_token is ever reached, regardless of that mock. The
    # unconditional 503 this produced was a genuine, unrelated Firebase-
    # config error, not a signal this test was actually exercising the
    # refresh-session/cookie logic it's meant to cover. Matching the
    # working pattern already used throughout test_auth.py, patch
    # _get_firebase_app() itself so the mock is actually on the path this
    # endpoint uses.
    with patch("app.api.v1.auth._get_firebase_app") as mock_get_firebase_app:
        mock_fb_auth = MagicMock()
        mock_fb_auth.verify_id_token.return_value = {"uid": "test-uid", "phone_number": user.phone_number}
        mock_get_firebase_app.return_value = mock_fb_auth

        response = client.post(
            "/api/v1/auth/firebase-login",
            json={"firebase_token": "valid-id-token"}
        )
        assert response.status_code == 200
        
        # Verify response cookies
        cookies = response.cookies
        assert "refresh_token" in cookies
        assert "access_token" in cookies
        
        # Verify database refresh session row
        refresh_sessions = db_session.query(RefreshSession).filter(RefreshSession.user_id == user.id).all()
        assert len(refresh_sessions) == 1
        session_row = refresh_sessions[0]
        assert session_row.revoked_at is None
        assert _ensure_utc(session_row.expires_at) > datetime.now(timezone.utc)
        assert _ensure_utc(session_row.absolute_expires_at) > datetime.now(timezone.utc)


def test_refresh_token_rotation(db_session):
    tenant, user = _seed_user_and_tenant(db_session)
    raw_token = _create_refresh_session(db_session, user.id)
    
    # Client performs refresh
    client.cookies.set("refresh_token", raw_token)
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://distroos.in"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    
    # Verify cookies have rotated token
    cookies = response.cookies
    assert "refresh_token" in cookies
    new_raw_token = cookies["refresh_token"]
    assert new_raw_token != raw_token
    
    # Old token must be invalidated (does not exist in DB as active)
    old_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    old_session = db_session.query(RefreshSession).filter(RefreshSession.token_hash == old_hash).first()
    assert old_session is None # token was updated/rotated


def test_refresh_expired_or_revoked_session(db_session):
    tenant, user = _seed_user_and_tenant(db_session)
    raw_token = _create_refresh_session(db_session, user.id)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    
    # Expire the session in database
    session_row = db_session.query(RefreshSession).filter(RefreshSession.token_hash == token_hash).first()
    session_row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    
    client.cookies.set("refresh_token", raw_token)
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://distroos.in"}
    )
    assert response.status_code == 401
    
    # Revoke the session in database
    session_row.revoked_at = datetime.now(timezone.utc)
    db_session.commit()
    
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://distroos.in"}
    )
    assert response.status_code == 401


def test_refresh_csrf_origin_check(db_session):
    tenant, user = _seed_user_and_tenant(db_session)
    raw_token = _create_refresh_session(db_session, user.id)
    
    client.cookies.set("refresh_token", raw_token)
    
    # Forbidden Origin
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://malicious-origin.com"}
    )
    assert response.status_code == 400
    assert "CORS validation failed" in response.json()["detail"]


def test_logout_revokes_and_clears_cookies(db_session):
    tenant, user = _seed_user_and_tenant(db_session)
    raw_token = _create_refresh_session(db_session, user.id)
    
    client.cookies.set("refresh_token", raw_token)
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "https://distroos.in"}
    )
    assert response.status_code == 200
    
    # Check revoked_at in database
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    session_row = db_session.query(RefreshSession).filter(RefreshSession.token_hash == token_hash).first()
    assert session_row.revoked_at is not None


def test_concurrent_refresh_requests(db_session):
    tenant, user = _seed_user_and_tenant(db_session)
    
    if db_session.bind.dialect.name == "sqlite":
        pytest.skip("Skipping concurrent refresh test on SQLite (requires row-level SELECT FOR UPDATE support)")

    # Disable shared session override so each HTTP request gets its own thread-safe DB session
    from app.main import app
    app.dependency_overrides.clear()

    raw_token = _create_refresh_session(db_session, user.id)
    
    # Make concurrent requests using threads on a single raw_token
    def make_request():
        thread_client = TestClient(app)
        thread_client.cookies.set("refresh_token", raw_token)
        return thread_client.post(
            "/api/v1/auth/refresh",
            headers={"Origin": "https://distroos.in"}
        )
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(make_request) for _ in range(2)]
        results = [f.result() for f in futures]
        
    status_codes = [r.status_code for r in results]
    assert 200 in status_codes
    assert 401 in status_codes


def test_unauthorized_refresh_clears_cookies(db_session):
    tenant, user = _seed_user_and_tenant(db_session)
    
    # Helper to check that response headers contain correct Set-Cookie deletion directives
    def assert_cookies_cleared(response):
        assert response.status_code == 401
        
        cookie_header = response.headers.get("set-cookie", "").lower()
        # Verify access_token delete attributes
        assert "access_token=" in cookie_header
        assert "path=/" in cookie_header
        # Verify refresh_token delete attributes
        assert "refresh_token=" in cookie_header
        assert "path=/api/v1/auth" in cookie_header
        # Dev attributes
        assert "secure" not in cookie_header
        assert "samesite=lax" in cookie_header

    # 1. Missing refresh token
    client.cookies.clear()
    resp_missing = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://distroos.in"}
    )
    assert_cookies_cleared(resp_missing)

    # 2. Invalid refresh token
    client.cookies.set("refresh_token", "non-existent-token")
    resp_invalid = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://distroos.in"}
    )
    assert_cookies_cleared(resp_invalid)

    # 3. Expired refresh token
    raw_token_exp = _create_refresh_session(db_session, user.id)
    token_hash_exp = hashlib.sha256(raw_token_exp.encode("utf-8")).hexdigest()
    session_exp = db_session.query(RefreshSession).filter(RefreshSession.token_hash == token_hash_exp).first()
    session_exp.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    client.cookies.set("refresh_token", raw_token_exp)
    resp_expired = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://distroos.in"}
    )
    assert_cookies_cleared(resp_expired)

    # 4. Revoked refresh token
    raw_token_rev = _create_refresh_session(db_session, user.id)
    token_hash_rev = hashlib.sha256(raw_token_rev.encode("utf-8")).hexdigest()
    session_rev = db_session.query(RefreshSession).filter(RefreshSession.token_hash == token_hash_rev).first()
    session_rev.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    client.cookies.set("refresh_token", raw_token_rev)
    resp_revoked = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://distroos.in"}
    )
    assert_cookies_cleared(resp_revoked)
