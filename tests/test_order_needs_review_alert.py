"""
Regression tests for the "order needs review" WhatsApp alert added to
NotificationService, and its default-enabled preference behaviour for
tenants whose notification_prefs JSON predates this event key.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.database import tenant_context
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.order import Order, OrderLineItem
from app.services.notification_service import NotificationService


def _make_order_with_one_unmatched_item(db_session, tenant, customer):
    order = Order(
        tenant_id=tenant.id,
        internal_order_id="ORD-NEEDS-REVIEW-1",
        source="WhatsApp",
        customer_id=customer.id,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderLineItem(
        order_id=order.id,
        product_id=None,
        quantity=5,
        unit_price=0.0,
        unmatched_raw_text="Some Unmatched Item",
    ))
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.mark.asyncio
async def test_order_needs_review_alert_sends_by_default_for_legacy_tenant(db_session):
    """A tenant whose notification_prefs JSON predates the
    order_needs_review_alert key should still receive the alert — a silently
    missed order is worse than an unwanted extra message."""
    tenant = DistributorTenant(name="Legacy Prefs Tenant")
    # Simulate a tenant created before this event key existed.
    tenant.notification_prefs = {"new_order_alert_to_distributor": True}
    tenant.whatsapp_phone_id = "dist-legacy00"
    tenant.whatsapp_order_phone = "+919999000011"
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    customer = Customer(
        tenant_id=tenant.id,
        retailer_name="Needs Review Kirana",
        customer_id="C-NEEDS-REVIEW",
        address_text="Some Street",
        gstin="07AAAAA1111A1Z1",
        tax_group="GST",
        payment_terms="COD",
        whatsapp_notifications_enabled=False,  # opted out — must NOT block this distributor-facing alert
    )
    db_session.add(customer)
    db_session.flush()

    order = _make_order_with_one_unmatched_item(db_session, tenant, customer)

    service = NotificationService(evolution_base_url="http://fake-evolution", api_key="fake-key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        sent = await service.notify(
            event="order_needs_review_alert",
            tenant=tenant,
            customer=customer,
            order=order,
            db=db_session,
            override_to_phone=tenant.whatsapp_order_phone,
        )

    assert sent is True
    assert mock_post.called
    sent_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
    assert "couldn't be auto-matched" in sent_payload["text"]
    assert order.internal_order_id in sent_payload["text"]


@pytest.mark.asyncio
async def test_order_needs_review_alert_respects_explicit_opt_out(db_session):
    """A tenant that explicitly disabled this event should not receive it."""
    tenant = DistributorTenant(name="Opted Out Tenant")
    tenant.notification_prefs = {"order_needs_review_alert": False}
    tenant.whatsapp_phone_id = "dist-optout00"
    tenant.whatsapp_order_phone = "+919999000022"
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    customer = Customer(
        tenant_id=tenant.id,
        retailer_name="Opted Out Kirana",
        customer_id="C-OPTED-OUT",
        address_text="Some Street",
        gstin="07AAAAA1111A1Z1",
        tax_group="GST",
        payment_terms="COD",
    )
    db_session.add(customer)
    db_session.flush()

    order = _make_order_with_one_unmatched_item(db_session, tenant, customer)

    service = NotificationService(evolution_base_url="http://fake-evolution", api_key="fake-key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        sent = await service.notify(
            event="order_needs_review_alert",
            tenant=tenant,
            customer=customer,
            order=order,
            db=db_session,
            override_to_phone=tenant.whatsapp_order_phone,
        )

    assert sent is False
    assert not mock_post.called
