import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.ledger import CustomerLedger
from app.models.payment import Payment
from app.models.order import Order
from app.models.invoice import Invoice
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
    db_session.flush()

    # 2b. Create an order + invoice to back the 25,000 outstanding balance
    backing_order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-VOUCHER-BACKING",
        source="Portal",
        customer_id=customer.id,
    )
    db_session.add(backing_order)
    db_session.flush()
    backing_invoice = Invoice(
        tenant_id=tenant.id,
        order_id=backing_order.id,
        customer_id=customer.id,
        gstin=customer.gstin,
        total_amount=25000.0,
        irn_status="Cleared",
        qr_code_status="Generated",
        payment_status="UNPAID",
        amount_paid=0.0,
    )
    db_session.add(backing_invoice)

    # Seed the matching DEBIT ledger entry so the ledger is consistent with
    # the 25,000 outstanding_balance set on the customer above.
    # record_transaction() recomputes outstanding_balance from the ledger,
    # so test data must be truthful: the ₹25,000 balance must exist as a
    # DEBIT ledger entry, not only as a raw field on the customer row.
    db_session.add(CustomerLedger(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        customer_id=customer.id,
        type="DEBIT",
        amount=25000.0,
        reference_id="ORD-VOUCHER-BACKING",
        description="Backing order confirmed (test seed)"
    ))
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

def test_allocate_payment_fifo_success(db_session, client):
    from datetime import datetime, timedelta
    from app.models.invoice import Invoice
    from app.models.order import Order
    from app.models.payment import PaymentInvoiceLink
    
    # 1. Setup Tenant
    tenant = DistributorTenant(name="FIFO Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Customer with outstanding balance
    customer = Customer(
        retailer_name="FIFO Debtor",
        customer_id="C-FIFO-1",
        address_text="FIFO Lane, Mumbai",
        gstin="27BBBBB2222B2Z2",
        tax_group="GST",
        payment_terms="Net 30",
        credit_limit=100000.0,
        outstanding_balance=35000.0
    )
    db_session.add(customer)
    db_session.commit()

    # 3. Setup two Orders and Invoices (Invoice A: 15,000, created 5 days ago; Invoice B: 20,000, created 2 days ago)
    order_a = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-FIFO-A",
        source="Portal",
        customer_id=customer.id,
        created_at=datetime.utcnow() - timedelta(days=5)
    )
    order_b = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-FIFO-B",
        source="Portal",
        customer_id=customer.id,
        created_at=datetime.utcnow() - timedelta(days=2)
    )
    db_session.add(order_a)
    db_session.add(order_b)
    db_session.commit()

    invoice_a = Invoice(
        tenant_id=tenant.id,
        order_id=order_a.id,
        customer_id=customer.id,
        gstin="27BBBBB2222B2Z2",
        total_amount=15000.00,
        payment_status="UNPAID",
        amount_paid=0.00,
        created_at=order_a.created_at
    )
    invoice_b = Invoice(
        tenant_id=tenant.id,
        order_id=order_b.id,
        customer_id=customer.id,
        gstin="27BBBBB2222B2Z2",
        total_amount=20000.00,
        payment_status="UNPAID",
        amount_paid=0.00,
        created_at=order_b.created_at
    )
    db_session.add(invoice_a)
    db_session.add(invoice_b)
    db_session.commit()

    # 4. Call endpoint to create a payment voucher for 25,000
    response = client.post(
        f"/api/v1/payments/collection-voucher?tenant_id={tenant.id}",
        json={
            "customer_id": str(customer.id),
            "amount": 25000.0,
            "method": "CARD",
            "reference_number": "CARD-TXN-12345"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"

    # 5. Verify database mutations
    db_session.expire_all()

    # Invoice A (15,000) should be fully PAID
    inv_a_db = db_session.get(Invoice, invoice_a.id)
    assert inv_a_db.payment_status == "PAID"
    assert float(inv_a_db.amount_paid) == 15000.00

    # Invoice B (20,000) should be PARTIALLY_PAID (10,000 paid)
    inv_b_db = db_session.get(Invoice, invoice_b.id)
    assert inv_b_db.payment_status == "PARTIALLY_PAID"
    assert float(inv_b_db.amount_paid) == 10000.00

    # PaymentInvoiceLinks should exist
    links = db_session.query(PaymentInvoiceLink).filter(PaymentInvoiceLink.payment_id == uuid.UUID(data["payment_id"])).all()
    assert len(links) == 2
    
    # Check link amounts
    link_a = next(l for l in links if l.invoice_id == invoice_a.id)
    link_b = next(l for l in links if l.invoice_id == invoice_b.id)
    assert float(link_a.amount_allocated) == 15000.00
    assert float(link_b.amount_allocated) == 10000.00
