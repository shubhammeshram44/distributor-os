import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import DistributorTenant
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product
from app.models.order import Order
from app.database import tenant_context

@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)

def test_whatsapp_webhook_triage_flow(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Triage Test Tenant")
    db_session.add(tenant)
    db_session.commit()

    tenant_context.set(tenant.id)

    # 2. Setup Customer with WhatsApp Phone Alias
    customer = Customer(
        retailer_name="Kaveri Provision Store",
        customer_id="CUST-T-101",
        address_text="Bengaluru",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days"
    )
    db_session.add(customer)
    db_session.flush()

    cust_alias = CustomerAlias(customer_id=customer.id, alias_value="+919999888877")
    db_session.add(cust_alias)
    db_session.commit()

    # 3. Post to WhatsApp webhook with an unmapped token
    response = client.post("/api/v1/whatsapp/webhook", json={
        "tenant_id": str(tenant.id),
        "phone_number": "+919999888877",
        "message_text": "10 PatanjaliDantKanti"
    })
    
    # Assert HTTP 200 OK
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["failed_rows"] == 0
    assert "manual assignment" in data["message"]

    # 4. Verify Order was created in database and tracking status normalizes to "Needs Review"
    order = db_session.query(Order).filter(Order.internal_order_id == data["order_id"]).first()
    assert order is not None
    assert order.current_status == "Needs Review"
    
    # 5. Verify the unmatched item exists and brand field contains the raw token string
    from app.models.order import OrderLineItem
    line_items = db_session.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    assert len(line_items) == 1
    
    unmatched_item = line_items[0]
    assert unmatched_item.product_id is None
    assert unmatched_item.unmatched_raw_text == "PatanjaliDantKanti"


def test_whatsapp_triage_resolution_self_learning_loop(db_session, client):
    # 1. Setup Tenant
    tenant = DistributorTenant(name="Resolution Test Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    # 2. Setup Product and Inventory for order confirmation stock checks
    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="PAT-101",
        brand="Patanjali",
        category="Personal Care",
        pack_size="100g",
        base_price=50.0
    )
    from app.models.inventory import Inventory
    db_session.add(product)
    db_session.flush()
    inv = Inventory(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id=product.id,
        quantity_on_hand=100,
        location="Bin A1",
        low_stock_threshold=10
    )
    db_session.add(inv)
    db_session.commit()

    # 3. Setup Customer and Order with unmatched item needing review
    customer = Customer(
        retailer_name="Test Store",
        customer_id="CUST-RES-101",
        address_text="Address",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days",
        credit_limit=10000.0,
        outstanding_balance=0.0
    )
    db_session.add(customer)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        internal_order_id="ORD-T-999",
        source="WhatsApp",
        customer_id=customer.id,
        created_at=datetime.utcnow()
    )
    db_session.add(order)
    db_session.flush()

    from app.models.order import OrderStateLedger
    db_session.add(OrderStateLedger(
        tenant_id=tenant.id,
        order_id=order.id,
        from_status=None,
        to_status="pending_review",
        updated_by="system_whatsapp_agent"
    ))
    
    from app.models.order import OrderLineItem
    item = OrderLineItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order.id,
        product_id=None,
        quantity=5,
        unit_price=0.0,
        unmatched_raw_text="patanjalidhantkanti"
    )
    db_session.add(item)
    db_session.commit()

    # 4. Resolve the item manually without save_as_permanent_alias flag in payload
    response = client.patch(
        f"/api/v1/orders/items/{item.id}/resolve",
        json={
            "sku_code": "PAT-101",
            "quantity": 5
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    # Refresh item and verify unmatched_raw_text is PRESERVED, and no alias created yet
    db_session.refresh(item)
    assert item.unmatched_raw_text == "patanjalidhantkanti"
    assert item.product_id == product.id

    from app.models.product import ProductAlias
    alias_before = db_session.query(ProductAlias).filter_by(tenant_id=tenant.id, product_id=product.id).first()
    assert alias_before is None

    # 5. Confirm the order to trigger bulk self-learning
    confirm_resp = client.post(f"/api/v1/orders/{order.id}/confirm")
    assert confirm_resp.status_code == 200

    # Refresh item and verify unmatched_raw_text is now CLEARED
    db_session.refresh(item)
    assert item.unmatched_raw_text is None

    # Verify the alias has been registered in the database
    alias_after = db_session.query(ProductAlias).filter_by(tenant_id=tenant.id, product_id=product.id).first()
    assert alias_after is not None
    assert alias_after.alias_name == "patanjalidhantkanti"

    # 6. Verify duplicate check silently ignores duplicates if confirming another order with the same alias
    order2 = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        internal_order_id="ORD-T-998",
        source="WhatsApp",
        customer_id=customer.id,
        created_at=datetime.utcnow()
    )
    db_session.add(order2)
    db_session.flush()

    item2 = OrderLineItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order2.id,
        product_id=product.id,
        quantity=2,
        unit_price=50.0,
        unmatched_raw_text="   PATANJALIDHANTKANTI   "  # Spaced + capitalized raw typo
    )
    db_session.add(item2)
    db_session.commit()

    confirm_resp2 = client.post(f"/api/v1/orders/{order2.id}/confirm")
    assert confirm_resp2.status_code == 200

    # Verify no additional duplicate alias was inserted
    aliases = db_session.query(ProductAlias).filter_by(tenant_id=tenant.id, product_id=product.id).all()
    assert len(aliases) == 1


def test_whatsapp_hybrid_matching_lux_patanjali(db_session, client, monkeypatch):
    # Mock Gemini parser to parse the custom test string
    from app.services.gemini_service import GeminiService, AntigravityParsedOrder, ParsedOrderItem
    monkeypatch.setattr(
        GeminiService,
        "parse_order_text",
        lambda self, text: AntigravityParsedOrder(
            items=[
                ParsedOrderItem(raw_product_name="lux soapp", quantity=10),
                ParsedOrderItem(raw_product_name="patanjalli", quantity=5),
            ],
            extracted_invoice_preference="UNSPECIFIED",
        ),
    )

    # 1. Setup Tenant
    tenant = DistributorTenant(name="Hybrid Match Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    # 2. Setup Customer & Alias
    customer = Customer(
        retailer_name="Lux Patanjali Retailer",
        customer_id="CUST-LP-101",
        address_text="Bengaluru",
        gstin="29AAAAA1111A1Z1",
        tax_group="GST-18",
        payment_terms="0-15 Days"
    )
    db_session.add(customer)
    db_session.flush()

    cust_alias = CustomerAlias(customer_id=customer.id, alias_value="+919999888877")
    db_session.add(cust_alias)

    # 3. Setup Products, Aliases and Inventory
    from app.models.product import ProductAlias
    p1 = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="LUX-101",
        brand="Lux",
        category="Soap",
        pack_size="100g",
        base_price=30.0
    )
    p2 = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="PAT-101",
        brand="Patanjali",
        category="Personal Care",
        pack_size="100g",
        base_price=50.0
    )
    db_session.add_all([p1, p2])
    db_session.flush()

    alias_p1 = ProductAlias(id=uuid.uuid4(), tenant_id=tenant.id, product_id=p1.id, alias_name="Lux Soap")
    alias_p2 = ProductAlias(id=uuid.uuid4(), tenant_id=tenant.id, product_id=p2.id, alias_name="Patanjali")
    db_session.add_all([alias_p1, alias_p2])

    from app.models.inventory import Inventory
    inv1 = Inventory(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id=p1.id,
        quantity_on_hand=100,
        location="Bin A1",
        low_stock_threshold=10
    )
    inv2 = Inventory(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id=p2.id,
        quantity_on_hand=100,
        location="Bin B1",
        low_stock_threshold=10
    )
    db_session.add_all([inv1, inv2])
    db_session.commit()

    # 4. Post to WhatsApp webhook with the custom message
    response = client.post("/api/v1/whatsapp/webhook", json={
        "tenant_id": str(tenant.id),
        "phone_number": "+919999888877",
        "message_text": "10 unit lux soapp and 5 patanjalli"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["failed_rows"] == 0

    # 5. Verify Order was created in database and both line items are matched
    order = db_session.query(Order).filter(Order.internal_order_id == data["order_id"]).first()
    assert order is not None
    assert order.current_status == "Draft"  # All matched successfully!

    from app.models.order import OrderLineItem
    line_items = db_session.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).all()
    assert len(line_items) == 2

    # Map line items by matched product_id
    item_map = {item.product_id: item for item in line_items}
    assert p1.id in item_map
    assert p2.id in item_map

    assert item_map[p1.id].quantity == 10
    assert item_map[p2.id].quantity == 5

