import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.order import Order
from app.services.payment_session_service import get_or_create_payment_session

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_razorpay_connect_invalid_keys(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Razorpay Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    # Call endpoint with invalid credentials
    response = client.post(
        f"/api/v1/tenant/razorpay-connect?tenant_id={tenant.id}",
        json={
            "key_id": "rzp_test_invalid123",
            "key_secret": "invalid_secret_abc"
        }
    )
    assert response.status_code == 400
    assert "Invalid Razorpay credentials" in response.json()["detail"]

def test_razorpay_connect_no_keys_blocks_payment_session(db_session):
    # Setup Tenant without Razorpay connected
    tenant = DistributorTenant(name="No Razorpay Tenant")
    db_session.add(tenant)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        tenant_id=tenant.id,
        retailer_name="Test Retailer",
        customer_id="C-TEST",
        tax_group="GST",
        payment_terms="Net 15",
        credit_limit=10000.0,
        outstanding_balance=500.0
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order and Invoice
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-1",
        source="Portal",
        customer_id=cust.id,
        status="Draft"
    )
    db_session.add(order)
    db_session.flush()

    invoice = Invoice(
        tenant_id=tenant.id,
        order_id=order.id,
        customer_id=cust.id,
        gstin="29AAAAA1111A1Z1",
        total_amount=500.0,
        payment_status="UNPAID",
        amount_paid=0.0
    )
    db_session.add(invoice)
    db_session.commit()

    # Attempt to create payment session - should raise ValueError because no keys connected
    with pytest.raises(ValueError) as exc_info:
        get_or_create_payment_session(
            db=db_session,
            invoice=invoice,
            customer=cust,
            order_id=order.id,
            tenant_id=tenant.id
        )
    assert "Razorpay not connected" in str(exc_info.value)
