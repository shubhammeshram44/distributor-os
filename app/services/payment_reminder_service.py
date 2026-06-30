import os
import logging
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.whatsapp_message_log import WhatsappMessageLog
from app.services.notification_service import NotificationService
from app.utils.payment_terms import parse_credit_days

logger = logging.getLogger("uvicorn.error")

FREQUENCY_CAP_DAYS = 3

async def run_payment_reminder_sweep(db: Session) -> dict:
    summary = {
        "tenants_processed": 0,
        "customers_evaluated": 0,
        "reminders_sent": 0,
        "skipped_recent": 0,
        "skipped_resolved": 0,
        "errors": 0
    }

    try:
        # Get notification service configuration
        evolution_base_url = os.getenv("EVOLUTION_API_URL", "http://34.158.60.42:8080")
        api_key = os.getenv("EVOLUTION_API_KEY", "distributorbotkey2026")
        notification_service = NotificationService(evolution_base_url, api_key)

        # 1. Query all tenants
        tenants = db.query(DistributorTenant).all()

        for tenant in tenants:
            # Check tenant notification preference
            prefs = tenant.notification_prefs or {}
            if not prefs.get("payment_reminder", True):
                continue

            summary["tenants_processed"] += 1

            # 2. Query customers of this tenant who have at least one UNPAID or PARTIALLY_PAID invoice
            customers = (
                db.query(Customer)
                .join(Invoice, Invoice.customer_id == Customer.id)
                .filter(
                    Customer.tenant_id == tenant.id,
                    Invoice.payment_status.in_(["UNPAID", "PARTIALLY_PAID"])
                )
                .distinct()
                .all()
            )

            for customer in customers:
                summary["customers_evaluated"] += 1

                try:
                    # 3. Fetch outstanding invoices for this customer to calculate overdue status
                    invoices = (
                        db.query(Invoice)
                        .filter(
                            Invoice.customer_id == customer.id,
                            Invoice.payment_status.in_(["UNPAID", "PARTIALLY_PAID"])
                        )
                        .all()
                    )

                    if not invoices:
                        continue

                    # Calculate total_outstanding and count
                    total_outstanding = sum(float(inv.total_amount - inv.amount_paid) for inv in invoices)
                    invoice_count = len(invoices)

                    # Determine most overdue invoice based on days_overdue
                    today = datetime.utcnow()
                    most_overdue_days = None
                    most_overdue_invoice = None

                    for inv in invoices:
                        credit_days = parse_credit_days(customer.payment_terms, customer.name, tenant.name)
                        due_date = inv.created_at + timedelta(days=credit_days)
                        days_overdue = (today - due_date).days

                        if most_overdue_days is None or days_overdue > most_overdue_days:
                            most_overdue_days = days_overdue
                            most_overdue_invoice = inv

                    if most_overdue_days is None:
                        continue

                    # Map days_overdue to a tier
                    tier = None
                    if most_overdue_days < -3:
                        # Too far in the future
                        continue
                    elif most_overdue_days < 0:
                        tier = "upcoming"
                    elif most_overdue_days <= 15:
                        tier = "just_overdue"
                    elif most_overdue_days <= 30:
                        tier = "moderately_overdue"
                    else:
                        tier = "severely_overdue"

                    # 4. FREQUENCY CAP check
                    # Check WhatsappMessageLog for a recent payment_reminder event for this customer
                    last_log = (
                        db.query(WhatsappMessageLog)
                        .filter(
                            WhatsappMessageLog.customer_id == customer.id,
                            WhatsappMessageLog.event == "payment_reminder",
                            WhatsappMessageLog.status == "sent"
                        )
                        .order_by(WhatsappMessageLog.created_at.desc())
                        .first()
                    )

                    if last_log:
                        cutoff = datetime.utcnow() - timedelta(days=FREQUENCY_CAP_DAYS)
                        if last_log.created_at >= cutoff:
                            summary["skipped_recent"] += 1
                            logger.info(
                                "Skipping reminder for customer %s: recently sent on %s",
                                customer.name, last_log.created_at
                            )
                            continue

                    # 5. RE-CHECK payment status fresh at send time
                    fresh_invoices = (
                        db.query(Invoice)
                        .filter(
                            Invoice.customer_id == customer.id,
                            Invoice.payment_status.in_(["UNPAID", "PARTIALLY_PAID"])
                        )
                        .all()
                    )
                    fresh_total = sum(float(inv.total_amount - inv.amount_paid) for inv in fresh_invoices)
                    if fresh_total <= 0:
                        summary["skipped_resolved"] += 1
                        logger.info("Skipping reminder for customer %s: outstanding balance cleared.", customer.name)
                        continue

                    # Gather specific invoice details for the "upcoming" tier
                    specific_invoice_id = None
                    specific_invoice_total = None
                    specific_invoice_due_date = None

                    if tier == "upcoming" and most_overdue_invoice:
                        # Fetch associated order for internal_order_id if possible
                        order = db.get(Order, most_overdue_invoice.order_id)
                        specific_invoice_id = f"INV-{order.internal_order_id}" if order else f"INV-{str(most_overdue_invoice.id)[:8].upper()}"
                        specific_invoice_total = float(most_overdue_invoice.total_amount - most_overdue_invoice.amount_paid)
                        credit_days = parse_credit_days(customer.payment_terms, customer.name, tenant.name)
                        due_date = most_overdue_invoice.created_at + timedelta(days=credit_days)
                        specific_invoice_due_date = due_date.strftime("%Y-%m-%d")

                    # 6. Send the payment reminder
                    success = await notification_service.notify_payment_reminder(
                        tenant=tenant,
                        customer=customer,
                        tier=tier,
                        total_outstanding=fresh_total,
                        invoice_count=len(fresh_invoices),
                        db=db,
                        specific_invoice_id=specific_invoice_id,
                        specific_invoice_total=specific_invoice_total,
                        specific_invoice_due_date=specific_invoice_due_date
                    )

                    if success:
                        summary["reminders_sent"] += 1
                        logger.info("Payment reminder sent successfully for customer %s (tier: %s)", customer.name, tier)
                    else:
                        summary["errors"] += 1
                        logger.error("Failed to send payment reminder for customer %s", customer.name)

                except Exception as cust_ex:
                    summary["errors"] += 1
                    logger.error(
                        "Error processing payment reminder for customer %s: %s",
                        customer.name, str(cust_ex), exc_info=True
                    )

    except Exception as sweep_ex:
        logger.error("Failed to execute payment reminder sweep: %s", str(sweep_ex), exc_info=True)
        summary["errors"] += 1

    logger.info("Payment reminder sweep complete: %s", str(summary))
    return summary
