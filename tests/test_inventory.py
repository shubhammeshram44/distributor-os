import uuid
from datetime import datetime, timedelta
import pytest
from app.models.tenant import DistributorTenant
from app.models.product import Product, ProductSupplierMapping
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.order import Order, OrderLineItem, OrderStateLedger
from app.services.inventory_service import InventoryService
from app.database import tenant_context

def test_inventory_logic_and_alerts(db_session):
    # Setup Tenant
    tenant = DistributorTenant(name="Reliance Distribution")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    # Setup Product and Stock
    product = Product(sku_id="SKU-SOAP", brand="HUL", category="Soap", pack_size="125g", base_price=50.0)
    db_session.add(product)
    db_session.flush()

    inventory = Inventory(
        sku_id=product.id,
        location="Aisle-A1",
        quantity_on_hand=20,
        quantity_committed=5,
        low_stock_threshold=10
    )
    db_session.add(inventory)
    db_session.commit()

    service = InventoryService()
    
    # 1. Test Stock Level Calculations
    stock = service.calculate_current_stock(db_session, product.id)
    assert stock["quantity_on_hand"] == 20
    assert stock["quantity_committed"] == 5
    assert stock["net_available"] == 15
    assert stock["low_stock_threshold"] == 10

    # 2. Test Low Stock Alert (hand=20 > threshold=10 -> False)
    assert not service.alert_low_stock(db_session, product.id)

    # Update stock to trigger alert
    inventory.quantity_on_hand = 8
    db_session.commit()
    assert service.alert_low_stock(db_session, product.id)


def test_sales_velocity_calculation(db_session):
    # Setup Tenant
    tenant = DistributorTenant(name="Reliance Distribution")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="SKU-AATA", brand="ITC", category="Flour", pack_size="10kg", base_price=380.0)
    db_session.add(p)
    db_session.flush()

    # Setup Customer
    cust = Customer(
        retailer_name="Aggarwal Stores", customer_id="C-1", address_text="Delhi",
        gstin="07AAAAA1111A1Z1", tax_group="GST", payment_terms="COD"
    )
    db_session.add(cust)
    db_session.flush()

    # Create 3 Orders in the last 10 days
    # Order 1 (Confirmed) -> Should be included
    o1 = Order(internal_order_id="ORD-1", source="Portal", customer_id=cust.id, created_at=datetime.utcnow() - timedelta(days=2))
    db_session.add(o1)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=o1.id, product_id=p.id, quantity=50, unit_price=380.0))
    # Ledger transitions for Order 1: None -> Draft -> Confirmed
    db_session.add(OrderStateLedger(order_id=o1.id, from_status=None, to_status="Draft", updated_by="admin", timestamp=datetime.utcnow() - timedelta(days=3)))
    db_session.add(OrderStateLedger(order_id=o1.id, from_status="Draft", to_status="Confirmed", updated_by="admin", timestamp=datetime.utcnow() - timedelta(days=2)))

    # Order 2 (Dispatched) -> Should be included
    o2 = Order(internal_order_id="ORD-2", source="Portal", customer_id=cust.id, created_at=datetime.utcnow() - timedelta(days=5))
    db_session.add(o2)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=o2.id, product_id=p.id, quantity=10, unit_price=380.0))
    db_session.add(OrderStateLedger(order_id=o2.id, from_status=None, to_status="Draft", updated_by="admin", timestamp=datetime.utcnow() - timedelta(days=6)))
    db_session.add(OrderStateLedger(order_id=o2.id, from_status="Draft", to_status="Dispatched", updated_by="admin", timestamp=datetime.utcnow() - timedelta(days=5)))

    # Order 3 (Draft status) -> Should be EXCLUDED because its latest status is Draft
    o3 = Order(internal_order_id="ORD-3", source="WhatsApp", customer_id=cust.id, created_at=datetime.utcnow() - timedelta(days=1))
    db_session.add(o3)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=o3.id, product_id=p.id, quantity=100, unit_price=380.0))
    db_session.add(OrderStateLedger(order_id=o3.id, from_status=None, to_status="Draft", updated_by="admin", timestamp=datetime.utcnow() - timedelta(days=1)))

    db_session.commit()

    service = InventoryService()
    # Velocity over last 10 days = (50 + 10) / 10 = 6.0 units per day
    velocity = service.calculate_sales_velocity(db_session, p.id, timeframe_days=10)
    assert velocity == 6.0


def test_ai_reorder_suggestions(db_session):
    # Setup Tenant
    tenant = DistributorTenant(name="Reliance Distribution")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    # Setup Product
    p = Product(sku_id="SKU-CHIPS", brand="ITC", category="Chips", pack_size="50g", base_price=10.0)
    db_session.add(p)
    db_session.flush()

    # Setup Supplier (as a record in Customer table)
    supplier = Customer(
        retailer_name="ITC Supplier Hub", customer_id="SUP-ITC", address_text="Kolkata Warehouse",
        gstin="19AAAAA2222A2Z2", tax_group="GST", payment_terms="Net 30"
    )
    db_session.add(supplier)
    db_session.flush()

    # Create Product-Supplier Mapping
    mapping = ProductSupplierMapping(product_id=p.id, supplier_id=supplier.id, is_primary=True)
    db_session.add(mapping)

    # Setup Inventory at low stock (committed=0, hand=5, threshold=10)
    inventory = Inventory(
        sku_id=p.id, location="Aisle-B1", quantity_on_hand=5, quantity_committed=0, low_stock_threshold=10
    )
    db_session.add(inventory)
    db_session.commit()

    service = InventoryService()

    # Run suggestions with 0 velocity fallback
    suggestions = service.get_ai_reorder_suggestions(db_session, supplier.id, lead_time_days=7)
    assert len(suggestions) == 1
    sug = suggestions[0]
    assert sug["sku_id"] == "SKU-CHIPS"
    assert sug["current_quantity_on_hand"] == 5
    assert sug["sales_velocity_per_day"] == 0.0
    # Suggested reorder qty for zero velocity = threshold (10) * 5 = 50 units
    assert sug["suggested_reorder_quantity"] == 50


def test_tenant_reorder_suggestions_aggregates_across_suppliers(db_session):
    """
    Regression test for InventoryService.get_tenant_reorder_suggestions:
    should surface reorder suggestions for every supplier-mapped product in
    the tenant (not just one supplier at a time), attach supplier name/phone,
    skip products that don't need reordering, and sort most-urgent first.
    """
    tenant = DistributorTenant(name="Multi-Supplier Distribution")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    # Supplier A -> low-stock product (needs reorder)
    supplier_a = Customer(
        retailer_name="ITC Supplier Hub", customer_id="SUP-ITC", address_text="Kolkata Warehouse",
        gstin="19AAAAA2222A2Z2", tax_group="GST", payment_terms="Net 30", phone_number="+919999900001"
    )
    # Supplier B -> healthy-stock product (should NOT show up)
    supplier_b = Customer(
        retailer_name="HUL Supplier Hub", customer_id="SUP-HUL", address_text="Mumbai Warehouse",
        gstin="27AAAAA3333A3Z3", tax_group="GST", payment_terms="Net 15", phone_number="+919999900002"
    )
    db_session.add_all([supplier_a, supplier_b])
    db_session.flush()

    low_stock_product = Product(sku_id="SKU-CHIPS", brand="ITC", category="Chips", pack_size="50g", base_price=10.0)
    healthy_product = Product(sku_id="SKU-SOAP", brand="HUL", category="Soap", pack_size="125g", base_price=50.0)
    db_session.add_all([low_stock_product, healthy_product])
    db_session.flush()

    db_session.add(ProductSupplierMapping(product_id=low_stock_product.id, supplier_id=supplier_a.id, is_primary=True))
    db_session.add(ProductSupplierMapping(product_id=healthy_product.id, supplier_id=supplier_b.id, is_primary=True))

    db_session.add(Inventory(
        sku_id=low_stock_product.id, location="Aisle-B1", quantity_on_hand=5, quantity_committed=0, low_stock_threshold=10
    ))
    db_session.add(Inventory(
        sku_id=healthy_product.id, location="Aisle-A1", quantity_on_hand=500, quantity_committed=0, low_stock_threshold=10
    ))
    db_session.commit()

    service = InventoryService()
    suggestions = service.get_tenant_reorder_suggestions(db_session, tenant.id, lead_time_days=7)

    # Only the low-stock product should be flagged; the healthy one is excluded.
    assert len(suggestions) == 1
    sug = suggestions[0]
    assert sug["sku_id"] == "SKU-CHIPS"
    assert sug["supplier_id"] == str(supplier_a.id)
    assert sug["supplier_name"] == "ITC Supplier Hub"
    assert sug["supplier_phone"] == "+919999900001"
    assert sug["suggested_reorder_quantity"] == 50
