import uuid
import pytest
from app.models.tenant import DistributorTenant
from app.models.product import Product, ProductAlias
from app.models.inventory import Inventory
from app.models.ingestion import IngestionJob, IngestionStaging
from app.services.ingestion_service import IngestionService
from app.database import tenant_context

def test_csv_ingestion_partial_success(db_session):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Vikas Sales Corp")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Products in catalog
    p1 = Product(sku_id="SKU-HUL-100", brand="HUL", category="Soap", pack_size="100g", base_price=30.00)
    p2 = Product(sku_id="SKU-ITC-200", brand="ITC", category="Aata", pack_size="10kg", base_price=400.00)
    db_session.add_all([p1, p2])
    db_session.flush()

    # Add an alias for p2
    alias_p2 = ProductAlias(product_id=p2.id, alias_name="Aashirvaad Gold")
    db_session.add(alias_p2)
    db_session.commit()

    # 3. Formulate raw CSV payload
    # Row 1: SKU-HUL-100 (Correct SKU) -> Should validate
    # Row 2: Aashirvaad Gold (Correct Alias) -> Should validate
    # Row 3: SKU-UNKNOWN (Doesn't exist) -> Should fail
    # Row 4: SKU-HUL-100 but invalid negative stock -> Should fail
    csv_content = (
        "ItemCode,StockQuantity,ReservedQty\n"
        "SKU-HUL-100,150,25\n"
        "Aashirvaad Gold,80,10\n"
        "SKU-UNKNOWN,500,0\n"
        "SKU-HUL-100,-10,5\n"
    ).encode("utf-8")

    # 4. Process Ingestion
    service = IngestionService()
    job = service.ingest_file(
        db=db_session,
        tenant_id=tenant.id,
        file_content=csv_content,
        filename="inventory_updates.csv"
    )

    # 5. Assertions
    assert job.status == "Completed"
    assert job.total_rows == 4
    assert job.successful_rows == 2
    assert job.failed_rows == 2

    # Check Staging Row Statuses
    staging_rows = db_session.query(IngestionStaging).filter_by(job_id=job.id).all()
    assert len(staging_rows) == 4

    # Assert Row 1 (Success)
    row1 = next(r for r in staging_rows if r.raw_data.get("ItemCode") == "SKU-HUL-100" and r.raw_data.get("StockQuantity") == "150")
    assert row1.status == "Validated"
    assert row1.error_message is None

    # Assert Row 2 (Success via Alias)
    row2 = next(r for r in staging_rows if r.raw_data.get("ItemCode") == "Aashirvaad Gold")
    assert row2.status == "Validated"
    assert row2.error_message is None

    # Assert Row 3 (Fail: SKU doesn't exist)
    row3 = next(r for r in staging_rows if r.raw_data.get("ItemCode") == "SKU-UNKNOWN")
    assert row3.status == "Failed"
    assert "does not exist in product catalog" in row3.error_message

    # Assert Row 4 (Fail: negative quantity)
    row4 = next(r for r in staging_rows if r.raw_data.get("ItemCode") == "SKU-HUL-100" and r.raw_data.get("StockQuantity") == "-10")
    assert row4.status == "Failed"
    assert "cannot be negative" in row4.error_message

    # Check final stock levels committed to Inventory
    inv_p1 = db_session.query(Inventory).filter_by(sku_id=p1.id).one()
    assert inv_p1.quantity_on_hand == 150
    assert inv_p1.quantity_committed == 25

    inv_p2 = db_session.query(Inventory).filter_by(sku_id=p2.id).one()
    assert inv_p2.quantity_on_hand == 80
    assert inv_p2.quantity_committed == 10


def test_obvious_non_order_pre_filter(db_session):
    from app.models.customer import Customer
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Vikas Sales Corp")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Whitelisted Customer
    customer = Customer(
        retailer_name="Debtor Shop",
        customer_id="C-DEBTOR-1",
        address_text="Mumbai",
        gstin="27BBBBB2222B2Z2",
        tax_group="GST",
        payment_terms="Net 30",
        credit_limit=100000.0,
        outstanding_balance=0.0,
        phone_number="+919876543210"
    )
    db_session.add(customer)
    db_session.commit()

    service = IngestionService()
    
    # 3. Call ingest_message with obvious non-order phrases
    # Short messages (< 5 chars) like "ok" and "👍" are caught by Layer 3 (message_too_short).
    # Messages >= 5 chars like "thanks", "hello", "baad mein" are caught by our pre-filter (non_order_intent).
    test_cases = [
        ("ok", "message_too_short"),
        ("👍", "message_too_short"),
        ("thanks", "non_order_intent"),
        ("hello", "non_order_intent"),
        ("baad mein", "non_order_intent")
    ]
    for msg, expected_reason in test_cases:
        res = service.ingest_message(
            db=db_session,
            tenant_id=tenant.id,
            sender_phone="+919876543210",
            message_text=msg
        )
        assert res["status"] == "ignored"
        assert res["reason"] == expected_reason


