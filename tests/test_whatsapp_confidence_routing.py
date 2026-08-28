"""
Regression tests for WA-3: previously no AI confidence score existed
anywhere in the WhatsApp order-parsing pipeline, so the spec's "route to
triage if confidence < 0.75, never auto-confirm" rule had no signal to act
on. These tests verify:
1. AntigravityParsedOrder now carries a confidence field.
2. The regex fallback assigns a conservative, sub-threshold confidence
   (since it has no genuine model confidence to report).
3. ingestion_service.ingest_message routes a low-confidence Gemini parse
   to "pending_review" instead of auto-confirming to "Draft".
"""
import uuid
from unittest.mock import patch, MagicMock
import pytest

from app.models.tenant import DistributorTenant
from app.models.customer import Customer, CustomerAlias
from app.models.product import Product, ProductAlias
from app.models.order import Order
from app.database import tenant_context
from app.services.gemini_service import GeminiService, AntigravityParsedOrder, ParsedOrderItem
from app.services.ingestion_service import IngestionService


def test_antigravity_parsed_order_has_confidence_field():
    """AntigravityParsedOrder must carry a confidence score (0.0-1.0)."""
    order = AntigravityParsedOrder(
        items=[ParsedOrderItem(raw_product_name="Soap", quantity=5)],
        extracted_invoice_preference="UNSPECIFIED",
        confidence=0.42,
    )
    assert order.confidence == 0.42


def test_regex_fallback_assigns_conservative_sub_threshold_confidence():
    """
    The regex fallback has no genuine model confidence to report -- it must
    assign a fixed score BELOW the spec's 0.75 auto-confirm threshold
    whenever it matched anything, so regex-parsed orders never look as
    trustworthy as a genuinely confident Gemini parse.
    """
    service = GeminiService(api_key=None)  # disabled -> always uses fallback
    result = service.parse_order_text("10 units of Surf Excel")
    assert result.items, "sanity check: the fallback should have matched something"
    assert result.confidence < 0.75

    empty_result = service.parse_order_text("hello there")
    assert not empty_result.items
    assert empty_result.confidence == 0.0


def test_ingest_message_routes_low_confidence_gemini_parse_to_triage(db_session):
    """
    Regression test for WA-3: a low-confidence Gemini parse (fully matched
    SKUs, so has_unmatched=False) must still route to pending_review, not
    silently auto-confirm to Draft, per the spec's "never auto-confirm
    below 0.75" rule.
    """
    tenant = DistributorTenant(name="WA3 Low Confidence Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    customer = Customer(
        tenant_id=tenant.id, retailer_name="WA3 Retailer", customer_id="C-WA3-1",
        address_text="Bengaluru", gstin="29AAAAA1111A1Z1", tax_group="GST-18", payment_terms="0-15 Days"
    )
    db_session.add(customer)
    db_session.flush()
    db_session.add(CustomerAlias(tenant_id=tenant.id, customer_id=customer.id, alias_value="+919999111122"))

    product = Product(tenant_id=tenant.id, sku_id="PROD-WA3-SOAP", brand="HUL", category="Soap", pack_size="100g", base_price=45.0)
    db_session.add(product)
    db_session.flush()
    db_session.add(ProductAlias(tenant_id=tenant.id, product_id=product.id, alias_name="HUL Soap"))
    db_session.commit()

    fake_parsed = AntigravityParsedOrder(
        items=[ParsedOrderItem(raw_product_name="HUL Soap", quantity=5)],
        extracted_invoice_preference="UNSPECIFIED",
        confidence=0.4,  # below the 0.75 threshold
    )

    with patch("app.services.ingestion_service.GeminiService") as MockGeminiService:
        mock_instance = MagicMock()
        mock_instance.enabled = True
        mock_instance.parse_order_text.return_value = fake_parsed
        MockGeminiService.return_value = mock_instance

        service = IngestionService()
        result = service.ingest_message(
            db=db_session, tenant_id=tenant.id, sender_phone="+919999111122",
            message_text="Need 5 HUL Soap maybe"
        )

    assert result["status"] == "success"
    order = db_session.query(Order).filter(Order.internal_order_id == result["order_id"]).first()
    assert order is not None
    assert order.current_status == "Needs Review", (
        "A low-confidence (< 0.75) Gemini parse must route to triage "
        "for human review, not auto-confirm to Draft"
    )


def test_ingest_message_high_confidence_gemini_parse_still_auto_confirms(db_session):
    """
    Functional guard: a HIGH-confidence, fully-matched Gemini parse must
    still auto-confirm to Draft as before -- the new confidence gate must
    not become overly broad and block legitimate, confident parses.
    """
    tenant = DistributorTenant(name="WA3 High Confidence Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    customer = Customer(
        tenant_id=tenant.id, retailer_name="WA3 Retailer High", customer_id="C-WA3-2",
        address_text="Bengaluru", gstin="29AAAAA1111A1Z1", tax_group="GST-18", payment_terms="0-15 Days"
    )
    db_session.add(customer)
    db_session.flush()
    db_session.add(CustomerAlias(tenant_id=tenant.id, customer_id=customer.id, alias_value="+919999111133"))

    product = Product(tenant_id=tenant.id, sku_id="PROD-WA3-SOAP-2", brand="HUL", category="Soap", pack_size="100g", base_price=45.0)
    db_session.add(product)
    db_session.flush()
    db_session.add(ProductAlias(tenant_id=tenant.id, product_id=product.id, alias_name="HUL Soap Two"))
    db_session.commit()

    fake_parsed = AntigravityParsedOrder(
        items=[ParsedOrderItem(raw_product_name="HUL Soap Two", quantity=5)],
        extracted_invoice_preference="UNSPECIFIED",
        confidence=0.95,
    )

    with patch("app.services.ingestion_service.GeminiService") as MockGeminiService:
        mock_instance = MagicMock()
        mock_instance.enabled = True
        mock_instance.parse_order_text.return_value = fake_parsed
        MockGeminiService.return_value = mock_instance

        service = IngestionService()
        result = service.ingest_message(
            db=db_session, tenant_id=tenant.id, sender_phone="+919999111133",
            message_text="Need 5 HUL Soap Two"
        )

    assert result["status"] == "success"
    order = db_session.query(Order).filter(Order.internal_order_id == result["order_id"]).first()
    assert order.current_status == "Draft"
