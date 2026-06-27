import os
import logging
import httpx
from sqlalchemy.orm import Session
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.order import Order
from app.models.whatsapp_message_log import WhatsappMessageLog
from app.utils.phone import normalize_phone_number

logger = logging.getLogger("uvicorn.error")

TEMPLATES = {
    "order_received": """Hi {customer_name},

✅ Order Received!
Order ID: {order_id}
Items: {item_summary}
Total: ₹{total}

We'll confirm and dispatch soon.
— {distributor_name}""",

    "order_confirmed": """Hi {customer_name},

Your order {order_id} has been confirmed ✓
Items: {item_summary}
Total: ₹{total}

— {distributor_name}""",

    "new_order_alert_to_distributor": """🛒 New Order Alert!

From: {customer_name}
Order ID: {order_id}
Items: {item_summary}
Total: ₹{total}"""
}

class NotificationService:
    def __init__(self, evolution_base_url: str, api_key: str):
        self.base_url = evolution_base_url.rstrip("/")
        self.api_key = api_key

    async def notify(
        self,
        event: str,
        tenant: DistributorTenant,
        customer: Customer,
        order: Order,
        db: Session,
        override_to_phone: str | None = None
    ) -> bool:
        """
        Returns True if message sent, False if skipped or failed.
        Never raises — all errors are logged and swallowed.
        """
        try:
            # 1. Check tenant notification preferences
            prefs = tenant.notification_prefs or {}
            if not prefs.get(event, False):
                logger.info("Notification skipped: %s disabled for tenant %s", event, str(tenant.id))
                return False

            # 2. Check customer notifications enablement (skipped for distributor alert)
            if event != "new_order_alert_to_distributor":
                if not customer.whatsapp_notifications_enabled:
                    logger.info("Notification skipped: customer %s opted out", str(customer.id))
                    return False

            # 3. Verify whatsapp_phone_id exists
            instance_name = tenant.whatsapp_phone_id
            if not instance_name:
                logger.warning("Notification skipped: No whatsapp_phone_id for tenant %s", str(tenant.id))
                return False

            # 4. Resolve and verify recipient phone number
            raw_phone = override_to_phone if override_to_phone else customer.phone_number
            if not raw_phone:
                logger.warning("Notification skipped: Phone number is empty or unresolved")
                return False

            # 5. Normalize phone number
            normalized_phone = normalize_phone_number(raw_phone)
            if normalized_phone.startswith("+"):
                normalized_phone = normalized_phone[1:]

            # 6. Render template
            template = TEMPLATES.get(event)
            if not template:
                logger.warning("Notification skipped: No template found for event %s", event)
                return False

            # Generate item summary
            items_list = []
            for item in order.line_items:
                if item.product:
                    items_list.append(f"{item.product.brand} x {item.quantity}")
                elif item.unmatched_raw_text:
                    items_list.append(f"{item.unmatched_raw_text} (Unmatched) x {item.quantity}")
                else:
                    items_list.append(f"Unknown Product x {item.quantity}")
            item_summary = ", ".join(items_list)

            rendered_message = template.format(
                customer_name=customer.name,
                order_id=order.internal_order_id,
                item_summary=item_summary,
                total=order.total_amount,
                distributor_name=tenant.name
            )

            # 7. Send text message via Evolution API
            headers = {"apikey": self.api_key}
            payload = {
                "number": normalized_phone,
                "text": rendered_message
            }
            url = f"{self.base_url}/message/sendText/{instance_name}"

            success = False
            error_msg = None
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                if response.status_code in (200, 201):
                    success = True
                else:
                    error_msg = f"Evolution API returned status code {response.status_code}: {response.text}"
                    logger.error(error_msg)
            except Exception as http_ex:
                error_msg = f"HTTP request failed: {str(http_ex)}"
                logger.error(error_msg)

            # 8. Log outcome to database
            # To be 100% safe from closed parent sessions in background contexts,
            # we write to the DB using a fresh local session.
            from app.database import SessionLocal
            db_log = SessionLocal()
            try:
                log_entry = WhatsappMessageLog(
                    tenant_id=tenant.id,
                    customer_id=customer.id,
                    order_id=order.id,
                    event=event,
                    to_phone=normalized_phone,
                    message_body=rendered_message,
                    status="sent" if success else "failed",
                    error_message=error_msg
                )
                db_log.add(log_entry)
                db_log.commit()
            except Exception as log_ex:
                db_log.rollback()
                logger.error("Failed to write WhatsappMessageLog: %s", str(log_ex))
            finally:
                db_log.close()

            return success

        except Exception as e:
            logger.warning("Notification fire failed silently: %s", str(e))
            return False
