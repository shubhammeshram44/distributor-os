import pytest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app as fastapi_app
import app.services.payment_gateway
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order, OrderLineItem
from app.models.payment_session import PaymentSession
from app.utils.encryption import encrypt_secret

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(fastapi_app)

def test_payment_session_created_on_confirmation(db_session, client):
    # Setup Tenant, Customer, Product, Inventory, Order, LineItem
    tenant = DistributorTenant(
        name="Razorpay Test Tenant",
        razorpay_key_id="rzp_test_key123",
        razorpay_key_secret_enc=encrypt_secret("secret123")
    )
    db_session.add(tenant)
    db_session.flush()

    customer = Customer(
        tenant_id=tenant.id,
        retailer_name="Razorpay Retailer",
        payment_terms="Net 30",
        phone_number="+919876543210"
    )
    db_session.add(customer)
    db_session.flush()

    p = Product(
        tenant_id=tenant.id,
        sku_id="PROD1",
        base_price=100.0,
        brand="Brand1",
        category="Snacks",
        pack_size="10",
        stock_quantity=100
    )
    db_session.add(p)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-100",
        source="WhatsApp",
        customer_id=customer.id,
        status="Draft"
    )
    db_session.add(order)
    db_session.flush()

    item = OrderLineItem(
        tenant_id=tenant.id,
        order_id=order.id,
        quantity=5,
        unit_price=100.0,
        unmatched_raw_text="Brand1 5 units"
    )
    db_session.add(item)

    from app.models.inventory import Inventory
    inv = Inventory(
        tenant_id=tenant.id,
        sku_id=p.id,
        location="WH-1",
        quantity_on_hand=100,
        quantity_committed=0
    )
    db_session.add(inv)
    db_session.commit()

    # Mock Razorpay PaymentGateway create_payment_link
    fake_response = {
        "id": "plink_test123",
        "short_url": "https://rzp.io/test",
        "url": "https://razorpay.com/test",
        "status": "created"
    }

    with patch("app.services.payment_gateway.PaymentGateway.create_payment_link", return_value=fake_response) as mock_create:
        response = client.post(
            f"/api/v1/orders/{order.id}/batch-confirm",
            json={
                "invoice_type": "RETAIL_INVOICE",
                "resolved_items": [
                    {
                        "item_id": str(item.id),
                        "product_id": str(p.id)
                    }
                ]
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify PaymentSession exists and is ACTIVE
        session = db_session.query(PaymentSession).filter(
            PaymentSession.order_id == order.id
        ).first()
        
        assert session is not None
        assert session.status == "ACTIVE"
        assert session.payment_link_url == "https://rzp.io/test"
        assert session.razorpay_payment_link_id == "plink_test123"
        assert float(session.amount) == 500.0  # 5 units * 100.0 base price
        
        mock_create.assert_called_once()


def test_get_payment_link_endpoint(db_session, client):
    # Setup Tenant, Customer, Product, Inventory, Order, LineItem
    tenant = DistributorTenant(
        name="Razorpay Endpoint Tenant",
        razorpay_key_id="rzp_test_key456",
        razorpay_key_secret_enc=encrypt_secret("secret456")
    )
    db_session.add(tenant)
    db_session.flush()

    customer = Customer(
        tenant_id=tenant.id,
        retailer_name="Razorpay Retailer 2",
        payment_terms="Net 30",
        phone_number="+919876543211"
    )
    db_session.add(customer)
    db_session.flush()

    p = Product(
        tenant_id=tenant.id,
        sku_id="PROD2",
        base_price=150.0,
        brand="Brand2",
        category="Beverages",
        pack_size="24",
        stock_quantity=50
    )
    db_session.add(p)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-101",
        source="WhatsApp",
        customer_id=customer.id,
        status="Draft"
    )
    db_session.add(order)
    db_session.flush()

    item = OrderLineItem(
        tenant_id=tenant.id,
        order_id=order.id,
        quantity=2,
        unit_price=150.0,
        unmatched_raw_text="Brand2 2 units"
    )
    db_session.add(item)
    
    from app.models.inventory import Inventory
    inv = Inventory(
        tenant_id=tenant.id,
        sku_id=p.id,
        location="WH-1",
        quantity_on_hand=50,
        quantity_committed=0
    )
    db_session.add(inv)
    db_session.commit()

    # Call confirm order
    fake_response = {
        "id": "plink_test456",
        "short_url": "https://rzp.io/test456",
        "url": "https://razorpay.com/test456",
        "status": "created"
    }

    with patch("app.services.payment_gateway.PaymentGateway.create_payment_link", return_value=fake_response) as mock_create:
        response = client.post(
            f"/api/v1/orders/{order.id}/batch-confirm",
            json={
                "invoice_type": "RETAIL_INVOICE",
                "resolved_items": [
                    {
                        "item_id": str(item.id),
                        "product_id": str(p.id)
                    }
                ]
            }
        )
        assert response.status_code == 200
        
        # Get invoice id
        from app.models.invoice import Invoice
        invoice = db_session.query(Invoice).filter(Invoice.order_id == order.id).first()
        assert invoice is not None
        
        # Fetch payment link via GET endpoint
        get_response = client.get(
            f"/api/v1/payments/payment-link?invoice_id={invoice.id}&tenant_id={tenant.id}"
        )
        assert get_response.status_code == 200
        assert get_response.json()["payment_link_url"] == "https://rzp.io/test456"
        assert get_response.json()["status"] == "ACTIVE"
        
        # Verify mock wasn't called again since active link exists
        assert mock_create.call_count == 1


def test_razorpay_webhook_paid_event(db_session, client):
    # Setup Tenant, Customer, Product, Inventory, Order, LineItem
    tenant = DistributorTenant(
        name="Razorpay Webhook Tenant",
        razorpay_key_id="rzp_test_key789",
        razorpay_key_secret_enc=encrypt_secret("secret789")
    )
    db_session.add(tenant)
    db_session.flush()

    customer = Customer(
        tenant_id=tenant.id,
        retailer_name="Razorpay Retailer 3",
        payment_terms="Net 30",
        phone_number="+919876543212"
    )
    db_session.add(customer)
    db_session.flush()

    p = Product(
        tenant_id=tenant.id,
        sku_id="PROD3",
        base_price=200.0,
        brand="Brand3",
        category="Beverages",
        pack_size="12",
        stock_quantity=50
    )
    db_session.add(p)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-102",
        source="WhatsApp",
        customer_id=customer.id,
        status="Draft"
    )
    db_session.add(order)
    db_session.flush()

    item = OrderLineItem(
        tenant_id=tenant.id,
        order_id=order.id,
        quantity=3,
        unit_price=200.0,
        unmatched_raw_text="Brand3 3 units"
    )
    db_session.add(item)
    
    from app.models.inventory import Inventory
    inv = Inventory(
        tenant_id=tenant.id,
        sku_id=p.id,
        location="WH-1",
        quantity_on_hand=50,
        quantity_committed=0
    )
    db_session.add(inv)
    db_session.commit()

    # Call confirm order
    fake_response = {
        "id": "plink_test789",
        "short_url": "https://rzp.io/test789",
        "url": "https://razorpay.com/test789",
        "status": "created"
    }

    with patch("app.services.payment_gateway.PaymentGateway.create_payment_link", return_value=fake_response) as mock_create:
        response = client.post(
            f"/api/v1/orders/{order.id}/batch-confirm",
            json={
                "invoice_type": "RETAIL_INVOICE",
                "resolved_items": [
                    {
                        "item_id": str(item.id),
                        "product_id": str(p.id)
                    }
                ]
            }
        )
        assert response.status_code == 200

        # Now mock webhook signature verification and post the paid webhook
        with patch("app.api.v1.payments.verify_razorpay_signature", return_value=True):
            webhook_payload = {
                "event": "payment_link.paid",
                "payload": {
                    "payment_link": {
                        "entity": {
                            "id": "plink_test789"
                        }
                    },
                    "payment": {
                        "entity": {
                            "id": "pay_test789",
                            "amount": 60000  # 600.00 INR in paise
                        }
                    }
                }
            }
            webhook_response = client.post(
                "/api/v1/payments/razorpay-webhook",
                headers={"X-Razorpay-Signature": "fake-sig"},
                json=webhook_payload
            )
            assert webhook_response.status_code == 200
            
            # Verify PaymentSession is updated to PAID
            session = db_session.query(PaymentSession).filter(
                PaymentSession.razorpay_payment_link_id == "plink_test789"
            ).first()
            assert session.status == "PAID"
            assert session.razorpay_payment_id == "pay_test789"
            assert session.paid_at is not None
            
            # Verify Invoice is fully paid / reconciled
            from app.models.invoice import Invoice
            invoice = db_session.query(Invoice).filter(Invoice.order_id == order.id).first()
            assert float(invoice.amount_paid) == 600.0
            assert invoice.payment_status == "PAID"


def test_preferred_invoice_paid_first(db_session):
    from app.services.payment_service import process_payment
    from app.models.invoice import Invoice
    from app.models.tenant import DistributorTenant
    from app.models.customer import Customer
    from app.models.order import Order
    from datetime import datetime, timedelta

    # 1. Setup Tenant and Customer
    tenant = DistributorTenant(name="Preferred Invoice Tenant")
    db_session.add(tenant)
    db_session.flush()

    customer = Customer(
        tenant_id=tenant.id,
        retailer_name="Preferred Retailer",
        payment_terms="Net 30",
        phone_number="+919876543219"
    )
    db_session.add(customer)
    db_session.flush()

    # Invoices reference real orders (order_id is a foreign key to orders.id)
    order_older = Order(
        tenant_id=tenant.id,
        customer_id=customer.id,
        internal_order_id="ORD-PREF-OLDER",
        source="Test",
        status="Confirmed"
    )
    order_newer = Order(
        tenant_id=tenant.id,
        customer_id=customer.id,
        internal_order_id="ORD-PREF-NEWER",
        source="Test",
        status="Confirmed"
    )
    db_session.add_all([order_older, order_newer])
    db_session.flush()

    # 2. Create two unpaid invoices (older one 500, newer one 1000)
    invoice_older = Invoice(
        tenant_id=tenant.id,
        order_id=order_older.id,
        gstin="29AAAAA1111A1Z1",
        total_amount=500.0,
        irn_status="Cleared",
        qr_code_status="Generated",
        customer_id=customer.id,
        payment_status="UNPAID",
        amount_paid=0.0,
        created_at=datetime.utcnow() - timedelta(days=2)
    )
    db_session.add(invoice_older)

    invoice_newer = Invoice(
        tenant_id=tenant.id,
        order_id=order_newer.id,
        gstin="29AAAAA1111A1Z1",
        total_amount=1000.0,
        irn_status="Cleared",
        qr_code_status="Generated",
        customer_id=customer.id,
        payment_status="UNPAID",
        amount_paid=0.0,
        created_at=datetime.utcnow() - timedelta(days=1)
    )
    db_session.add(invoice_newer)
    
    # Update customer outstanding balance to match invoice sum
    customer.outstanding_balance = 1500.0
    db_session.commit()

    # 3. Call process_payment with preferred_invoice_id pointing to invoice_newer
    payment = process_payment(
        db=db_session,
        tenant_id=tenant.id,
        customer_id=customer.id,
        amount=1000.0,
        method="RAZORPAY_UPI",
        reference_number="pay_pref_123",
        preferred_invoice_id=invoice_newer.id
    )
    db_session.commit()

    # 4. Asserts
    db_session.refresh(invoice_older)
    db_session.refresh(invoice_newer)
    db_session.refresh(customer)

    assert invoice_newer.payment_status == "PAID"
    assert float(invoice_newer.amount_paid) == 1000.0
    assert invoice_older.payment_status == "UNPAID"
    assert float(invoice_older.amount_paid) == 0.0
    assert float(customer.outstanding_balance) == 500.0
