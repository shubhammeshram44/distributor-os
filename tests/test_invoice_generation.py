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
    # GST is now split into CGST + SGST (each half of the 18% product rate)
    # instead of a single combined "GST (18%)" line — legally required for an
    # intra-state GST tax invoice.
    assert "CGST:" in pdf_text
    assert "SGST:" in pdf_text
    assert "45.00" in pdf_text  # 500 subtotal × 18% ÷ 2 = 45 each


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

    # Setup Order (Confirmed status, RETAIL_INVOICE)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-RET-INV-1",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="RETAIL_INVOICE"
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


def test_invoice_pdf_partial_allocation(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Partial Allocation Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product with stock = 300
    p = Product(sku_id="PROD-PARTIAL-INV", brand="BrandX", category="TestCategory", pack_size="1 unit", base_price=7.0, stock_quantity=300)
    db_session.add(p)
    db_session.flush()

    from app.models.inventory import Inventory
    inv = Inventory(
        tenant_id=tenant.id,
        sku_id=p.id,
        location="WH1",
        quantity_on_hand=300,
        low_stock_threshold=10
    )
    db_session.add(inv)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Partial Invoice Stores", customer_id="C-PARTIAL-INV", address_text="Some Street",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD", credit_limit=100000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-PARTIAL-INV-1",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="GST_TAX_INVOICE"
    )
    db_session.add(order)
    db_session.flush()

    # Add line item with quantity = 400 (which is > 300)
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=400, unit_price=7.0))

    # Ledger transition: None -> Draft
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # Confirm order via confirm endpoint
    response = client.post(f"/api/v1/orders/{order.id}/confirm")
    assert response.status_code == 200

    # Get PDF invoice
    response = client.get(f"/api/v1/orders/{order.id}/invoice")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    
    # Extract and assert text content
    pdf_text = extract_text_from_pdf(response.content)
    # The subtotal should reflect 300 * 7 = 2100, not 400 * 7 = 2800.
    # GST is now split into CGST + SGST: 2100 * 18% = 378 total, i.e. 189 each
    # (not a single combined 378 line), not 2800 * 18% = 504.
    # Total Payable should be 2100 + 189 + 189 = 2478, not 2800 + 504 = 3304.
    assert "300" in pdf_text
    assert "400" not in pdf_text
    assert "2,100.00" in pdf_text
    assert "2,800.00" not in pdf_text
    assert "189.00" in pdf_text
    assert "504.00" not in pdf_text
    assert "2,478.00" in pdf_text
    assert "3,304.00" not in pdf_text


def test_invoice_uses_per_product_gst_rate_and_hsn_code(db_session, client):
    """A product with a non-default GST rate (5% instead of 18%) and an HSN
    code should be reflected accurately on the tax invoice PDF."""
    tenant = DistributorTenant(name="Per-Product GST Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(
        sku_id="PROD-5PCT-GST", brand="LowRateBrand", category="Essentials",
        pack_size="1kg", base_price=100.0, stock_quantity=50,
        gst_rate=5.0, hsn_code="10063000",
    )
    db_session.add(p)
    db_session.flush()

    from app.models.inventory import Inventory
    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=50, low_stock_threshold=10)
    db_session.add(inv)
    db_session.flush()

    cust = Customer(
        retailer_name="Low Rate Stores", customer_id="C-5PCT", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id, internal_order_id="ORD-5PCT-GST-1", source="WhatsApp",
        customer_id=cust.id, invoice_type="GST_TAX_INVOICE"
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=100.0))
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    response = client.post(f"/api/v1/orders/{order.id}/confirm")
    assert response.status_code == 200

    response = client.get(f"/api/v1/orders/{order.id}/invoice")
    assert response.status_code == 200
    pdf_text = extract_text_from_pdf(response.content)

    # Subtotal 1000, GST at 5% = 50 total -> 25 CGST + 25 SGST (not 18%'s 90 each)
    # Compare with newlines stripped since long HSN codes / narrow PDF columns
    # can wrap the digits across a line break in text extraction.
    assert "10063000" in pdf_text.replace("\n", "")  # HSN code printed
    assert "25.00" in pdf_text
    assert "90.00" not in pdf_text

    from app.models.invoice import Invoice
    invoice = db_session.query(Invoice).filter_by(order_id=order.id).one()
    assert float(invoice.cgst_amount) == 25.0
    assert float(invoice.sgst_amount) == 25.0
    assert invoice.invoice_number is not None
    assert invoice.invoice_number.startswith("INV/")


def test_sequential_invoice_numbering_increments_per_tenant(db_session, client):
    """Confirming two orders for the same tenant should produce two distinct,
    sequential invoice numbers in the same financial year."""
    tenant = DistributorTenant(name="Sequential Invoice Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-SEQ-1", brand="SeqBrand", category="Cat", pack_size="1u", base_price=10.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    from app.models.inventory import Inventory
    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=100, low_stock_threshold=10)
    db_session.add(inv)
    db_session.flush()

    cust = Customer(
        retailer_name="Sequential Stores", customer_id="C-SEQ", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    from app.models.invoice import Invoice
    invoice_numbers = []
    for i in range(2):
        order = Order(
            tenant_id=tenant.id, internal_order_id=f"ORD-SEQ-{i}", source="WhatsApp", customer_id=cust.id
        )
        db_session.add(order)
        db_session.flush()
        db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=1, unit_price=10.0))
        db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
        db_session.commit()

        resp = client.post(f"/api/v1/orders/{order.id}/confirm")
        assert resp.status_code == 200

        invoice = db_session.query(Invoice).filter_by(order_id=order.id).one()
        invoice_numbers.append(invoice.invoice_number)

    assert invoice_numbers[0] != invoice_numbers[1]
    assert invoice_numbers[0].rsplit("/", 1)[0] == invoice_numbers[1].rsplit("/", 1)[0]  # same FY prefix
    seq0 = int(invoice_numbers[0].rsplit("/", 1)[1])
    seq1 = int(invoice_numbers[1].rsplit("/", 1)[1])
    assert seq1 == seq0 + 1


def test_zero_value_order_does_not_create_invoice(db_session, client):
    """Confirming an order with 0 units available anywhere should not create
    an Invoice row at all — previously a $0.00 invoice was created, polluting
    the payment reminder sweep and customer outstanding balance."""
    from app.models.inventory import Inventory
    from app.models.invoice import Invoice

    tenant = DistributorTenant(name="Zero Value Invoice Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-ZERO-INV", brand="ZeroBrand", category="Cat", pack_size="1u", base_price=10.0, stock_quantity=0)
    db_session.add(p)
    db_session.flush()

    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=0, low_stock_threshold=10)
    db_session.add(inv)
    db_session.flush()

    cust = Customer(
        retailer_name="Zero Value Stores", customer_id="C-ZERO-INV", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(tenant_id=tenant.id, internal_order_id="ORD-ZERO-INV-1", source="WhatsApp", customer_id=cust.id)
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=10.0))
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    resp = client.post(f"/api/v1/orders/{order.id}/confirm")
    assert resp.status_code == 200

    invoice = db_session.query(Invoice).filter_by(order_id=order.id).first()
    assert invoice is None
