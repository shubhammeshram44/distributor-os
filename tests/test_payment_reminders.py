import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from sqlalchemy.orm import Session
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.whatsapp_message_log import WhatsappMessageLog
from app.utils.payment_terms import parse_credit_days
from app.services.payment_reminder_service import run_payment_reminder_sweep

# 1. Test parse_credit_days
def test_parse_credit_days(caplog):
    # Test valid cases
    assert parse_credit_days("0-15 Days") == 0
    assert parse_credit_days("16-30 Days") == 16
    assert parse_credit_days("31-60 Days") == 31
    assert parse_credit_days("60+ Days") == 60
    assert parse_credit_days("Net 30") == 30

    # Test unparseable fallback to 30
    assert parse_credit_days("Net Unknown", "CustA", "TenantA") == 30
    assert "Could not parse credit days" in caplog.text

    assert parse_credit_days(None, "CustB", "TenantB") == 30
    assert "Empty payment terms" in caplog.text


# 2. Test run_payment_reminder_sweep integration
@pytest.mark.asyncio
async def test_run_payment_reminder_sweep_scenarios(db_session: Session):
    # Set up test tenants
    tenant_active = DistributorTenant(
        id=uuid.uuid4(),
        name="Active Tenant",
        notification_prefs={"payment_reminder": True}
    )
    tenant_inactive = DistributorTenant(
        id=uuid.uuid4(),
        name="Inactive Tenant",
        notification_prefs={"payment_reminder": False}
    )
    db_session.add_all([tenant_active, tenant_inactive])
    db_session.commit()

    today = datetime.utcnow()

    # Helpers to create customer, order, and invoice
    def make_scenario(
        customer_name: str,
        payment_terms: str,
        days_overdue: int | None,  # if None, invoice is paid
        tenant_id: uuid.UUID,
        log_days_ago: int | None = None
    ):
        customer = Customer(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            retailer_name=customer_name,
            payment_terms=payment_terms,
            whatsapp_notifications_enabled=True,
            phone_number="+919999999999"
        )
        db_session.add(customer)
        db_session.flush()

        order = Order(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            internal_order_id=f"ORD-{uuid.uuid4().hex[:6].upper()}",
            source="Portal",
            customer_id=customer.id,
            status="Confirmed"
        )
        db_session.add(order)
        db_session.flush()

        # Calculate created_at to achieve days_overdue
        if days_overdue is not None:
            # Parse credit days from terms
            credit_days = parse_credit_days(payment_terms)
            created_at = today - timedelta(days=(credit_days + days_overdue))
            
            invoice = Invoice(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                order_id=order.id,
                customer_id=customer.id,
                gstin="29AAAAA1111A1Z1",
                total_amount=1000.0,
                amount_paid=0.0,
                payment_status="UNPAID",
                created_at=created_at
            )
            db_session.add(invoice)
        else:
            # Paid invoice
            invoice = Invoice(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                order_id=order.id,
                customer_id=customer.id,
                gstin="29AAAAA1111A1Z1",
                total_amount=1000.0,
                amount_paid=1000.0,
                payment_status="PAID",
                created_at=today - timedelta(days=10)
            )
            db_session.add(invoice)

        if log_days_ago is not None:
            log_entry = WhatsappMessageLog(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                customer_id=customer.id,
                order_id=None,
                event="payment_reminder",
                to_phone="919999999999",
                message_body="Test body",
                status="sent",
                created_at=today - timedelta(days=log_days_ago)
            )
            db_session.add(log_entry)

        db_session.commit()
        return customer, invoice

    # Scenario 1: Customer with no outstanding invoices (should be skipped)
    make_scenario("No Outstanding", "0-15 Days", None, tenant_active.id)

    # Scenario 2: Customer in "upcoming" tier (due in 2 days, days_overdue = -2)
    cust_upcoming, _ = make_scenario("Upcoming Customer", "Net 30", -2, tenant_active.id)

    # Scenario 3: Customer in "just_overdue" tier (days_overdue = 5)
    cust_just, _ = make_scenario("Just Overdue Customer", "Net 30", 5, tenant_active.id)

    # Scenario 4: Customer in "moderately_overdue" tier (days_overdue = 20)
    cust_mod, _ = make_scenario("Moderately Overdue Customer", "Net 30", 20, tenant_active.id)

    # Scenario 5: Customer in "severely_overdue" tier (days_overdue = 45)
    cust_severe, _ = make_scenario("Severely Overdue Customer", "Net 30", 45, tenant_active.id)

    # Scenario 6: Customer who received reminder 1 day ago (should be skipped — frequency cap)
    make_scenario("Recent Notified", "Net 30", 5, tenant_active.id, log_days_ago=1)

    # Scenario 7: Customer who received reminder 5 days ago (should NOT be skipped)
    cust_old_notified, _ = make_scenario("Old Notified", "Net 30", 5, tenant_active.id, log_days_ago=5)

    # Scenario 8: Tenant has preference disabled (entire tenant skipped)
    make_scenario("Disabled Tenant Cust", "Net 30", 5, tenant_inactive.id)

    # Scenario 9: Payment posted between query and send
    cust_resolved, inv_resolved = make_scenario("Resolved Mid Sweep", "Net 30", 5, tenant_active.id)

    # We mock parse_credit_days to intercept and mark cust_resolved's invoice as PAID before the fresh check
    original_parse = parse_credit_days
    def spy_parse_credit_days(payment_terms, customer_name="Unknown", tenant_name="Unknown"):
        if customer_name == "Resolved Mid Sweep":
            inv_resolved.payment_status = "PAID"
            inv_resolved.amount_paid = inv_resolved.total_amount
            db_session.commit()
        return original_parse(payment_terms, customer_name, tenant_name)

    # Patch NotificationService.notify_payment_reminder
    with patch("app.services.notification_service.NotificationService.notify_payment_reminder", new_callable=AsyncMock) as mock_notify, \
         patch("app.services.payment_reminder_service.parse_credit_days", side_effect=spy_parse_credit_days):
        
        mock_notify.return_value = True

        summary = await run_payment_reminder_sweep(db_session)

        # Assert summary counts
        assert summary["tenants_processed"] == 1  # only tenant_active
        # Active tenant has outstanding invoices for:
        # - Upcoming Customer
        # - Just Overdue Customer
        # - Moderately Overdue Customer
        # - Severely Overdue Customer
        # - Recent Notified
        # - Old Notified
        # - Resolved Mid Sweep
        # Total customers evaluated: 7
        assert summary["customers_evaluated"] == 7
        
        # Reminders sent:
        # - Upcoming (tier upcoming)
        # - Just Overdue (tier just_overdue)
        # - Moderately Overdue (tier moderately_overdue)
        # - Severely Overdue (tier severely_overdue)
        # - Old Notified (tier just_overdue)
        # Total sent: 5
        assert summary["reminders_sent"] == 5

        # Skipped recent (frequency cap):
        # - Recent Notified (1 day ago)
        assert summary["skipped_recent"] == 1

        # Skipped resolved (payment posted mid-sweep):
        # - Resolved Mid Sweep
        assert summary["skipped_resolved"] == 1

        assert summary["errors"] == 0

        # Assert notify_payment_reminder was called with the correct tiers
        called_args = [call.kwargs for call in mock_notify.call_args_list]
        called_tiers = [arg["tier"] for arg in called_args]
        assert set(called_tiers) == {"upcoming", "just_overdue", "moderately_overdue", "severely_overdue"}
