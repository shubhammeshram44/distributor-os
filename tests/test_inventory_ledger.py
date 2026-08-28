"""
Regression tests for INV-3: no inventory audit/movement trail existed at
all previously -- Inventory.quantity_on_hand/quantity_committed were
mutated directly at every stock-affecting call site with no history
surviving past whatever an in-memory log line happened to record. "Why
does this SKU have this many units on hand" was unanswerable after the
fact.

These tests exercise the real API endpoints/service functions (not just
the InventoryLedger model in isolation) to prove actual wiring: every
stock-affecting call site must now write a corresponding, correctly
signed InventoryLedger row.
"""
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.models.tenant import DistributorTenant
from app.models.product import Product
from app.models.customer import Customer
from app.models.order import Order, OrderLineItem
from app.models.inventory import Inventory
from app.models.inventory_ledger import InventoryLedger
from app.database import tenant_context

client = TestClient(app)


def test_order_confirmation_logs_deduction_to_inventory_ledger(db_session):
    tenant = DistributorTenant(name="INV3 Confirm Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-INV3-CONFIRM", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=50)
    db_session.add(p)
    db_session.flush()
    db_session.add(Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=50, low_stock_threshold=10))

    cust = Customer(
        retailer_name="INV3 Confirm Kirana", customer_id="C-INV3-CONFIRM", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD", credit_limit=100000.0
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(tenant_id=tenant.id, internal_order_id="ORD-INV3-CONFIRM-1", source="Portal", customer_id=cust.id)
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=45.0))
    db_session.commit()

    response = client.put(f"/api/v1/orders/{order.id}/status", json={"to_status": "Confirmed"})
    assert response.status_code == 200

    db_session.expire_all()
    entries = db_session.query(InventoryLedger).filter(
        InventoryLedger.tenant_id == tenant.id, InventoryLedger.sku_id == p.id
    ).all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.movement_type == "ORDER_CONFIRMED"
    assert entry.quantity_delta == -10
    assert entry.quantity_on_hand_after == 40
    assert entry.reference_id == "ORD-INV3-CONFIRM-1"


def test_order_cancellation_logs_restock_to_inventory_ledger(db_session):
    tenant = DistributorTenant(name="INV3 Cancel Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-INV3-CANCEL", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=50)
    db_session.add(p)
    db_session.flush()
    db_session.add(Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=50, low_stock_threshold=10))

    cust = Customer(
        retailer_name="INV3 Cancel Kirana", customer_id="C-INV3-CANCEL", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD", credit_limit=100000.0
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(tenant_id=tenant.id, internal_order_id="ORD-INV3-CANCEL-1", source="Portal", customer_id=cust.id)
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=45.0))
    db_session.commit()

    confirm_resp = client.put(f"/api/v1/orders/{order.id}/status", json={"to_status": "Confirmed"})
    assert confirm_resp.status_code == 200

    cancel_resp = client.post(f"/api/v1/orders/{order.id}/cancel")
    assert cancel_resp.status_code == 200

    db_session.expire_all()
    entries = db_session.query(InventoryLedger).filter(
        InventoryLedger.tenant_id == tenant.id, InventoryLedger.sku_id == p.id
    ).order_by(InventoryLedger.created_at.asc()).all()
    assert len(entries) == 2
    confirm_entry, cancel_entry = entries
    assert confirm_entry.movement_type == "ORDER_CONFIRMED"
    assert confirm_entry.quantity_delta == -10
    assert cancel_entry.movement_type == "ORDER_CANCELLED"
    assert cancel_entry.quantity_delta == 10
    assert cancel_entry.quantity_on_hand_after == 50


def test_manual_restock_logs_to_inventory_ledger(db_session):
    tenant = DistributorTenant(name="INV3 Restock Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-INV3-RESTOCK", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=20)
    db_session.add(p)
    db_session.flush()
    db_session.add(Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=20, low_stock_threshold=10))
    db_session.commit()

    response = client.post(
        f"/api/v1/products/adjust-stock?tenant_id={tenant.id}",
        json={"sku_id": "PROD-INV3-RESTOCK", "quantity_received": 15}
    )
    assert response.status_code == 200

    db_session.expire_all()
    entries = db_session.query(InventoryLedger).filter(
        InventoryLedger.tenant_id == tenant.id, InventoryLedger.sku_id == p.id
    ).all()
    assert len(entries) == 1
    assert entries[0].movement_type == "MANUAL_RESTOCK"
    assert entries[0].quantity_delta == 15
    assert entries[0].quantity_on_hand_after == 35


def test_product_creation_logs_initial_stock_to_inventory_ledger(db_session):
    tenant = DistributorTenant(name="INV3 Create Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    response = client.post(
        f"/api/v1/products?tenant_id={tenant.id}",
        json={
            "sku_id": "PROD-INV3-CREATE", "brand": "HUL", "category": "Soap",
            "pack_size": "100g", "base_price": 45.0
        }
    )
    assert response.status_code == 201
    product_id = uuid.UUID(response.json()["product_id"])

    entries = db_session.query(InventoryLedger).filter(
        InventoryLedger.tenant_id == tenant.id, InventoryLedger.sku_id == product_id
    ).all()
    assert len(entries) == 1
    assert entries[0].movement_type == "INITIAL_STOCK"
    assert entries[0].quantity_delta == 100
