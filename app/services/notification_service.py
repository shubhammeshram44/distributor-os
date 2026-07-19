import os
import uuid
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

We'll update you once your order is confirmed and share dispatch details shortly.
— {distributor_name}""",

    "order_confirmed": """Hi {customer_name},

Your order {order_id} has been confirmed ✓
Items: {item_summary}
Total: ₹{total}

— {distributor_name}""",

    "order_dispatched": """Hi {customer_name},

🚚 Your order {order_id} has been dispatched!
Items: {item_summary}
Total: ₹{total}

Your order is on its way.
— {distributor_name}""",

    "order_delivered": """Hi {customer_name},

✅ Your order {order_id} has been delivered!
Items: {item_summary}
Total: ₹{total}

Thank you for your order. We look forward to serving you again!
— {distributor_name}""",

    "new_order_alert_to_distributor": """🛒 New Order Alert!

From: {customer_name}
Order ID: {order_id}
Items: {item_summary}
Total: ₹{total}"""
}

PAYMENT_REMINDER_TEMPLATES = {
    "upcoming": """Hi {customer_name},

Friendly reminder that ₹{total:,.0f} is due on {due_date}.

Pay now: {payment_link}

Thank you for your business!
— {distributor_name}""",

    "just_overdue": """Hi {customer_name},

Your payment of ₹{total:,.0f} is overdue.

Pay most overdue invoice: {payment_link}
Pay full outstanding balance: {outstanding_link}

Please arrange payment at your earliest convenience.
— {distributor_name}""",

    "moderately_overdue": """Hi {customer_name},

₹{total:,.0f} has been overdue for {days_overdue} days.

Pay most overdue invoice: {payment_link}
Pay full outstanding balance: {outstanding_link}

Please process immediately to avoid service interruption.
— {distributor_name}""",

    "severely_overdue": """Hi {customer_name},

URGENT: ₹{total:,.0f} is severely overdue ({days_overdue} days).

Pay most overdue invoice: {payment_link}
Pay full outstanding balance: {outstanding_link}

Please clear immediately.
— {distributor_name}"""
}

CONSOLIDATED_PAYMENT_REMINDER_TEMPLATE = """Hi {customer_name},

You have {invoice_count} unpaid invoices totaling ₹{total:,.0f}.

Pay all outstanding invoices in one go: {outstanding_link}

Thank you for your business!
— {distributor_name}"""



class NotificationService:
    def __init__(self, evolution_base_url: str, api_key: str):
        self.base_url = evolution_base_url.rstrip("/")
        self.api_key = api_key

    async def _send_and_log(
        self,
        tenant: DistributorTenant,
        customer: Customer,
        order_id: uuid.UUID | None,
        event: str,
        rendered_message: str,
        override_to_phone: str | None = None
    ) -> bool:
        # 1. Verify whatsapp_phone_id exists
        instance_name = tenant.whatsapp_phone_id
        if not instance_name:
            logger.warning("Notification skipped: No whatsapp_phone_id for tenant %s", str(tenant.id))
            return False

        # 2. Resolve and verify recipient phone number
        raw_phone = override_to_phone if override_to_phone else customer.phone_number
        if not raw_phone:
            logger.warning("Notification skipped: Phone number is empty or unresolved")
            return False

        # 3. Normalize phone number
        normalized_phone = normalize_phone_number(raw_phone)
        if normalized_phone.startswith("+"):
            normalized_phone = normalized_phone[1:]

        # 4. Send text message via Evolution API
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

        # 5. Log outcome to database
        # To be 100% safe from closed parent sessions in background contexts,
        # we write to the DB using a fresh local session.
        from app.database import SessionLocal
        db_log = SessionLocal()
        try:
            log_entry = WhatsappMessageLog(
                tenant_id=tenant.id,
                customer_id=customer.id,
                order_id=order_id,
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

            # 3. Render template
            template = TEMPLATES.get(event)
            if not template:
                logger.warning("Notification skipped: No template found for event %s", event)
                return False

            # Generate item summary
            items_list = []
            for item in order.line_items:
                qty = item.allocated_quantity if item.allocated_quantity is not None else item.quantity
                if item.product:
                    items_list.append(f"{item.product.brand} x {qty}")
                elif item.unmatched_raw_text:
                    items_list.append(f"{item.unmatched_raw_text} (Unmatched) x {qty}")
                else:
                    items_list.append(f"Unknown Product x {qty}")
            item_summary = ", ".join(items_list)

            rendered_message = template.format(
                customer_name=customer.name,
                order_id=order.internal_order_id,
                item_summary=item_summary,
                total=order.total_amount,
                distributor_name=tenant.name
            )

            # 4. Delegate sending and logging to private helper
            return await self._send_and_log(
                tenant=tenant,
                customer=customer,
                order_id=order.id,
                event=event,
                rendered_message=rendered_message,
                override_to_phone=override_to_phone
            )

        except Exception as e:
            logger.warning("Notification fire failed silently: %s", str(e))
            return False

    async def notify_payment_reminder(
        self,
        tenant: DistributorTenant,
        customer: Customer,
        tier: str,
        total_outstanding: float,
        invoice_count: int,
        db: Session,
        specific_invoice_id: str | None = None,
        specific_invoice_total: float | None = None,
        specific_invoice_due_date: str | None = None,
        payment_link: str | None = None,
        outstanding_link: str | None = None,
        days_overdue: int = 0
    ) -> bool:
        """
        Renders and sends a tiered payment reminder via Evolution API.
        Never raises.
        """
        try:
            # 1. Check tenant notification preferences
            prefs = tenant.notification_prefs or {}
            pref_key = "payment_reminder_upcoming" if tier == "upcoming" else "payment_reminder_overdue"
            if not prefs.get(pref_key, True) and not prefs.get("payment_reminder", True):
                logger.info("Notification skipped: %s disabled for tenant %s", pref_key, str(tenant.id))
                return False

            # 2. Check customer notifications enablement
            if not customer.whatsapp_notifications_enabled:
                logger.info("Notification skipped: customer %s opted out", str(customer.id))
                return False

            # 3. Render template
            template = PAYMENT_REMINDER_TEMPLATES.get(tier)
            if not template:
                logger.warning("Notification skipped: No template found for payment reminder tier %s", tier)
                return False

            link_to_show = payment_link if payment_link else "Contact your distributor to pay"
            out_link_to_show = outstanding_link if outstanding_link else "Contact your distributor to pay"

            rendered_message = template.format(
                customer_name=customer.name,
                total=specific_invoice_total if tier == "upcoming" else total_outstanding,
                due_date=specific_invoice_due_date or "N/A",
                payment_link=link_to_show,
                outstanding_link=out_link_to_show,
                days_overdue=days_overdue,
                distributor_name=tenant.name
            )

            # 4. Delegate sending and logging to private helper
            return await self._send_and_log(
                tenant=tenant,
                customer=customer,
                order_id=None,
                event="payment_reminder",
                rendered_message=rendered_message
            )

        except Exception as e:
            logger.warning("Payment reminder fire failed silently: %s", str(e))
            return False

    async def notify_consolidated_payment_reminder(
        self,
        tenant: DistributorTenant,
        customer: Customer,
        total_outstanding: float,
        invoice_count: int,
        db: Session,
        outstanding_link: str | None = None,
    ) -> bool:
        """
        Renders and sends a single consolidated reminder covering all of a customer's
        outstanding invoices (used instead of the tiered single-invoice reminder for
        customers with many open invoices). Logged as event="consolidated_payment_reminder"
        so it has its own frequency-cap dedup lane in WhatsappMessageLog.
        Never raises.
        """
        try:
            # 1. Check tenant notification preferences
            prefs = tenant.notification_prefs or {}
            if not prefs.get("payment_reminder", True):
                logger.info("Notification skipped: payment_reminder disabled for tenant %s", str(tenant.id))
                return False

            # 2. Check customer notifications enablement
            if not customer.whatsapp_notifications_enabled:
                logger.info("Notification skipped: customer %s opted out", str(customer.id))
                return False

            # 3. Render template
            link_to_show = outstanding_link if outstanding_link else "Contact your distributor to pay"
            rendered_message = CONSOLIDATED_PAYMENT_REMINDER_TEMPLATE.format(
                customer_name=customer.name,
                invoice_count=invoice_count,
                total=total_outstanding,
                outstanding_link=link_to_show,
                distributor_name=tenant.name
            )

            # 4. Delegate sending and logging to private helper
            return await self._send_and_log(
                tenant=tenant,
                customer=customer,
                order_id=None,
                event="consolidated_payment_reminder",
                rendered_message=rendered_message
            )

        except Exception as e:
            logger.warning("Consolidated payment reminder fire failed silently: %s", str(e))
            return False
