import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.ledger import CustomerLedger
from app.models.payment import Payment
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_create_collection_voucher_success(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Payments Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Customer with outstanding balance
    customer = Customer(
        retailer_name="Debtor Shop",
        customer_id="C-DEBTOR-1",
        address_text="Debtor Lane, Mumbai",
        gstin="27BBBBB2222B2Z2",
        tax_group="GST",
        payment_terms="Net 30",
        credit_limit=100000.0,
        outstanding_balance=25000.0
    )
    db_session.add(customer)
    db_session.commit()

    # 3. Call endpoint to create a payment voucher
    response = client.post(
        f"/api/v1/payments/collection-voucher?tenant_id={tenant.id}",
        json={
            "customer_id": str(customer.id),
            "amount": 10000.0,
            "method": "UPI",
            "reference_number": "UPI-TXN-12345"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "payment_id" in data
    assert data["customer_id"] == str(customer.id)
    assert data["amount"] == 10000.0
    assert data["method"] == "UPI"
    assert data["reference_number"] == "UPI-TXN-12345"
    assert data["payment_status"] == "COMPLETED"

    # 4. Verify Database mutations
    db_session.expire_all()
    
    # Customer outstanding balance should be decremented (25000 - 10000 = 15000)
    customer_db = db_session.get(Customer, customer.id)
    assert float(customer_db.outstanding_balance) == 15000.0

    # Payment record should exist
    payment_id = uuid.UUID(data["payment_id"])
    payment_db = db_session.get(Payment, payment_id)
    assert payment_db is not None
    assert float(payment_db.amount) == 10000.0
    assert payment_db.method == "UPI"
    assert payment_db.reference_number == "UPI-TXN-12345"
    assert payment_db.status == "COMPLETED"

    # Customer ledger credit entry should exist
    ledger_entry = db_session.query(CustomerLedger).filter(
        CustomerLedger.customer_id == customer.id,
        CustomerLedger.type == "CREDIT"
    ).first()
    assert ledger_entry is not None
    assert float(ledger_entry.amount) == 10000.0
    assert ledger_entry.reference_id == "UPI-TXN-12345"

def test_create_collection_voucher_customer_not_found(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Payments Fail Tenant")
    db_session.add(tenant)
    db_session.commit()

    fake_customer_id = uuid.uuid4()
    response = client.post(
        f"/api/v1/payments/collection-voucher?tenant_id={tenant.id}",
        json={
            "customer_id": str(fake_customer_id),
            "amount": 5000.0,
            "method": "CASH"
        }
    )
    assert response.status_code == 404
    assert "Customer not found" in response.json()["detail"]
