"""Regression tests for customer-approved partial fulfillment.

These tests document the business invariants independently of the UI:
- original requested demand is never overwritten
- normal shortage allocates all available stock
- customer may accept less than available stock
- Demand Gap is measured from original requested quantity
"""
import uuid

import pytest

from app.models.demand_gap import DemandGap
from app.models.inventory import Inventory
from app.models.order import OrderLineItem
from app.services.order_confirmation_service import confirm_order


def _single_line(db, order):
    return db.query(OrderLineItem).filter(OrderLineItem.order_id == order.id).one()


def _inventory(db, order, item):
    return db.query(Inventory).filter(
        Inventory.tenant_id == order.tenant_id,
        Inventory.sku_id == item.product_id,
    ).one()


def _gap(db, order, item, reason):
    return db.query(DemandGap).filter(
        DemandGap.order_id == order.id,
        DemandGap.product_id == item.product_id,
        DemandGap.reason_code == reason,
    ).one()


def test_shortage_allocates_available_and_tracks_gap(db_session, draft_order):
    """145 requested / 142 available -> allocate 142 and track gap 3."""
    db = db_session
    order = draft_order
    item = _single_line(db, order)
    item.quantity = 145
    inv = _inventory(db, order, item)
    inv.quantity_on_hand = 142
    db.flush()

    confirm_order(db, order, updated_by="test", bypass_credit_limit=True)
    db.flush()

    assert item.quantity == 145
    assert item.allocated_quantity == 142
    assert inv.quantity_on_hand == 0
    assert order.status == "Partially Confirmed"
    gap = _gap(db, order, item, "STOCK_SHORTAGE")
    assert gap.requested_qty == 145
    assert gap.allocated_qty == 142
    assert gap.gap_qty == 3


def test_customer_can_accept_less_than_available_without_losing_original_demand(db_session, draft_order):
    """145 requested / 142 available / customer accepts 140 -> leave 2, gap 5."""
    db = db_session
    order = draft_order
    item = _single_line(db, order)
    item.quantity = 145
    inv = _inventory(db, order, item)
    inv.quantity_on_hand = 142
    db.flush()

    confirm_order(
        db,
        order,
        updated_by="test",
        bypass_credit_limit=True,
        approved_quantities={item.id: 140},
    )
    db.flush()

    assert item.quantity == 145  # original demand remains immutable
    assert item.allocated_quantity == 140
    assert inv.quantity_on_hand == 2
    assert order.status == "Partially Confirmed"
    gap = _gap(db, order, item, "CUSTOMER_REDUCTION")
    assert gap.requested_qty == 145
    assert gap.allocated_qty == 140
    assert gap.gap_qty == 5
    assert float(gap.revenue_at_risk) == pytest.approx(5 * float(item.unit_price))


def test_approved_quantity_cannot_exceed_original_request(db_session, draft_order):
    db = db_session
    order = draft_order
    item = _single_line(db, order)

    with pytest.raises(Exception) as exc:
        confirm_order(
            db,
            order,
            updated_by="test",
            bypass_credit_limit=True,
            approved_quantities={item.id: item.quantity + 1},
        )

    assert "must be between 0 and requested quantity" in str(exc.value)
