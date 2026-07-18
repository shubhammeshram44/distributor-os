import uuid
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
import httpx
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.order import Order, OrderStateLedger
from app.models.customer import Customer
from app.models.shipment import Shipment
from app.database import tenant_context

logger = logging.getLogger(__name__)

class IntegrationService:
    def sync_tally_inventory(self, db: Session, tenant_id: uuid.UUID, base_url: str) -> dict:
        """
        Queries the mock Tally ODBC endpoint, parses stock XML response,
        and updates local Inventory records.
        """
        tenant_context.set(tenant_id)
        url = f"{base_url}/api/v1/mocks/tally/query"

        try:
            # Call Tally API
            response = httpx.post(url, content="SELECT SKU, ON_HAND, COMMITTED FROM INVENTORY", timeout=5.0)
            if response.status_code != 200:
                raise Exception(f"Tally mock returned status {response.status_code}")

            # Parse XML
            root = ET.fromstring(response.text)
            rows = root.findall(".//ROW")
            
            synced_count = 0
            for row in rows:
                sku = row.find("SKU").text
                on_hand = int(row.find("ON_HAND").text)
                committed = int(row.find("COMMITTED").text)

                # Find product mapping
                product_stmt = select(Product).where(Product.sku_id == sku)
                product = db.execute(product_stmt).scalar_one_or_none()
                if not product:
                    continue

                # Find/Create Inventory record
                inv_stmt = select(Inventory).where(Inventory.sku_id == product.id)
                inv = db.execute(inv_stmt).scalar_one_or_none()
                if not inv:
                    inv = Inventory(
                        tenant_id=tenant_id,
                        sku_id=product.id,
                        location="Tally Synced Bin",
                        quantity_on_hand=on_hand,
                        quantity_committed=committed,
                        low_stock_threshold=10
                    )
                    db.add(inv)
                else:
                    inv.quantity_on_hand = on_hand
                    inv.quantity_committed = committed
                
                synced_count += 1

            db.commit()
            return {"status": "success", "synced_records": synced_count}

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to sync with Tally: {e}")
            return {"status": "failed", "error": str(e)}

    def book_outbound_shipment(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        carrier: str,
        base_url: str
    ) -> Shipment:
        """
        Books outbound shipping with logistics mock APIs (Delhivery/Blue Dart),
        creates a Shipment record, and transitions the Order status to 'Dispatched'.
        """
        tenant_context.set(tenant_id)

        # 1. Fetch Order and Customer
        order = db.get(Order, order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found.")

        customer = db.get(Customer, order.customer_id)
        if not customer:
            raise ValueError(f"Customer associated with Order not found.")

        # 2. Formulate Payload
        shipment_payload = {
            "order_id": str(order.id),
            "destination_address": customer.address_text,
            "recipient_name": customer.retailer_name,
            "weight_kg": 5.2 # Hardcoded package estimate
        }

        # 3. Call specific mock logistics endpoint
        if carrier.lower() == "delhivery":
            url = f"{base_url}/api/v1/mocks/delhivery/create-shipment"
            response = httpx.post(url, json=shipment_payload, timeout=5.0)
            if response.status_code != 200:
                raise Exception("Delhivery mock booking failed.")
            data = response.json()
            tracking_id = data["waybill"]
            shipment_status = data["status"]
        elif carrier.lower() in ["blue dart", "bluedart"]:
            url = f"{base_url}/api/v1/mocks/bluedart/create-waybill"
            response = httpx.post(url, json=shipment_payload, timeout=5.0)
            if response.status_code != 200:
                raise Exception("Blue Dart mock booking failed.")
            data = response.json()
            tracking_id = data["waybill"]
            shipment_status = "Dispatched"  # mapped from WAYBILL_GENERATED
        else:
            raise ValueError(f"Unsupported logistics carrier: {carrier}")

        # 4. Create local Shipment
        shipment = Shipment(
            tenant_id=tenant_id,
            order_id=order.id,
            carrier=carrier,
            tracking_id=tracking_id,
            status=shipment_status,
            destination=customer.address_text
        )
        db.add(shipment)

        # 5. Transition order to 'Dispatched' in Append-only Ledger
        current_state = order.current_status
        ledger = OrderStateLedger(
            tenant_id=tenant_id,
            order_id=order.id,
            from_status=current_state,
            to_status="Dispatched",
            updated_by="system_logistics_agent",
            metadata_json={
                "tracking_id": tracking_id,
                "carrier": carrier,
                "booked_at": datetime.utcnow().isoformat()
            }
        )
        db.add(ledger)
        order.status = "Dispatched"
        db.commit()

        logger.info(f"Shipment booked with {carrier}. Waybill: {tracking_id}")
        return shipment
