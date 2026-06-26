import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.models.order import Order
from app.models.inventory import Inventory
from app.models.ledger import CustomerLedger
from app.models.shipment import Shipment
from app.models.tenant import DistributorTenant
from app.models.customer import Customer

client = TestClient(app)

# =====================================================================
# 1. WHATSAPP NLP INGESTION & TRIAGE PIPELINE
# =====================================================================

def test_whatsapp_unmapped_token_creates_needs_review_order(db_session, setup_test_catalog):
    """
    CRITICAL FEAT: Triage Pipeline
    When an unknown token comes through WhatsApp, the system must NOT return 
    an ERR-VAL-404. It must return a 200 OK and create a parent Order 
    with a 'NEEDS_REVIEW' status layout.
    """
    payload = {
        "sender": "+919999888877",
        "message": "Bhaiya, send 5 packs of PatanjaliDantKanti"
    }
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    
    assert response.status_code == 200, "Webhook failed on unmapped token!"
    assert response.json().get("status") == "success"
    
    order = db_session.query(Order).filter(Order.customer_mobile == "+919999888877").first()
    assert order is not None, "Order was not created in the database!"
    assert order.current_status == "Needs Review"


def test_whatsapp_webhook_unwhitelisted_sender(db_session, setup_test_catalog):
    """
    Verifies that webhook requests from unwhitelisted senders log clean 
    and return 200 OK early without creating an order.
    """
    payload = {
        "sender": "+919999000000",
        "message": "Bhaiya, send 5 packs of PatanjaliDantKanti"
    }
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    
    assert response.status_code == 200
    assert response.json().get("status") == "ignored"
    assert "not whitelisted" in response.json().get("message")
    
    # Ensure no order is created for unwhitelisted sender
    order = db_session.query(Order).filter(Order.customer_mobile == "+919999000000").first()
    assert order is None


def test_whatsapp_webhook_decoupled_routing(db_session, setup_test_catalog):
    """
    Verifies smart routing to the correct tenant based on payload.receiver.
    """
    tenant = db_session.query(DistributorTenant).first()
    tenant.whatsapp_order_phone = "+918888888888"
    db_session.commit()
    
    payload = {
        "sender": "+919999888877",
        "receiver": "+918888888888",
        "message": "Bhaiya, send 5 packs of PatanjaliDantKanti"
    }
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    assert response.json().get("status") == "success"


# =====================================================================
# 2. THE ORDER JOURNEY (ADDITION, CONFIRMATION, SHIPMENT)
# =====================================================================

def test_order_addition_and_creation(db_session, setup_test_catalog):
    """
    Verifies that structured manual/API order entry correctly adds an order 
    to the system with its initial pending parameters.
    """
    order_payload = {
        "customer_id": 1,
        "items": [
            {"sku_id": "SKU-AASHIRVAAD-AATA", "quantity": 10, "price": 450.00}
        ]
    }
    response = client.post("/api/v1/orders/create", json=order_payload)
    assert response.status_code == 201
    
    order_id = response.json().get("order_id")
    order = db_session.query(Order).get(order_id)
    assert order is not None
    assert order.total_amount == 4500.00


def test_order_confirmation_workflow(db_session, setup_pending_order):
    """
    Verifies transitioning an order from 'Pending' to 'Confirmed', ensuring
    the transition registers cleanly in the order state ledger.
    """
    order_id = setup_pending_order.id
    response = client.post(f"/api/v1/orders/{order_id}/confirm")
    assert response.status_code == 200
    
    db_session.refresh(setup_pending_order)
    assert setup_pending_order.current_status == "Confirmed"


def test_order_shipment_generation_and_tracking(db_session, setup_confirmed_order):
    """
    Verifies that confirming/processing an order for delivery generates a 
    corresponding Shipment record tracking its logistics state.
    """
    order_id = setup_confirmed_order.id
    shipment_payload = {
        "delivery_partner": "Local Logistics",
        "vehicle_number": "KA-03-EX-1234"
    }
    response = client.post(f"/api/v1/orders/{order_id}/dispatch", json=shipment_payload)
    assert response.status_code == 200
    
    shipment = db_session.query(Shipment).filter(Shipment.order_id == order_id).first()
    assert shipment is not None
    assert shipment.status == "DISPATCHED"


# =====================================================================
# 3. INVENTORY MANAGEMENT (ADDITION & DASHBOARD GRID)
# =====================================================================

def test_inventory_stock_inward_addition(db_session, setup_test_catalog):
    """
    Verifies that dynamic stock inward actions properly increment physical stock
    counts and associate correctly with the item's sku_id.
    """
    inward_payload = {
        "sku_id": "SKU-AASHIRVAAD-AATA",
        "quantity_added": 50,
        "warehouse_location": "Bay-A1"
    }
    response = client.post("/api/v1/inventory/inward", json=inward_payload)
    assert response.status_code == 200
    
    inv = db_session.query(Inventory).filter(Inventory.sku_id == "SKU-AASHIRVAAD-AATA").first()
    assert inv.physical_stock >= 50


def test_inventory_grid_includes_zero_stock_items(db_session, setup_empty_catalog_item):
    """
    CRITICAL FEAT: Outer Join Bugfix
    Catalog items with 0 physical stock must still show up on the frontend
    inventory panel instead of being dropped by strict INNER JOINs.
    """
    response = client.get("/api/v1/inventory/dashboard-grid")
    assert response.status_code == 200
    
    items = response.json().get("data", [])
    zero_stock_item_exists = any(item["sku_code"] == "ZERO_STOCK_SKU" for item in items)
    assert zero_stock_item_exists, "Regression! Items with 0 stock are being hidden from the catalog panel."


# =====================================================================
# 4. PAYMENT PROCESS & FIFO RECONCILIATION
# =====================================================================

def test_payment_voucher_logging(db_session, setup_test_catalog):
    """
    Verifies receiving a direct payment logs a voucher entry under the 
    customer's account ledger.
    """
    customer = db_session.query(Customer).first()
    payload = {
        "customer_id": str(customer.id),
        "amount": 2000.00,
        "payment_mode": "Cash"
    }
    response = client.post("/api/v1/payments/voucher", json=payload)
    assert response.status_code == 201

    ledger_entry = db_session.query(CustomerLedger).filter(
        CustomerLedger.customer_id == customer.id
    ).order_by(CustomerLedger.id.desc()).first()
    assert ledger_entry is not None
    assert ledger_entry.credit == 2000.00


def test_fifo_payment_cascade(db_session, setup_unpaid_orders):
    """
    CRITICAL FEAT: FIFO Cascade
    When a customer pays an amount, it must systematically close out older
    outstanding invoices/orders in a First-In, First-Out sequence, avoiding 
    permanently un-synced 'Unpaid' statuses.
    """
    customer_id = setup_unpaid_orders["customer_id"]
    order_1_id = setup_unpaid_orders["order_1_id"] # Due: 500
    order_2_id = setup_unpaid_orders["order_2_id"] # Due: 1000
    
    payment_payload = {
        "customer_id": customer_id,
        "amount": 700.00,
        "payment_mode": "UPI"
    }
    response = client.post("/api/v1/payments/collect", json=payment_payload)
    assert response.status_code == 200
    
    order_1 = db_session.query(Order).get(order_1_id)
    assert order_1.payment_status == "PAID"
    
    order_2 = db_session.query(Order).get(order_2_id)
    assert order_2.payment_status == "PARTIALLY_PAID"
