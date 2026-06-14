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
        retailer_name="Settings Test Shop", customer_id="C-SETTINGS-1", address_text="Settings Street, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="0-15 Days",
        credit_limit=50000.0, outstanding_balance=1000.0
    )
    db_session.add(cust)
    db_session.commit()

    # Call PATCH endpoint
    response = client.patch(
        f"/api/v1/customers/{cust.id}",
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
    response = client.patch(
        f"/api/v1/customers/{fake_id}",
        json={
            "credit_limit": 75000.0,
            "billing_terms": "16-30 Days"
        }
    )
    assert response.status_code == 404
    assert "Customer not found" in response.json()["detail"]


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

