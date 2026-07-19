"""
Tests for the customer allocation-priority scoring service and its read-only
dashboard endpoint.
"""
import uuid
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from app.main import app
from app.database import tenant_context
from app.models.tenant import DistributorTenant
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order, OrderLineItem
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentInvoiceLink
from app.models.demand_gap import DemandGap
from app.services.customer_scoring_service import rank_customers_for_allocation

client = TestClient(app)


def _make_customer(db_session, tenant_id, name, cust_code, payment_terms="Net 30"):
    customer = Customer(
        tenant_id=tenant_id, retailer_name=name, customer_id=cust_code,
        address_text="Delhi", gstin="07AAAAA1111A1Z1", tax_group="GST",
        payment_terms=payment_terms, credit_limit=1000000.0,
    )
    db_session.add(customer)
    db_session.flush()
    return customer


def _make_demand_gap(db_session, tenant_id, customer_id, product_id, gap_qty=10, revenue_at_risk=1000.0):
    db_session.add(DemandGap(
        id=uuid.uuid4(), tenant_id=tenant_id, order_id=None, customer_id=customer_id,
        product_id=product_id, reason_code="STOCK_SHORTAGE", status="OPEN",
        requested_qty=gap_qty + 5, allocated_qty=5, gap_qty=gap_qty,
        unit_price=100.0, revenue_at_risk=revenue_at_risk, created_at=datetime.utcnow(),
    ))


def _make_paid_invoice_on_time(db_session, tenant_id, customer_id, order_id, days_ago_created=40, paid_after_days=5):
    invoice = Invoice(
        id=uuid.uuid4(), tenant_id=tenant_id, order_id=order_id, customer_id=customer_id,
        gstin="07AAAAA1111A1Z1", total_amount=1000.0, amount_paid=1000.0,
        payment_status="PAID", created_at=datetime.utcnow() - timedelta(days=days_ago_created),
    )
    db_session.add(invoice)
    db_session.flush()

    payment = Payment(
        id=uuid.uuid4(), tenant_id=tenant_id, customer_id=customer_id, amount=1000.0,
        method="UPI", status="SUCCESS",
        created_at=invoice.created_at + timedelta(days=paid_after_days),
    )
    db_session.add(payment)
    db_session.flush()
    db_session.add(PaymentInvoiceLink(
        id=uuid.uuid4(), tenant_id=tenant_id, payment_id=payment.id, invoice_id=invoice.id, amount_allocated=1000.0,
    ))
    return invoice


def test_reliable_customer_outranks_chronic_late_payer(db_session):
    """A customer with on-time payments, frequent orders, and high revenue
    should score higher than one with chronic late payments and low activity,
    when both have an open demand gap for the same product."""
    tenant = DistributorTenant(name="Scoring Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    product = Product(tenant_id=tenant.id, sku_id="PROD-SCORE-1", brand="BrandX", category="Cat", pack_size="1u", base_price=100.0)
    db_session.add(product)
    db_session.flush()

    good_customer = _make_customer(db_session, tenant.id, "Reliable Kirana", "C-GOOD", payment_terms="Net 30")
    bad_customer = _make_customer(db_session, tenant.id, "Late Payer Kirana", "C-BAD", payment_terms="Net 30")
    db_session.flush()

    # Good customer: 5 recent orders, all invoices paid on time.
    for i in range(5):
        order = Order(tenant_id=tenant.id, internal_order_id=f"ORD-GOOD-{i}", source="Portal", customer_id=good_customer.id)
        db_session.add(order)
        db_session.flush()
        db_session.add(OrderLineItem(order_id=order.id, product_id=product.id, quantity=5, unit_price=100.0))
        _make_paid_invoice_on_time(db_session, tenant.id, good_customer.id, order.id, days_ago_created=20 + i, paid_after_days=2)

    # Bad customer: 1 order, invoice still unpaid and well past its due date (chronically late).
    bad_order = Order(tenant_id=tenant.id, internal_order_id="ORD-BAD-1", source="Portal", customer_id=bad_customer.id)
    db_session.add(bad_order)
    db_session.flush()
    db_session.add(OrderLineItem(order_id=bad_order.id, product_id=product.id, quantity=5, unit_price=100.0))
    db_session.add(Invoice(
        tenant_id=tenant.id, order_id=bad_order.id, customer_id=bad_customer.id, gstin="07AAAAA1111A1Z1",
        total_amount=500.0, amount_paid=0.0, payment_status="UNPAID",
        created_at=datetime.utcnow() - timedelta(days=90),
    ))

    _make_demand_gap(db_session, tenant.id, good_customer.id, product.id)
    _make_demand_gap(db_session, tenant.id, bad_customer.id, product.id)
    db_session.commit()

    ranked = rank_customers_for_allocation(db_session, tenant.id, sku_id=product.id)

    assert len(ranked) == 2
    scores_by_name = {r["customer_name"]: r["score"] for r in ranked}
    assert scores_by_name["Reliable Kirana"] > scores_by_name["Late Payer Kirana"]
    assert ranked[0]["customer_name"] == "Reliable Kirana"  # sorted descending


def test_rank_customers_returns_empty_list_when_no_open_gaps(db_session):
    tenant = DistributorTenant(name="No Gaps Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    ranked = rank_customers_for_allocation(db_session, tenant.id)
    assert ranked == []


def test_allocation_priority_endpoint(db_session):
    tenant = DistributorTenant(name="Endpoint Scoring Tenant")
    db_session.add(tenant)
    db_session.commit()
    tenant_context.set(tenant.id)

    product = Product(tenant_id=tenant.id, sku_id="PROD-ENDPOINT-1", brand="BrandY", category="Cat", pack_size="1u", base_price=50.0)
    db_session.add(product)
    db_session.flush()

    customer = _make_customer(db_session, tenant.id, "Endpoint Kirana", "C-ENDPOINT-SCORE")
    db_session.flush()
    _make_demand_gap(db_session, tenant.id, customer.id, product.id, gap_qty=8, revenue_at_risk=400.0)
    db_session.commit()

    resp = client.get(f"/api/v1/dashboard/allocation-priority?tenant_id={tenant.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["customer_name"] == "Endpoint Kirana"
    assert data["items"][0]["open_gap_qty"] == 8
