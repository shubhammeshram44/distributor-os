"""Contract-level tests for stock-shortage fulfillment choices."""

from app.api.v1.fulfillment import FulfillmentDecisionPayload


def test_confirm_available_payload_needs_no_quantity_override():
    payload = FulfillmentDecisionPayload(action="CONFIRM_AVAILABLE")
    assert payload.action == "CONFIRM_AVAILABLE"
    assert payload.line_decisions == []


def test_confirm_custom_accepts_customer_quantity():
    payload = FulfillmentDecisionPayload(
        action="CONFIRM_CUSTOM",
        line_decisions=[
            {"item_id": "00000000-0000-0000-0000-000000000001", "approved_quantity": 140}
        ],
    )
    assert payload.line_decisions[0].approved_quantity == 140


def test_cancel_full_is_explicit_action():
    payload = FulfillmentDecisionPayload(action="CANCEL_FULL")
    assert payload.action == "CANCEL_FULL"
