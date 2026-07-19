import io
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.product import Product, ProductAlias, ProductSupplierMapping
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_import_products_success(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Import Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Add an existing product to update
    existing_prod = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="PROD-TEST-UPDATE",
        brand="BrandOld",
        category="CatOld",
        pack_size="50g",
        base_price=100.00
    )
    db_session.add(existing_prod)
    db_session.commit()

    # 3. Create mock CSV data
    # Contains:
    # - Update for existing_prod
    # - Insert for new_prod
    csv_content = (
        "sku_id,brand,category,pack_size,base_price\n"
        "PROD-TEST-UPDATE,BrandNew,CatNew,100g,120.50\n"
        "PROD-TEST-INSERT,BrandInsert,CatInsert,250g,45.00\n"
    )

    csv_file = io.BytesIO(csv_content.encode("utf-8"))

    # 4. Trigger import endpoint
    response = client.post(
        "/api/v1/products/import",
        data={"tenant_id": str(tenant.id)},
        files={"file": ("products.csv", csv_file, "text/csv")}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["successful_rows"] == 2
    assert data["inserted_count"] == 1
    assert data["updated_count"] == 1
    assert data["failed_rows"] == 0

    # 5. Assert database state
    # Verify existing product got updated
    db_session.expire_all()
    updated_prod = db_session.query(Product).filter_by(sku_id="PROD-TEST-UPDATE").one()
    assert float(updated_prod.base_price) == 120.50
    assert updated_prod.brand == "BrandNew"
    assert updated_prod.category == "CatNew"
    assert updated_prod.pack_size == "100g"

    # Verify new product got inserted
    inserted_prod = db_session.query(Product).filter_by(sku_id="PROD-TEST-INSERT").one()
    assert float(inserted_prod.base_price) == 45.00
    assert inserted_prod.brand == "BrandInsert"
    assert inserted_prod.category == "CatInsert"
    assert inserted_prod.pack_size == "250g"

    # Verify default aliases got created for the inserted product
    aliases = db_session.query(ProductAlias).filter_by(product_id=inserted_prod.id).all()
    assert len(aliases) == 2
    alias_names = {a.alias_name for a in aliases}
    assert "PROD-TEST-INSERT" in alias_names
    assert "BrandInsert CatInsert" in alias_names


def test_import_products_missing_headers(db_session, client):
    tenant = DistributorTenant(name="Import Header Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    # CSV missing base_price column
    csv_content = (
        "sku_id,brand,category,pack_size\n"
        "PROD-FAIL,BrandFail,CatFail,100g\n"
    )

    csv_file = io.BytesIO(csv_content.encode("utf-8"))

    response = client.post(
        "/api/v1/products/import",
        data={"tenant_id": str(tenant.id)},
        files={"file": ("products.csv", csv_file, "text/csv")}
    )

    assert response.status_code == 400
    assert "missing required headers" in response.json()["detail"].lower()


def test_import_products_validation_rollback(db_session, client):
    tenant = DistributorTenant(name="Import Rollback Tenant")
    db_session.add(tenant)
    db_session.commit()

    # Row 3 contains invalid float value for price, causing rollback of the whole file
    csv_content = (
        "sku_id,brand,category,pack_size,base_price\n"
        "PROD-VALID-1,Brand1,Cat1,100g,10.00\n"
        "PROD-INVALID-2,Brand2,Cat2,200g,NOT_A_FLOAT\n"
    )

    csv_file = io.BytesIO(csv_content.encode("utf-8"))

    response = client.post(
        "/api/v1/products/import",
        data={"tenant_id": str(tenant.id)},
        files={"file": ("products.csv", csv_file, "text/csv")}
    )

    assert response.status_code == 422
    data = response.json()
    assert "errors" in data["detail"]
    assert any("NOT_A_FLOAT" in err for err in data["detail"]["errors"])

    # Verify transactional integrity: PROD-VALID-1 was NOT committed since the whole import failed
    db_session.expire_all()
    product_count = db_session.query(Product).filter(Product.tenant_id == tenant.id).count()
    assert product_count == 0


def test_manual_product_creation(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Manual Creation Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Trigger POST /products manually
    payload = {
        "sku_id": "PROD-MANUAL-NEW",
        "brand": "HUL",
        "category": "Soap",
        "pack_size": "150g",
        "base_price": 55.50
    }

    response = client.post(
        f"/api/v1/products?tenant_id={tenant.id}",
        json=payload
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "product_id" in data

    # 3. Assert database state
    db_session.expire_all()
    product = db_session.query(Product).filter_by(sku_id="PROD-MANUAL-NEW").one()
    assert float(product.base_price) == 55.50
    assert product.brand == "HUL"
    assert product.category == "Soap"
    assert product.pack_size == "150g"
    assert product.stock_quantity == 100  # Default initial stock

    # Verify default aliases got created
    aliases = db_session.query(ProductAlias).filter_by(product_id=product.id).all()
    assert len(aliases) == 2
    alias_names = {a.alias_name for a in aliases}
    assert "PROD-MANUAL-NEW" in alias_names
    assert "HUL Soap" in alias_names

    # 4. Assert duplicate SKU is rejected with 400
    dup_response = client.post(
        f"/api/v1/products?tenant_id={tenant.id}",
        json=payload
    )
    assert dup_response.status_code == 400
    assert "already exists" in dup_response.json()["detail"]

    # 5. Assert validation bounds (negative price)
    bad_payload = payload.copy()
    bad_payload["sku_id"] = "PROD-MANUAL-BAD"
    bad_payload["base_price"] = -5.0
    bad_response = client.post(
        f"/api/v1/products?tenant_id={tenant.id}",
        json=bad_payload
    )
    assert bad_response.status_code == 422


def test_stock_adjustment(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Stock Adjust Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Add product
    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="PROD-ADJUST-TEST",
        brand="BrandA",
        category="CatA",
        pack_size="10g",
        base_price=20.00,
        stock_quantity=50
    )
    db_session.add(product)
    db_session.commit()

    # 3. Post adjustment
    payload = {
        "sku_id": "PROD-ADJUST-TEST",
        "quantity_received": 30
    }

    response = client.post(
        f"/api/v1/products/adjust-stock?tenant_id={tenant.id}",
        json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["sku_id"] == "PROD-ADJUST-TEST"
    assert data["new_stock"] == 80

    # Assert database state
    db_session.expire_all()
    updated_prod = db_session.query(Product).filter_by(sku_id="PROD-ADJUST-TEST").one()
    assert updated_prod.stock_quantity == 80

    # 4. Check 404 for invalid SKU
    bad_sku_payload = {
        "sku_id": "PROD-INVALID-SKU",
        "quantity_received": 10
    }
    bad_sku_resp = client.post(
        f"/api/v1/products/adjust-stock?tenant_id={tenant.id}",
        json=bad_sku_payload
    )
    assert bad_sku_resp.status_code == 404

    # 5. Check 422 for invalid quantity
    bad_qty_payload = {
        "sku_id": "PROD-ADJUST-TEST",
        "quantity_received": -5
    }
    bad_qty_resp = client.post(
        f"/api/v1/products/adjust-stock?tenant_id={tenant.id}",
        json=bad_qty_payload
    )
    assert bad_qty_resp.status_code == 422




def test_reorder_suggestions_endpoint(db_session, client):
    """
    Regression test for GET /api/v1/products/reorder-suggestions: should
    return only products that actually need reordering, with supplier info
    attached, and validate lead_time_days.
    """
    tenant = DistributorTenant(name="Reorder Endpoint Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    supplier = Customer(
        retailer_name="ITC Supplier Hub", customer_id="SUP-ITC-2", address_text="Kolkata Warehouse",
        gstin="19AAAAA2222A2Z2", tax_group="GST", payment_terms="Net 30", phone_number="+919999900003"
    )
    db_session.add(supplier)
    db_session.flush()

    low_stock_product = Product(sku_id="SKU-CHIPS-2", brand="ITC", category="Chips", pack_size="50g", base_price=10.0)
    db_session.add(low_stock_product)
    db_session.flush()

    db_session.add(ProductSupplierMapping(product_id=low_stock_product.id, supplier_id=supplier.id, is_primary=True))
    db_session.add(Inventory(
        sku_id=low_stock_product.id, location="Aisle-B1", quantity_on_hand=5, quantity_committed=0, low_stock_threshold=10
    ))
    db_session.commit()

    response = client.get(f"/api/v1/products/reorder-suggestions?tenant_id={tenant.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["suggestions"][0]["sku_id"] == "SKU-CHIPS-2"
    assert data["suggestions"][0]["supplier_name"] == "ITC Supplier Hub"
    assert data["suggestions"][0]["supplier_phone"] == "+919999900003"

    # Invalid lead_time_days should be rejected with 400
    bad_response = client.get(f"/api/v1/products/reorder-suggestions?tenant_id={tenant.id}&lead_time_days=0")
    assert bad_response.status_code == 400
