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

    # 2. Setup Product
    product = Product(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku_id="PAT-101",
        brand="Patanjali",
        category="Personal Care",
        pack_size="100g",
        base_price=50.0
    )
    db_session.add(product)
    db_session.commit()

    # 3. Setup Order with unmatched item needing review
    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        internal_order_id="ORD-T-999",
        source="WhatsApp",
        customer_id=uuid.uuid4(),  # Mock UUID
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

    # 4. Resolve the item manually with save_as_permanent_alias = True
    response = client.patch(
        f"/api/v1/orders/items/{item.id}/resolve",
        json={
            "sku_code": "PAT-101",
            "quantity": 10,
            "save_as_permanent_alias": True
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["order_status"] == "Pending"  # Draft maps to Pending on frontend

    # 5. Verify the alias has been registered in the database
    from app.models.product import ProductAlias
    alias = db_session.query(ProductAlias).filter_by(tenant_id=tenant.id, product_id=product.id).first()
    assert alias is not None
    assert alias.alias_name == "patanjalidhantkanti"

    # 6. Verify duplicate check silently ignores duplicates if called again with a new item with the same alias name
    item2 = OrderLineItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order.id,
        product_id=None,
        quantity=2,
        unit_price=0.0,
        unmatched_raw_text="   PATANJALIDHANTKANTI   "  # Spaced + capitalized raw typo
    )
    db_session.add(item2)
    db_session.commit()

    response2 = client.patch(
        f"/api/v1/orders/items/{item2.id}/resolve",
        json={
            "sku_code": "PAT-101",
            "quantity": 2,
            "save_as_permanent_alias": True
        }
    )
    assert response2.status_code == 200
    assert response2.json()["status"] == "success"

    # Verify no additional duplicate alias was inserted
    aliases = db_session.query(ProductAlias).filter_by(tenant_id=tenant.id, product_id=product.id).all()
    assert len(aliases) == 1

