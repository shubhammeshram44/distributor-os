import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.product import Product, ProductAlias
from app.models.customer import Customer
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.models.inventory import Inventory
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_confirm_order_success(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Orders Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Products with stock_quantity and Inventory
    p1 = Product(sku_id="PROD-SOAP-1", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    p2 = Product(sku_id="PROD-SOAP-2", brand="HUL", category="Soap", pack_size="200g", base_price=80.0, stock_quantity=50)
    db_session.add_all([p1, p2])
    db_session.flush()

    inv1 = Inventory(tenant_id=tenant.id, sku_id=p1.id, location="Loc1", quantity_on_hand=100, low_stock_threshold=10)
    inv2 = Inventory(tenant_id=tenant.id, sku_id=p2.id, location="Loc2", quantity_on_hand=50, low_stock_threshold=10)
    db_session.add_all([inv1, inv2])
    db_session.flush()

    # 3. Setup Customer
    cust = Customer(
        retailer_name="Aggarwal Kirana", customer_id="C-1", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # 4. Setup Order (currently in Pending/Draft status)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-CONFIRM-TEST-1",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add lines
    db_session.add(OrderLineItem(order_id=order.id, product_id=p1.id, quantity=30, unit_price=45.0))
    db_session.add(OrderLineItem(order_id=order.id, product_id=p2.id, quantity=10, unit_price=80.0))

    # Ledger transition: None -> Draft
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # 5. Call confirmation endpoint
    response = client.put(
        f"/api/v1/orders/{order.id}/status",
        json={"to_status": "Confirmed"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["new_status"] == "Confirmed"

    # 6. Verify database state
    db_session.expire_all()

    # Verify stock decrements in Inventory (no change to physical stock, committed pool incremented)
    inv1_db = db_session.query(Inventory).filter_by(sku_id=p1.id).one()
    inv2_db = db_session.query(Inventory).filter_by(sku_id=p2.id).one()
    assert inv1_db.quantity_on_hand == 70
    assert inv1_db.quantity_committed == 30
    assert inv2_db.quantity_on_hand == 40
    assert inv2_db.quantity_committed == 10

    # Verify ledger entry
    latest_ledger = db_session.query(OrderStateLedger).filter_by(order_id=order.id).order_by(OrderStateLedger.timestamp.desc()).first()
    assert latest_ledger.to_status == "Confirmed"
    assert latest_ledger.from_status == "Draft"


def test_confirm_order_insufficient_stock(db_session, client):
    """
    With partial allocation: requesting more than available stock should now return 200.
    The order is confirmed with allocated_quantity = available stock, transitions to
    "Partially Confirmed" (not "Confirmed", since fulfillment state now reflects the
    actual allocation outcome), and a STOCK_SHORTAGE DemandGap row is persisted with
    a non-null revenue_at_risk.
    """
    # Setup Tenant
    tenant = DistributorTenant(name="Orders Test Tenant 2")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Product with 20 units in stock; order will request 30
    p = Product(sku_id="PROD-LOW-STOCK", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=20)
    db_session.add(p)
    db_session.flush()

    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=20, low_stock_threshold=10)
    db_session.add(inv)
    db_session.flush()

    cust = Customer(
        retailer_name="Aggarwal Kirana", customer_id="C-2", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-CONFIRM-TEST-2",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # requested qty (30) exceeds stock (20) — should be partially allocated
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=30, unit_price=45.0))
    db_session.commit()

    response = client.put(
        f"/api/v1/orders/{order.id}/status",
        json={"to_status": "Confirmed"}
    )

    # Partial allocation — should succeed (200), NOT reject
    assert response.status_code == 200
    assert response.json()["new_status"] == "Partially Confirmed"

    # Inventory physical stock should be unchanged, committed should be fully allocated (20)
    db_session.expire_all()
    inv_db = db_session.query(Inventory).filter_by(sku_id=p.id).one()
    assert inv_db.quantity_on_hand == 0
    assert inv_db.quantity_committed == 20

    # Line item should have allocated_quantity = 20 (available), not 30 (requested)
    item_db = db_session.query(OrderLineItem).filter_by(order_id=order.id).one()
    assert item_db.allocated_quantity == 20

    # A STOCK_SHORTAGE DemandGap row should have been persisted
    from app.models.demand_gap import DemandGap
    gap = db_session.query(DemandGap).filter_by(order_id=order.id).one()
    assert gap.reason_code == "STOCK_SHORTAGE"
    assert gap.gap_qty == 10           # 30 requested – 20 allocated
    assert gap.revenue_at_risk is not None
    assert float(gap.revenue_at_risk) == 450.0  # 10 units × ₹45
    assert gap.status == "OPEN"


def test_confirm_order_zero_stock_awaiting_stock(db_session, client):
    """Confirming an order with 0 units available anywhere should set
    'Awaiting Stock' (not 'Confirmed' and not 'Partially Confirmed')."""
    tenant = DistributorTenant(name="Awaiting Stock Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-ZERO-STOCK", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=0)
    db_session.add(p)
    db_session.flush()

    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=0, low_stock_threshold=10)
    db_session.add(inv)
    db_session.flush()

    cust = Customer(
        retailer_name="Zero Stock Kirana", customer_id="C-ZERO", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(tenant_id=tenant.id, internal_order_id="ORD-ZERO-STOCK-1", source="Portal", customer_id=cust.id)
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=45.0))
    db_session.commit()

    response = client.put(f"/api/v1/orders/{order.id}/status", json={"to_status": "Confirmed"})
    assert response.status_code == 200
    assert response.json()["new_status"] == "Awaiting Stock"


def test_pending_allocations_queue_and_approve(db_session, client):
    """Open STOCK_SHORTAGE gaps appear in the pending-allocations queue, and
    approving after restock allocates the remaining units and upgrades the
    order's fulfillment status."""
    tenant = DistributorTenant(name="Allocation Queue Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-QUEUE-1", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=20)
    db_session.add(p)
    db_session.flush()

    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=20, low_stock_threshold=10)
    db_session.add(inv)
    db_session.flush()

    cust = Customer(
        retailer_name="Queue Test Kirana", customer_id="C-QUEUE", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(tenant_id=tenant.id, internal_order_id="ORD-QUEUE-1", source="Portal", customer_id=cust.id)
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=30, unit_price=45.0))
    db_session.commit()

    confirm_resp = client.put(f"/api/v1/orders/{order.id}/status", json={"to_status": "Confirmed"})
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["new_status"] == "Partially Confirmed"

    # Queue should list the gap
    queue_resp = client.get(f"/api/v1/orders/pending-allocations?tenant_id={tenant.id}")
    assert queue_resp.status_code == 200
    items = queue_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["gap_qty"] == 10
    assert items[0]["can_fulfil_now"] is False

    # Restock: 15 more units arrive
    db_session.expire_all()
    inv_db = db_session.query(Inventory).filter_by(sku_id=p.id).one()
    inv_db.quantity_on_hand += 15
    db_session.commit()

    demand_gap_id = items[0]["demand_gap_id"]
    approve_resp = client.post(
        f"/api/v1/orders/pending-allocations/{demand_gap_id}/approve?tenant_id={tenant.id}"
    )
    assert approve_resp.status_code == 200
    approve_data = approve_resp.json()
    assert approve_data["status"] == "allocated"
    assert approve_data["newly_allocated_qty"] == 10  # only the remaining gap, not all 15 new units
    assert approve_data["remaining_gap_qty"] == 0
    assert approve_data["order_status"] == "Confirmed"

    # Queue should now be empty
    queue_resp_2 = client.get(f"/api/v1/orders/pending-allocations?tenant_id={tenant.id}")
    assert queue_resp_2.json()["items"] == []

    db_session.expire_all()
    item_db = db_session.query(OrderLineItem).filter_by(order_id=order.id).one()
    assert item_db.allocated_quantity == 30
    order_db = db_session.query(Order).filter_by(id=order.id).one()
    assert order_db.current_status == "Confirmed"


def test_dispatch_releases_committed_inventory(db_session, client):
    """Dispatching a confirmed order should release its allocated units from
    quantity_committed (they've physically left the warehouse) without
    touching quantity_on_hand again."""
    tenant = DistributorTenant(name="Dispatch Release Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-DISPATCH-1", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=50)
    db_session.add(p)
    db_session.flush()

    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=50, low_stock_threshold=10)
    db_session.add(inv)
    db_session.flush()

    cust = Customer(
        retailer_name="Dispatch Test Kirana", customer_id="C-DISPATCH", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(tenant_id=tenant.id, internal_order_id="ORD-DISPATCH-1", source="Portal", customer_id=cust.id)
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=20, unit_price=45.0))
    db_session.commit()

    confirm_resp = client.put(f"/api/v1/orders/{order.id}/status", json={"to_status": "Confirmed"})
    assert confirm_resp.status_code == 200

    db_session.expire_all()
    inv_after_confirm = db_session.query(Inventory).filter_by(sku_id=p.id).one()
    assert inv_after_confirm.quantity_on_hand == 30
    assert inv_after_confirm.quantity_committed == 20

    dispatch_resp = client.post(
        f"/api/v1/orders/{order.id}/dispatch",
        json={"delivery_partner": "Test Courier", "vehicle_number": "KA-01-AB-1234"}
    )
    assert dispatch_resp.status_code == 200

    db_session.expire_all()
    inv_after_dispatch = db_session.query(Inventory).filter_by(sku_id=p.id).one()
    # on_hand unchanged by dispatch — already deducted at confirm time
    assert inv_after_dispatch.quantity_on_hand == 30
    # committed released back to 0 — units have physically shipped
    assert inv_after_dispatch.quantity_committed == 0


def test_cancel_partially_confirmed_order_restores_correctly(db_session, client):
    """Cancelling a Partially Confirmed order should restore only the units
    that were actually allocated (not the full requested quantity), and fully
    release quantity_committed."""
    tenant = DistributorTenant(name="Cancel Partial Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-CANCEL-PARTIAL-1", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=20)
    db_session.add(p)
    db_session.flush()

    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=20, low_stock_threshold=10)
    db_session.add(inv)
    db_session.flush()

    cust = Customer(
        retailer_name="Cancel Partial Kirana", customer_id="C-CANCEL-PARTIAL", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD", credit_limit=100000.0
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(tenant_id=tenant.id, internal_order_id="ORD-CANCEL-PARTIAL-1", source="Portal", customer_id=cust.id)
    db_session.add(order)
    db_session.flush()

    # requested 30, only 20 in stock -> allocated_quantity will be 20
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=30, unit_price=45.0))
    db_session.commit()

    confirm_resp = client.put(f"/api/v1/orders/{order.id}/status", json={"to_status": "Confirmed"})
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["new_status"] == "Partially Confirmed"

    cancel_resp = client.post(f"/api/v1/orders/{order.id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["new_status"] == "Cancelled"

    db_session.expire_all()
    inv_db = db_session.query(Inventory).filter_by(sku_id=p.id).one()
    # Only the 20 allocated units should be restored to on-hand (not 30 requested)
    assert inv_db.quantity_on_hand == 20
    assert inv_db.quantity_committed == 0



def test_confirm_order_atomic_rollback(db_session, client):
    """
    With partial allocation: both items should confirm successfully.
    p1 (enough stock) is fully allocated; p2 (5 available, 10 requested) is partially
    allocated to 5. A STOCK_SHORTAGE DemandGap row is created for p2's gap of 5 units.
    """
    tenant = DistributorTenant(name="Orders Test Tenant 3")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    p1 = Product(sku_id="PROD-OK", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    p2 = Product(sku_id="PROD-NOT-OK", brand="HUL", category="Soap", pack_size="200g", base_price=80.0, stock_quantity=5)
    db_session.add_all([p1, p2])
    db_session.flush()

    inv1 = Inventory(tenant_id=tenant.id, sku_id=p1.id, location="Loc1", quantity_on_hand=100, low_stock_threshold=10)
    inv2 = Inventory(tenant_id=tenant.id, sku_id=p2.id, location="Loc2", quantity_on_hand=5, low_stock_threshold=10)
    db_session.add_all([inv1, inv2])
    db_session.flush()

    cust = Customer(
        retailer_name="Aggarwal Kirana", customer_id="C-3", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-CONFIRM-TEST-3",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # p1: 30 requested, 100 available — fully allocated
    # p2: 10 requested, 5 available — partially allocated (5 gap)
    db_session.add(OrderLineItem(order_id=order.id, product_id=p1.id, quantity=30, unit_price=45.0))
    db_session.add(OrderLineItem(order_id=order.id, product_id=p2.id, quantity=10, unit_price=80.0))
    db_session.commit()

    response = client.put(
        f"/api/v1/orders/{order.id}/status",
        json={"to_status": "Confirmed"}
    )

    # Partial allocation — order succeeds
    assert response.status_code == 200

    # p1 fully allocated: physical stock 100, committed 30
    # p2 partially allocated: physical stock 5, committed 5
    db_session.expire_all()
    inv1_db = db_session.query(Inventory).filter_by(sku_id=p1.id).one()
    inv2_db = db_session.query(Inventory).filter_by(sku_id=p2.id).one()
    assert inv1_db.quantity_on_hand == 70
    assert inv1_db.quantity_committed == 30
    assert inv2_db.quantity_on_hand == 0
    assert inv2_db.quantity_committed == 5

    # DemandGap row for p2's shortage
    from app.models.demand_gap import DemandGap
    gap = db_session.query(DemandGap).filter_by(order_id=order.id, reason_code="STOCK_SHORTAGE").one()
    assert gap.product_id == p2.id
    assert gap.gap_qty == 5
    assert float(gap.revenue_at_risk) == 400.0  # 5 × ₹80


def test_resolve_order_item(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Resolve Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Products
    p_valid = Product(sku_id="PROD-VALID", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    p_unmatched = Product(sku_id="UNMATCHED_SKU", brand="Generic", category="Grocery", pack_size="1 unit", base_price=0.0)
    db_session.add_all([p_valid, p_unmatched])
    db_session.flush()

    # 3. Setup Customer
    cust = Customer(
        retailer_name="Aggarwal Kirana", customer_id="C-4", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # 4. Setup Order (Needs Review status)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-RESOLVE-TEST-1",
        source="WhatsApp",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add unmatched line item
    line_item = OrderLineItem(order_id=order.id, product_id=p_unmatched.id, quantity=10, unit_price=0.0)
    db_session.add(line_item)
    db_session.flush()

    # Ledger transition: None -> Needs Review
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Needs Review", updated_by="system_whatsapp_agent"))
    db_session.commit()

    # 5. Call resolve endpoint
    payload = {
        "sku_code": "PROD-VALID",
        "quantity": 5
    }

    response = client.patch(
        f"/api/v1/orders/items/{line_item.id}/resolve",
        json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["sku_code"] == "PROD-VALID"
    assert data["quantity"] == 5
    assert data["unit_price"] == 45.0
    assert data["order_status"] == "Pending"

    # 6. Verify database state
    db_session.expire_all()
    item_db = db_session.get(OrderLineItem, line_item.id)
    assert item_db.product_id == p_valid.id
    assert item_db.quantity == 5
    assert float(item_db.unit_price) == 45.0

    order_db = db_session.get(Order, order.id)
    assert order_db.current_status == "Draft"  # Maps to Pending


def test_get_order_invoice_success(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Invoice Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-INVOICE", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Invoice Stores", customer_id="C-INV-1", address_text="Invoice Street, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order (Confirmed status)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-INVOICE-TEST-1",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add line item
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=45.0))

    # Ledger transition: None -> Confirmed
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Confirmed", updated_by="admin"))
    db_session.commit()

    # Get PDF invoice
    response = client.get(f"/api/v1/orders/{order.id}/invoice")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=invoice_" in response.headers["content-disposition"]
    assert len(response.content) > 0


def test_get_order_invoice_not_confirmed(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Invoice Test Tenant 2")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-INVOICE-2", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Invoice Stores 2", customer_id="C-INV-2", address_text="Invoice Street 2, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order (Draft status, not Confirmed)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-INVOICE-TEST-2",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add line item
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=45.0))

    # Ledger transition: None -> Draft
    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # Attempt to get PDF invoice
    response = client.get(f"/api/v1/orders/{order.id}/invoice")
    assert response.status_code == 400
    assert "Invoices can only be generated for Confirmed orders" in response.json()["detail"]


def test_list_orders(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="List Orders Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-LIST", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="List Customer", customer_id="C-LIST-1", address_text="List Street, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-LIST-TEST-1",
        source="WhatsApp",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    # Add line item
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=5, unit_price=45.0))
    db_session.commit()

    # List orders via API
    response = client.get(f"/api/v1/orders?tenant_id={tenant.id}")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) >= 1
    assert items[0]["order_id"] == "ORD-LIST-TEST-1"
    assert items[0]["customer"] == "List Customer"
    assert items[0]["amount"] == 225.0
    assert items[0]["status"] == "Pending"  # Draft maps to Pending


def test_credit_limit_guardrail_success_and_failure(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Credit Limit Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="PROD-CREDIT", brand="HUL", category="Soap", pack_size="100g", base_price=500.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="Loc", quantity_on_hand=100, low_stock_threshold=10)
    db_session.add(inv)
    db_session.flush()

    # Setup Customer with structural credit_limit of 5,000.0
    cust = Customer(
        retailer_name="Credit Test Shop", customer_id="C-CREDIT-1", address_text="Credit Street, Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=5000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order 1: Total amount = 5 * 500 = 2,500.0
    order1 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-CREDIT-TEST-1",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order1)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order1.id, product_id=p.id, quantity=5, unit_price=500.0))
    db_session.add(OrderStateLedger(order_id=order1.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # Confirm Order 1 (2,500 <= 5,000) -> Should pass
    response = client.put(f"/api/v1/orders/{order1.id}/status", json={"to_status": "Confirmed"})
    assert response.status_code == 200
    db_session.expire_all()
    cust_db = db_session.get(Customer, cust.id)
    assert float(cust_db.outstanding_balance) == 2500.0

    # Setup Order 2: Total amount = 6 * 500 = 3,000.0
    # Combined with Order 1 (2,500) = 5,500.0 which exceeds 5,000.0 credit limit!
    order2 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-CREDIT-TEST-2",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order2)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order2.id, product_id=p.id, quantity=6, unit_price=500.0))
    db_session.add(OrderStateLedger(order_id=order2.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # Confirm Order 2 -> Should fail with 400 Bad Request
    response = client.put(f"/api/v1/orders/{order2.id}/status", json={"to_status": "Confirmed"})
    assert response.status_code == 400
    assert "Credit limit exceeded" in response.json()["detail"]

    # Verify outstanding balance was NOT incremented for Order 2
    db_session.expire_all()
    cust_db2 = db_session.get(Customer, cust.id)
    assert float(cust_db2.outstanding_balance) == 2500.0


def test_list_orders_with_invoice_payment_status(db_session, client):
    from app.models.invoice import Invoice
    
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Payment Status List Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Product
    p = Product(sku_id="PROD-LIST-PAY", brand="HUL", category="Soap", pack_size="100g", base_price=45.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # 3. Setup Customer
    cust = Customer(
        retailer_name="Payment List Customer", customer_id="C-PAY-LIST-1", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # 4. Setup Order 1 (without invoice)
    order1 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-PAY-LIST-1",
        source="WhatsApp",
        customer_id=cust.id
    )
    db_session.add(order1)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order1.id, product_id=p.id, quantity=5, unit_price=45.0))

    # 5. Setup Order 2 (with invoice having status PAID)
    order2 = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-PAY-LIST-2",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order2)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order2.id, product_id=p.id, quantity=10, unit_price=45.0))

    # Add Invoice for Order 2
    inv2 = Invoice(
        tenant_id=tenant.id,
        order_id=order2.id,
        gstin=cust.gstin,
        total_amount=450.0,
        payment_status="PAID",
        amount_paid=450.0
    )
    db_session.add(inv2)
    db_session.commit()

    # 6. Call List orders API
    response = client.get(f"/api/v1/orders?tenant_id={tenant.id}")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2

    # Map results by order_id
    results_map = {item["order_id"]: item for item in items}

    # Verify Order 1 (no invoice, should default to UNPAID and 0.0 amount_paid)
    assert "ORD-PAY-LIST-1" in results_map
    assert results_map["ORD-PAY-LIST-1"]["payment_status"] == "UNPAID"
    assert results_map["ORD-PAY-LIST-1"]["amount_paid"] == 0.0

    # Verify Order 2 (has invoice with PAID status)
    assert "ORD-PAY-LIST-2" in results_map
    assert results_map["ORD-PAY-LIST-2"]["payment_status"] == "PAID"
    assert results_map["ORD-PAY-LIST-2"]["amount_paid"] == 450.0


def test_get_order_by_id_with_allocations(db_session, client):
    from app.models.invoice import Invoice
    from app.models.payment import Payment, PaymentInvoiceLink
    
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Order Details Detail Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Product
    p = Product(sku_id="PROD-DET-PAY", brand="HUL", category="Soap", pack_size="100g", base_price=50.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    # 3. Setup Customer
    cust = Customer(
        retailer_name="Payment Detail Customer", customer_id="C-PAY-DET-1", address_text="Mumbai",
        gstin="27AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # 4. Setup Order (with invoice having status PAID and one allocated payment)
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-PAY-DET-1",
        source="WhatsApp",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=50.0))

    # Add Invoice
    inv = Invoice(
        tenant_id=tenant.id,
        order_id=order.id,
        gstin=cust.gstin,
        total_amount=500.0,
        payment_status="PAID",
        amount_paid=500.0
    )
    db_session.add(inv)
    db_session.flush()

    # Add Payment
    pay = Payment(
        tenant_id=tenant.id,
        customer_id=cust.id,
        amount=500.0,
        method="UPI",
        reference_number="TXN1234567890",
        status="COMPLETED"
    )
    db_session.add(pay)
    db_session.flush()

    # Add Payment-Invoice Link
    link = PaymentInvoiceLink(
        tenant_id=tenant.id,
        payment_id=pay.id,
        invoice_id=inv.id,
        amount_allocated=500.0
    )
    db_session.add(link)
    db_session.commit()

    # 5. Call single order lookup API
    response = client.get(f"/api/v1/orders/{order.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(order.id)
    assert data["order_id"] == "ORD-PAY-DET-1"
    assert data["payment_status"] == "PAID"
    assert data["amount_paid"] == 500.0
    assert len(data["payments_allocated"]) == 1
    assert data["payments_allocated"][0]["payment_code"] == f"PAY-REC-{str(pay.id)[:8].upper()}"
    assert data["payments_allocated"][0]["amount_allocated"] == 500.0
    assert data["payments_allocated"][0]["total_voucher_amount"] == 500.0
    assert data["payments_allocated"][0]["method"] == "UPI"
    assert data["payments_allocated"][0]["reference_number"] == "TXN1234567890"

    # 6. Test 404
    fake_id = uuid.uuid4()
    response_404 = client.get(f"/api/v1/orders/{fake_id}")
    assert response_404.status_code == 404


def test_create_order_from_payload(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Create Order Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Product
    prod = Product(
        sku_id="PROD-TEST-CREATE",
        brand="HUL",
        category="Soap",
        pack_size="1 unit",
        base_price=50.0,
        stock_quantity=100
    )
    db_session.add(prod)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Create Order Stores",
        customer_id="C-CREATE-1",
        address_text="Test Address",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days"
    )
    db_session.add(cust)
    db_session.flush()
    db_session.commit()

    # Post creation payload
    payload = {
        "tenant_id": str(tenant.id),
        "customer_id": str(cust.id),
        "source": "WhatsApp",
        "status": "Draft",
        "items": [
            {
                "sku_id": "PROD-TEST-CREATE",
                "quantity": 5,
                "unit_price": 50.0
            }
        ]
    }

    response = client.post("/api/v1/orders", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "order_id" in data
    assert "internal_order_id" in data
    assert data["new_status"] == "Draft"

    # Query DB to check if order and items are created
    created_order_id = uuid.UUID(data["order_id"])
    order = db_session.get(Order, created_order_id)
    assert order is not None
    assert order.tenant_id == tenant.id
    assert order.customer_id == cust.id
    assert order.source == "WhatsApp"
    assert order.current_status == "Draft"

    line_items = db_session.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    assert len(line_items) == 1
    assert line_items[0].product_id == prod.id
    assert line_items[0].quantity == 5
    assert line_items[0].unit_price == 50.0


def test_patch_order_invoice_type(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Patch Order Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Customer
    cust = Customer(
        retailer_name="Patch Order Stores",
        customer_id="C-PATCH-1",
        address_text="Test Address",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-PATCH-1",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="UNSPECIFIED"
    )
    db_session.add(order)
    db_session.commit()

    # 1. Success Patch
    response = client.patch(f"/api/v1/orders/{order.id}", json={"invoice_type": "GST_TAX_INVOICE"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["invoice_type"] == "GST_TAX_INVOICE"

    # Verify db updated
    db_session.refresh(order)
    assert order.invoice_type == "GST_TAX_INVOICE"

    # 2. Validation Failure
    response_fail = client.patch(f"/api/v1/orders/{order.id}", json={"invoice_type": "INVALID_TYPE"})
    assert response_fail.status_code == 422


def test_batch_confirm_order_success(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Batch Confirm Tenant")
    db_session.add(tenant)
    db_session.flush()
    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(
        sku_id="PROD-BATCH-1",
        brand="Brand X",
        category="Category Y",
        pack_size="1 Liter",
        base_price=150.0,
        stock_quantity=100
    )
    db_session.add(p)
    db_session.flush()

    # Inventory row with enough stock to fully allocate the line item below,
    # so this happy-path test exercises a true "Confirmed" (fully allocated)
    # outcome rather than "Awaiting Stock" (0 allocated, no Inventory row).
    inv = Inventory(
        tenant_id=tenant.id,
        sku_id=p.id,
        location="WH1",
        quantity_on_hand=100,
        low_stock_threshold=10
    )
    db_session.add(inv)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Batch Confirm Retailer",
        customer_id="C-BATCH-1",
        address_text="Test Address",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-BATCH-CONFIRM-1",
        source="WhatsApp",
        customer_id=cust.id,
        invoice_type="UNSPECIFIED"
    )
    db_session.add(order)
    db_session.flush()

    # Setup Unmatched Line Item
    item = OrderLineItem(
        order_id=order.id,
        product_id=None,
        quantity=5,
        unit_price=0.0,
        unmatched_raw_text="Brand X 1L"
    )
    db_session.add(item)
    db_session.commit()

    # Call atomic batch-confirm
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
    data = response.json()
    assert data["status"] == "success"
    assert data["new_status"] == "Confirmed"
    assert data["changes_applied"] == 1

    # Verify db updates
    db_session.refresh(order)
    db_session.refresh(item)
    assert order.current_status == "Confirmed"
    assert order.invoice_type == "RETAIL_INVOICE"
    assert item.product_id == p.id
    assert float(item.unit_price) == 150.0
    assert item.unmatched_raw_text is None  # self-learning cleared it


def test_record_delivery_event(db_session, client):
    # Setup Tenant
    tenant = DistributorTenant(name="Delivery Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Setup Customer
    cust = Customer(
        retailer_name="Delivery Retailer", customer_id="C-DEL", address_text="Address",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Setup Order
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-DELIVERY-TEST-1",
        source="Portal",
        customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
    db_session.commit()

    # Call delivery event endpoint
    response = client.post(
        f"/api/v1/orders/{order.id}/delivery-event",
        json={
            "status": "delivered",
            "source": "manual",
            "tenant_id": str(tenant.id)
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Delivered"
    assert data["delivery_source"] == "manual"
    assert data["delivered_at"] is not None

    db_session.expire_all()
    db_session.refresh(order)
    assert order.current_status == "Delivered"
    assert order.delivery_source == "manual"
    assert order.delivered_at is not None


def test_orders_list_query_count_regression(db_session, client):
    from sqlalchemy import event
    
    # Setup Tenant
    tenant = DistributorTenant(name="Query Count Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # Helper to create an order
    def create_mock_order(idx):
        cust = Customer(
            retailer_name=f"Retailer {idx}", customer_id=f"C-Q-{idx}", address_text="Address",
            gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
        )
        db_session.add(cust)
        db_session.flush()

        order = Order(
            tenant_id=tenant.id,
            internal_order_id=f"ORD-QC-{idx}",
            source="Portal",
            customer_id=cust.id,
            status="Draft"
        )
        db_session.add(order)
        db_session.flush()
        
        db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="admin"))
        db_session.commit()
        return order

    # Create 1 order
    create_mock_order(1)

    queries_count_1 = 0
    @event.listens_for(db_session.bind, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal queries_count_1
        queries_count_1 += 1

    # Call list endpoint
    resp = client.get(f"/api/v1/orders?tenant_id={tenant.id}")
    assert resp.status_code == 200
    
    # Remove listener
    event.remove(db_session.bind, "after_cursor_execute", receive_after_cursor_execute)

    # Create 4 more orders (total 5)
    for i in range(2, 6):
        create_mock_order(i)

    queries_count_5 = 0
    @event.listens_for(db_session.bind, "after_cursor_execute")
    def receive_after_cursor_execute_5(conn, cursor, statement, parameters, context, executemany):
        nonlocal queries_count_5
        queries_count_5 += 1

    # Call list endpoint again
    resp = client.get(f"/api/v1/orders?tenant_id={tenant.id}")
    assert resp.status_code == 200

    event.remove(db_session.bind, "after_cursor_execute", receive_after_cursor_execute_5)

    # Assert query count remains bounded (constant query complexity, not O(N))
    assert queries_count_5 <= queries_count_1 + 1


def test_order_risk_assessment(db_session, client):
    # Setup mock data for tenant, customer, order
    from app.models.tenant import DistributorTenant
    from app.models.customer import Customer
    from app.models.order import Order, OrderLineItem, OrderStateLedger
    from app.models.product import Product
    import uuid

    tenant = DistributorTenant(id=uuid.uuid4(), name="Risk Test Tenant")
    db_session.add(tenant)
    db_session.flush()

    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        retailer_name="Risk Test Retailer",
        outstanding_balance=8000.0,
        credit_limit=10000.0,
        phone_number="+919999999999",
        whatsapp_notifications_enabled=True
    )
    db_session.add(customer)
    
    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="PROD-RISK-1",
        brand="Risk Brand",
        category="Risk Cat",
        pack_size="Pack of 1",
        base_price=100.0,
        stock_quantity=50
    )
    db_session.add(product)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        customer_id=customer.id,
        internal_order_id="ORD-RISK-1",
        source="Risk Source",
        status="Draft"
    )
    db_session.add(order)
    db_session.flush()

    line_item = OrderLineItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order.id,
        product_id=product.id,
        quantity=5,
        unit_price=100.0
    )
    db_session.add(line_item)
    
    ledger = OrderStateLedger(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order.id,
        from_status=None,
        to_status="Draft",
        updated_by="test"
    )
    db_session.add(ledger)
    db_session.commit()

    # Call risk assessment endpoint
    resp = client.get(f"/api/v1/orders/{order.id}/risk-assessment?tenant_id={tenant.id}")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["order_id"] == str(order.id)
    assert data["customer_id"] == str(customer.id)
    assert data["score"] >= 0
    assert data["level"] in ("clear", "caution", "high_risk")
    assert "signals" in data
    assert "recommendation" in data
    assert data["outstanding_balance"] == 8000.0
    assert data["credit_limit"] == 10000.0
    assert data["credit_utilisation_pct"] == 80.0


# ──────────────────────────────────────────────────────────────────────────────
# DemandGap — revenue_at_risk is always non-null (both reason codes)
# ──────────────────────────────────────────────────────────────────────────────

def test_demand_gap_revenue_at_risk_stock_shortage(db_session, client):
    """
    After a partial-allocation confirmation, the STOCK_SHORTAGE DemandGap row must carry
    a non-null revenue_at_risk equal to gap_qty × unit_price.
    """
    from app.models.demand_gap import DemandGap

    tenant = DistributorTenant(name="DG Revenue Test Tenant 1")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-DG-REV-1", brand="HUL", category="Soap", pack_size="200g", base_price=100.0, stock_quantity=10)
    db_session.add(p)
    db_session.flush()

    # Only 10 in stock; order will request 25 → gap = 15
    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="WH1", quantity_on_hand=10, low_stock_threshold=5)
    db_session.add(inv)
    db_session.flush()

    cust = Customer(
        retailer_name="Gap Revenue Shop", customer_id="C-DG-REV-1", address_text="Mumbai",
        gstin="27AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id, internal_order_id="ORD-DG-REV-1",
        source="Portal", customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=25, unit_price=100.0))
    db_session.commit()

    resp = client.put(f"/api/v1/orders/{order.id}/status", json={"to_status": "Confirmed"})
    assert resp.status_code == 200

    db_session.expire_all()
    gap = db_session.query(DemandGap).filter_by(order_id=order.id).one()

    # revenue_at_risk must be non-null and correctly computed
    assert gap.revenue_at_risk is not None
    assert float(gap.revenue_at_risk) == 1500.0  # 15 units × ₹100
    assert gap.reason_code == "STOCK_SHORTAGE"
    assert gap.status == "OPEN"


def test_demand_gap_credit_limit_persists_after_rejection(db_session, client):
    """
    When a credit-limit rejection occurs, a CREDIT_LIMIT DemandGap row must be persisted
    (via the separate-session commit) even though the main transaction is rolled back.
    revenue_at_risk must equal the full current_order_total.
    """
    from app.models.demand_gap import DemandGap

    tenant = DistributorTenant(name="DG Credit Limit Persist Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    p = Product(sku_id="PROD-DG-CL-1", brand="P&G", category="Detergent", pack_size="1kg", base_price=200.0, stock_quantity=100)
    db_session.add(p)
    db_session.flush()

    inv = Inventory(tenant_id=tenant.id, sku_id=p.id, location="WH1", quantity_on_hand=100, low_stock_threshold=5)
    db_session.add(inv)
    db_session.flush()

    # Customer with a tight credit_limit of 1,000 so a 10-unit ₹200 order (₹2,000) triggers it
    cust = Customer(
        retailer_name="Tight Credit Shop", customer_id="C-DG-CL-1", address_text="Pune",
        gstin="27AAAAA1111A1Z1", tax_group="GST", payment_terms="COD",
        credit_limit=1000.0, outstanding_balance=0.0
    )
    db_session.add(cust)
    db_session.flush()

    order = Order(
        tenant_id=tenant.id, internal_order_id="ORD-DG-CL-1",
        source="Portal", customer_id=cust.id
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderStateLedger(order_id=order.id, from_status=None, to_status="Draft", updated_by="test"))
    db_session.add(OrderLineItem(order_id=order.id, product_id=p.id, quantity=10, unit_price=200.0))
    db_session.commit()

    # This should be rejected with 400 (combined = ₹2,000 > ₹1,000 limit)
    resp = client.put(f"/api/v1/orders/{order.id}/status", json={"to_status": "Confirmed"})
    assert resp.status_code == 400
    assert "Credit limit exceeded" in resp.json()["detail"]

    # DemandGap row must still exist despite the rollback
    db_session.expire_all()
    gap = db_session.query(DemandGap).filter_by(order_id=order.id, reason_code="CREDIT_LIMIT").first()
    assert gap is not None, "CREDIT_LIMIT DemandGap row was not persisted after rejection"
    assert gap.revenue_at_risk is not None
    assert float(gap.revenue_at_risk) == 2000.0  # full current_order_total
    assert gap.status == "OPEN"
    assert gap.product_id is None  # CREDIT_LIMIT rows have no product reference


def test_demand_gap_rollup_endpoint_defaults_to_7_days(db_session, client):
    """
    Calling /api/v1/dashboard/demand-gap-summary without a days param must use
    window_days=7 in the response (not 30 or any other default).
    The endpoint must also return zero values cleanly when there are no gaps.
    """
    tenant = DistributorTenant(name="DG Rollup Default Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    # Call without days param
    resp = client.get(f"/api/v1/dashboard/demand-gap-summary?tenant_id={tenant.id}")
    assert resp.status_code == 200
    data = resp.json()

    # Default window must be 7 days
    assert data["window_days"] == 7

    # Zero-gap case must not error — just return clean zeros / empty array
    assert data["total_revenue_at_risk"] == 0.0
    assert data["distinct_customers_affected"] == 0
    assert data["by_reason"] == []
