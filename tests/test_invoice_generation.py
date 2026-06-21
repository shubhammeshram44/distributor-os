import io
import uuid
import pypdf
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.product import Product
from app.models.customer import Customer
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)


def extract_text_from_pdf(pdf_bytes):
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def test_gst_tax_invoice_pdf_content(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="GST Invoice Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-GST-INV", brand="GSTBrand", category="TestCategory", pack_size="100ml", base_price=50.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="GST Invoice Stores", customer_id="C-GST-INV", address_text="GST Street, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order (Confirmed status, GST_TAX_INVOICE)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-GST-INV-1",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="GST_TAX_INVOICE"
    )
    db_session.add(order)
    db_session.flush()

    # Add line item
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=50.0))

    # Ledger transition: None -> Confirmed
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Confirmed", updated_by="admin"))
    db_session.commit()

    # Get PDF invoice
    response = client.get(f"/api/v1/orders/{order.id}/invoice")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    
    # Extract and assert text content
    pdf_text = extract_text_from_pdf(response.content)
    assert "TAX INVOICE" in pdf_text
    assert "RETAIL INVOICE" not in pdf_text
    assert "GSTIN: 07AAAAA1111A1Z1" in pdf_text
    assert "GST (18%):" in pdf_text


def test_retail_cash_invoice_pdf_content(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Retail Invoice Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-RETAIL-INV", brand="RetailBrand", category="TestCategory", pack_size="100ml", base_price=50.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Retail Invoice Stores", customer_id="C-RET-INV", address_text="Retail Street, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order (Confirmed status, RETAIL_CASH_INVOICE)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-RET-INV-1",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="RETAIL_CASH_INVOICE"
    )
    db_session.add(order)
    db_session.flush()

    # Add line item
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=50.0))

    # Ledger transition: None -> Confirmed
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Confirmed", updated_by="admin"))
    db_session.commit()

    # Get PDF invoice
    response = client.get(f"/api/v1/orders/{order.id}/invoice")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    
    # Extract and assert text content
    pdf_text = extract_text_from_pdf(response.content)
    assert "RETAIL INVOICE" in pdf_text
    assert "TAX INVOICE" not in pdf_text
    assert "GSTIN:" not in pdf_text
    assert "GST (18%):" not in pdf_text
