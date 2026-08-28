import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_patch_customer_settings(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Customer Edit Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Customer
    cust = Customer(
        tenant_id=tenant.id,
        retailer_name="Settings Test Shop", customer_id="C-SETTINGS-1", address_text="Settings Street, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="0-15 Days",
        credit_limit=50000.0, outstanding_balance=1000.0
    )
    db_session.add(cust)
    db_session.commit()

    # Call PATCH endpoint
    response = client.patch(
        f"/api/v1/customers/{cust.id}?tenant_id={tenant.id}",
        json={
            "credit_limit": 75000.0,
            "billing_terms": "16-30 Days"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["customer_id"] == str(cust.id)
    assert data["credit_limit"] == 75000.0
    assert data["billing_terms"] == "16-30 Days"

    # Verify DB update
    db_session.expire_all()
    cust_db = db_session.get(Customer, cust.id)
    assert float(cust_db.credit_limit) == 75000.0
    assert cust_db.payment_terms == "16-30 Days"


def test_patch_customer_settings_not_found(client):
    fake_id = uuid.uuid4()
    fake_tenant_id = uuid.uuid4()
    response = client.patch(
        f"/api/v1/customers/{fake_id}?tenant_id={fake_tenant_id}",
        json={
            "credit_limit": 75000.0,
            "billing_terms": "16-30 Days"
        }
    )
    assert response.status_code == 404
    assert "Customer not found" in response.json()["detail"]


def test_patch_customer_settings_cross_tenant_is_rejected(db_session, client):
    """
    Regression test for CUST-2: a caller supplying another tenant's
    customer_id must not be able to modify that customer's credit
    limit/billing terms by passing a DIFFERENT (their own, or any
    arbitrary) tenant_id -- and must not succeed at all if no tenant_id
    ownership check is performed. Previously this endpoint had no tenant_id
    parameter whatsoever and derived tenant scoping only from the fetched
    customer row itself, after the fetch had already succeeded.
    """
    tenant_a = DistributorTenant(name="Tenant A Customer Owner")
    tenant_b = DistributorTenant(name="Tenant B Attacker")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    cust = Customer(
        tenant_id=tenant_a.id,
        retailer_name="Tenant A Shop", customer_id="C-CROSSTENANT-1", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="0-15 Days",
        credit_limit=50000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.commit()

    # Attacker (operating as Tenant B) tries to modify Tenant A's customer
    # by passing Tenant B's own id as tenant_id.
    response = client.patch(
        f"/api/v1/customers/{cust.id}?tenant_id={tenant_b.id}",
        json={"credit_limit": 999999.0, "billing_terms": "Hacked"}
    )
    assert response.status_code == 404

    db_session.expire_all()
    cust_db = db_session.get(Customer, cust.id)
    assert float(cust_db.credit_limit) == 50000.0
    assert cust_db.payment_terms == "0-15 Days"


def test_onboard_customer_success(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Onboard Tenant")
    db_session.add(tenant)
    db_session.commit()

    # Call POST endpoint
    response = client.post(
        f"/api/v1/customers?tenant_id={tenant.id}",
        json={
            "store_name": "New Onboarded Store",
            "contact_number": "+919999111122",
            "delivery_address": "Onboarding Colony, Bengaluru",
            "credit_limit": 25000.0,
            "billing_terms": "31-60 Days"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "id" in data
    assert "C-ONB-" in data["customer_id"]
    assert data["retailer_name"] == "New Onboarded Store"
    assert data["contact_number"] == "+919999111122"

    # Verify DB insertion
    db_session.expire_all()
    from app.models.customer import CustomerAlias
    alias = db_session.query(CustomerAlias).filter(CustomerAlias.alias_value == "+919999111122").first()
    assert alias is not None
    cust = db_session.get(Customer, alias.customer_id)
    assert cust is not None
    assert cust.retailer_name == "New Onboarded Store"
    assert cust.address_text == "Onboarding Colony, Bengaluru"
    assert float(cust.credit_limit) == 25000.0
    assert cust.payment_terms == "31-60 Days"


def test_onboard_customer_duplicate(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Onboard Duplicate Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup pre-existing Customer and Alias
    cust = Customer(
        retailer_name="Pre-existing Store", customer_id="C-EXIST-1", address_text="Exist St",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=50000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()

    from app.models.customer import CustomerAlias
    alias = CustomerAlias(tenant_id=tenant.id, customer_id=cust.id, alias_value="+919999333344")
    db_session.add(alias)
    db_session.commit()

    # Attempt to onboard with duplicate phone number
    response = client.post(
        f"/api/v1/customers?tenant_id={tenant.id}",
        json={
            "store_name": "Second Attempt Store",
            "contact_number": "+919999333344",
            "delivery_address": "Somewhere Else",
            "credit_limit": 10000.0,
            "billing_terms": "COD"
        }
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_onboard_customer_race_condition_caught_by_db_constraint(db_session, client, monkeypatch):
    """
    Regression test for CUST-3: onboard_customer's existing-alias check was
    a plain check-then-insert with no lock -- a classic TOCTOU race. This
    simulates the race directly by monkeypatching the pre-check to always
    report "no existing alias found" (as if a concurrent request's insert
    hadn't committed yet when this request's SELECT ran), then verifies the
    request still cannot succeed in creating a genuine duplicate: the
    DB-level unique constraint on customer_aliases(tenant_id, alias_value)
    must catch it and the endpoint must convert that into a clean 409
    instead of an unhandled 500.
    """
    tenant = DistributorTenant(name="Race Condition Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    from app.models.customer import CustomerAlias
    cust = Customer(
        tenant_id=tenant.id,
        retailer_name="Race Condition Store", customer_id="C-RACE-1", address_text="Race St",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=50000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()
    db_session.add(CustomerAlias(tenant_id=tenant.id, customer_id=cust.id, alias_value="+919888222233"))
    db_session.commit()

    # Force the pre-check to report "no existing alias" (simulating the
    # race window), so the request proceeds straight to the insert -- which
    # must then be caught by the DB constraint, not silently succeed.
    import app.api.v1.customers as customers_module
    from sqlalchemy.orm import Query
    original_first = Query.first

    def _patched_first(self):
        if self.column_descriptions and self.column_descriptions[0]["entity"] is CustomerAlias:
            return None
        return original_first(self)

    monkeypatch.setattr(Query, "first", _patched_first)

    response = client.post(
        f"/api/v1/customers?tenant_id={tenant.id}",
        json={
            "store_name": "Race Condition Duplicate Store",
            "contact_number": "+919888222233",
            "delivery_address": "Somewhere Else",
            "credit_limit": 10000.0,
            "billing_terms": "COD"
        }
    )
    assert response.status_code == 409

    db_session.expire_all()
    alias_count = db_session.query(CustomerAlias).filter(
        CustomerAlias.tenant_id == tenant.id, CustomerAlias.alias_value == "+919888222233"
    ).count()
    assert alias_count == 1, "The race must not result in two aliases with the same value"


def test_customer_statement(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Statement Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Customer
    cust = Customer(
        retailer_name="Statement Shop", customer_id="C-STATEMENT", address_text="Statement St",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=50000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()

    # Seed Ledger Entries
    from app.models.ledger import CustomerLedger
    db_session.add(CustomerLedger(
        tenant_id=tenant.id, customer_id=cust.id, type="DEBIT", amount=1000.0, reference_id="ORD-1"
    ))
    db_session.add(CustomerLedger(
        tenant_id=tenant.id, customer_id=cust.id, type="CREDIT", amount=400.0, reference_id="PAY-1"
    ))
    db_session.commit()

    # Call statement endpoint
    response = client.get(f"/api/v1/customers/{cust.id}/statement?tenant_id={tenant.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == str(cust.id)
    assert data["retailer_name"] == "Statement Shop"
    assert data["running_balance"] == 600.0

    statement = data["statement"]
    assert len(statement) == 2
    assert statement[0]["type"] == "DEBIT"
    assert statement[0]["amount"] == 1000.0
    assert statement[0]["running_balance"] == 1000.0
    assert statement[1]["type"] == "CREDIT"
    assert statement[1]["amount"] == 400.0
    assert statement[1]["running_balance"] == 600.0



def test_update_customer_notification_prefs_success(db_session, client):
    tenant = DistributorTenant(name="Notif Prefs Tenant")
    db_session.add(tenant)
    db_session.commit()

    cust = Customer(
        tenant_id=tenant.id,
        retailer_name="Notif Prefs Shop", customer_id="C-NOTIFPREFS-1", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="0-15 Days",
        whatsapp_notifications_enabled=True
    )
    db_session.add(cust)
    db_session.commit()

    response = client.patch(
        f"/api/v1/customers/{cust.id}/notification-prefs?tenant_id={tenant.id}",
        json={"whatsapp_notifications_enabled": False}
    )
    assert response.status_code == 200
    assert response.json()["whatsapp_notifications_enabled"] is False

    db_session.expire_all()
    assert db_session.get(Customer, cust.id).whatsapp_notifications_enabled is False


def test_update_customer_notification_prefs_cross_tenant_is_rejected(db_session, client):
    """
    Regression test for CUST-2: same cross-tenant IDOR fix applied to
    update_customer_notification_prefs.
    """
    tenant_a = DistributorTenant(name="Notif Tenant A")
    tenant_b = DistributorTenant(name="Notif Tenant B")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    cust = Customer(
        tenant_id=tenant_a.id,
        retailer_name="Notif Cross Tenant Shop", customer_id="C-NOTIFCROSS-1", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="0-15 Days",
        whatsapp_notifications_enabled=True
    )
    db_session.add(cust)
    db_session.commit()

    response = client.patch(
        f"/api/v1/customers/{cust.id}/notification-prefs?tenant_id={tenant_b.id}",
        json={"whatsapp_notifications_enabled": False}
    )
    assert response.status_code == 404

    db_session.expire_all()
    assert db_session.get(Customer, cust.id).whatsapp_notifications_enabled is True


def test_patch_customer_settings_rejects_negative_credit_limit(db_session, client):
    """
    Regression test for CUST-8: CustomerUpdatePayload.credit_limit was
    previously an unconstrained float -- only the frontend enforced
    credit_limit >= 0. The API itself accepted negative values, which
    would make check_credit_limit's `combined > credit_limit` comparison
    always true, silently locking the customer out of ordering entirely.
    """
    tenant = DistributorTenant(name="Negative Credit Limit Tenant")
    db_session.add(tenant)
    db_session.commit()

    cust = Customer(
        tenant_id=tenant.id,
        retailer_name="Negative Credit Shop", customer_id="C-NEGCREDIT-1", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="0-15 Days",
        credit_limit=50000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.commit()

    response = client.patch(
        f"/api/v1/customers/{cust.id}?tenant_id={tenant.id}",
        json={"credit_limit": -100.0, "billing_terms": "16-30 Days"}
    )
    assert response.status_code == 422

    db_session.expire_all()
    assert float(db_session.get(Customer, cust.id).credit_limit) == 50000.0


def test_onboard_customer_rejects_negative_credit_limit(db_session, client):
    """Regression test for CUST-8 on the onboard_customer creation path."""
    tenant = DistributorTenant(name="Negative Credit Onboard Tenant")
    db_session.add(tenant)
    db_session.commit()

    response = client.post(
        f"/api/v1/customers?tenant_id={tenant.id}",
        json={
            "store_name": "Negative Credit Store",
            "contact_number": "+919999444455",
            "delivery_address": "Somewhere",
            "credit_limit": -50.0,
            "billing_terms": "COD"
        }
    )
    assert response.status_code == 422


def test_list_customers_pagination_has_deterministic_tiebreaker(db_session, client):
    """
    Regression test for CUST-7: sorting by a non-unique column (e.g.
    credit_limit, where many customers can share the same default value)
    with only .offset/.limit and no secondary tiebreaker can reorder/
    duplicate/skip rows across pages whenever values tie. This proves
    that two consecutive full-list fetches, sorted by a tied column,
    return the exact same order both times (a stable sort), and that
    paginating through in two halves returns the same set of ids as one
    single fetch (no page-boundary duplication/loss).
    """
    tenant = DistributorTenant(name="Pagination Tiebreak Tenant")
    db_session.add(tenant)
    db_session.commit()

    # All customers share the identical credit_limit -- a real tie.
    for i in range(6):
        db_session.add(Customer(
            tenant_id=tenant.id, retailer_name=f"Tiebreak Shop {i}", customer_id=f"C-TIEBREAK-{i}",
            address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
            credit_limit=100000.0, outstanding_balance=0.0
        ))
    db_session.commit()

    resp1 = client.get(f"/api/v1/customers?tenant_id={tenant.id}&sort_by=credit_limit&limit=50")
    resp2 = client.get(f"/api/v1/customers?tenant_id={tenant.id}&sort_by=credit_limit&limit=50")
    assert resp1.status_code == 200 and resp2.status_code == 200
    ids_1 = [item["id"] for item in resp1.json()["items"]]
    ids_2 = [item["id"] for item in resp2.json()["items"]]
    assert ids_1 == ids_2, "Repeated requests with tied sort values must return the same stable order"

    # Paginate through in two pages of 3 -- must cover the same 6 ids with no overlap/gap.
    page1 = client.get(f"/api/v1/customers?tenant_id={tenant.id}&sort_by=credit_limit&skip=0&limit=3").json()["items"]
    page2 = client.get(f"/api/v1/customers?tenant_id={tenant.id}&sort_by=credit_limit&skip=3&limit=3").json()["items"]
    paged_ids = {item["id"] for item in page1} | {item["id"] for item in page2}
    assert paged_ids == set(ids_1), "Paginating through tied rows must not duplicate or skip any customer"


def test_list_customers_search_matches_customer_alias(db_session, client):
    """
    Regression test for CUST-6: customer search previously only matched
    Customer.retailer_name / Customer.phone_number. A customer with an
    additional identity in customer_aliases (e.g. a second WhatsApp
    number -- which the ingestion whitelist in ingestion_service.py DOES
    check via CustomerAlias) was invisible to this staff-facing search
    even though the customer genuinely exists.
    """
    from app.models.customer import CustomerAlias

    tenant = DistributorTenant(name="Search Alias Tenant")
    db_session.add(tenant)
    db_session.commit()

    cust = Customer(
        tenant_id=tenant.id, retailer_name="Alias Search Shop", customer_id="C-ALIASSEARCH-1",
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        phone_number="+919000000001"
    )
    db_session.add(cust)
    db_session.flush()
    db_session.add(CustomerAlias(tenant_id=tenant.id, customer_id=cust.id, alias_value="+919888777766"))
    db_session.commit()

    # Search by the ALIAS number, not the primary phone_number.
    response = client.get(f"/api/v1/customers?tenant_id={tenant.id}&search=9888777766")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(cust.id) in ids, "Searching by a registered CustomerAlias value must find the customer"
