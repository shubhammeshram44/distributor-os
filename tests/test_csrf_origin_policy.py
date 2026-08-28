"""
Regression tests for AUTH-4: origin-based CSRF validation previously
existed only in app/api/v1/auth.py's _validate_origin(), and was only
ever called by POST /auth/refresh and POST /auth/logout -- every other
cookie-authenticated, state-changing endpoint across the rest of the API
had zero origin validation, despite production cookies being set with
samesite="none" (required for this app's cross-origin frontend/backend
split), which disables SameSite's own CSRF protection entirely.

Also fixed: app/main.py's CORSMiddleware allow_origins list and
app/api/v1/auth.py's ALLOWED_ORIGINS list were two independently
maintained allowlists that had already drifted out of sync (main.py was
missing the production https://distroos.in domains).
"""
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.database import tenant_context
from app.utils.security import sign_jwt
from app.utils.origin_policy import ALLOWED_ORIGINS, is_origin_allowed

client = TestClient(app)


def test_mutating_endpoint_with_cookie_auth_rejects_untrusted_origin(db_session):
    """
    A PATCH request authenticated purely via the access_token cookie (no
    Authorization header) from an untrusted Origin must now be rejected --
    previously this endpoint (and every other one outside auth.py) had no
    origin check at all.
    """
    tenant = DistributorTenant(name="CSRF Middleware Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    cust = Customer(
        tenant_id=tenant.id, retailer_name="CSRF Test Store", customer_id="C-CSRF-1",
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=50000.0
    )
    db_session.add(cust)
    db_session.commit()

    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    response = client.patch(
        f"/api/v1/customers/{cust.id}?tenant_id={tenant.id}",
        json={"credit_limit": 60000.0, "billing_terms": "COD"},
        headers={"Origin": "https://malicious-attacker-site.com"},
    )
    client.cookies.clear()

    assert response.status_code == 403
    assert "CORS validation failed" in response.json()["detail"]

    # The credit limit must NOT have been changed by the rejected request.
    db_session.expire_all()
    db_session.refresh(cust)
    assert float(cust.credit_limit) == 50000.0


def test_mutating_endpoint_with_cookie_auth_allows_trusted_origin(db_session):
    """The same request from a trusted origin must succeed normally --
    this fix must not break legitimate same-site/allowed-origin traffic."""
    tenant = DistributorTenant(name="CSRF Trusted Origin Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    cust = Customer(
        tenant_id=tenant.id, retailer_name="CSRF Trusted Store", customer_id="C-CSRF-2",
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=50000.0
    )
    db_session.add(cust)
    db_session.commit()

    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    response = client.patch(
        f"/api/v1/customers/{cust.id}?tenant_id={tenant.id}",
        json={"credit_limit": 60000.0, "billing_terms": "COD"},
        headers={"Origin": "https://distroos.in"},
    )
    client.cookies.clear()

    assert response.status_code == 200


def test_mutating_endpoint_without_cookie_or_origin_is_unaffected(db_session):
    """A request with no Origin header at all (e.g. a non-browser client,
    server-to-server call) must pass through the new middleware completely
    unaffected -- matching _validate_origin's pre-existing "only check if
    Origin is present" semantics."""
    tenant = DistributorTenant(name="CSRF No Origin Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    cust = Customer(
        tenant_id=tenant.id, retailer_name="CSRF No Origin Store", customer_id="C-CSRF-3",
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=50000.0
    )
    db_session.add(cust)
    db_session.commit()

    token = sign_jwt({"user_id": str(uuid.uuid4()), "tenant_id": str(tenant.id), "role": "SUPER_ADMIN"})
    client.cookies.set("access_token", token)

    response = client.patch(
        f"/api/v1/customers/{cust.id}?tenant_id={tenant.id}",
        json={"credit_limit": 60000.0, "billing_terms": "COD"},
    )
    client.cookies.clear()

    assert response.status_code == 200


def test_main_cors_allowlist_matches_auth_origin_policy():
    """
    Regression test for the "two drifted allowlists" half of AUTH-4:
    app/main.py's CORS allowed_origins must include every production
    origin app.utils.origin_policy.ALLOWED_ORIGINS defines (previously it
    was missing https://distroos.in and https://www.distroos.in entirely
    unless the ALLOWED_ORIGINS env var happened to be set).
    """
    import app.main as main_module
    for origin in ALLOWED_ORIGINS:
        assert origin in main_module.allowed_origins, (
            f"{origin} is in the shared origin policy but missing from "
            "app.main's CORS allowed_origins -- the two allowlists have drifted again."
        )


def test_is_origin_allowed_accepts_localhost_only_in_development(monkeypatch):
    """Dev-mode localhost/127.0.0.1 origins (any port) must be accepted in
    development but rejected in production, matching the original
    _validate_origin behavior this was refactored out of."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert is_origin_allowed("http://localhost:3000") is True
    assert is_origin_allowed("http://127.0.0.1:5173") is True
    assert is_origin_allowed("https://random-untrusted-site.com") is False

    monkeypatch.setenv("ENVIRONMENT", "production")
    assert is_origin_allowed("http://localhost:3000") is False
    assert is_origin_allowed("https://distroos.in") is True
