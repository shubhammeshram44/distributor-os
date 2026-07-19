"""
Customer scoring service for stock allocation prioritization.

When physical stock is insufficient to cover every open order/demand-gap for a
SKU, this service produces a ranked list of customers to help a distributor
decide who should receive the limited stock first. It is a read-only,
advisory scoring layer — it does NOT allocate stock itself and is not wired
into any approval/allocation workflow. All numbers are computed on the fly
from existing tables (no persisted scoring columns/tables).

Composite score (0-100) — weights are intentionally simple, documented, and
tunable (see the constants below):

  payment_consistency   40%  — % of the customer's invoices that were (or, for
                               still-open invoices past their due date, would
                               have been) paid on/before their due date. This
                               is weighted highest because allocating scarce
                               stock to a customer who reliably pays on time
                               is the strongest predictor that the allocation
                               will actually convert into collected revenue.
  order_frequency       30%  — number of orders placed in the last 90 days,
                               normalized against the busiest customer in the
                               current candidate pool. Signals an active,
                               ongoing relationship.
  relationship_value    30%  — total invoiced revenue from the customer over
                               the last 90 days, normalized against the
                               highest-revenue customer in the candidate pool.
                               Signals how much the relationship is worth in
                               absolute terms.

Order frequency and relationship value are normalized *relative to the other
candidates being ranked* (min-max against the pool's own maximum) rather than
against a fixed global target, since a "good" order volume or revenue figure
varies a lot by distributor size and product mix.
"""
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.demand_gap import DemandGap
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.payment import Payment, PaymentInvoiceLink
from app.models.tenant import DistributorTenant
from app.utils.payment_terms import parse_credit_days

# Tunable weights for the composite score. Must sum to 1.0.
PAYMENT_CONSISTENCY_WEIGHT = 0.40
ORDER_FREQUENCY_WEIGHT = 0.30
RELATIONSHIP_VALUE_WEIGHT = 0.30

ORDER_FREQUENCY_WINDOW_DAYS = 90
ORDER_FREQUENCY_RECENT_WINDOW_DAYS = 30
RELATIONSHIP_VALUE_WINDOW_DAYS = 90

# Score used when a customer has no invoice history to judge payment
# consistency from — neutral (neither rewarded nor penalized).
NEUTRAL_PAYMENT_CONSISTENCY_SCORE = 50.0


def _compute_payment_consistency(db: Session, tenant: DistributorTenant | None, customer: Customer) -> float:
    """
    % of the customer's invoices paid on/before their due date.

    due_date = invoice.created_at + credit_days (parsed from customer.payment_terms).
    - PAID invoices: on-time if the most recent linked payment landed on/before due_date.
    - UNPAID/PARTIALLY_PAID invoices past their due_date already count against the
      customer (they are currently overdue, regardless of eventual outcome).
    - UNPAID/PARTIALLY_PAID invoices not yet due are excluded — too early to judge.
    """
    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer.id, Invoice.total_amount > 0)
        .all()
    )
    if not invoices:
        return NEUTRAL_PAYMENT_CONSISTENCY_SCORE

    credit_days = parse_credit_days(
        customer.payment_terms,
        customer.name,
        tenant.name if tenant else "Unknown",
    )
    now = datetime.utcnow()

    on_time = 0
    considered = 0
    for inv in invoices:
        due_date = inv.created_at + timedelta(days=credit_days)

        if inv.payment_status == "PAID":
            considered += 1
            last_payment_at = (
                db.query(func.max(Payment.created_at))
                .join(PaymentInvoiceLink, PaymentInvoiceLink.payment_id == Payment.id)
                .filter(PaymentInvoiceLink.invoice_id == inv.id)
                .scalar()
            )
            paid_at = last_payment_at or inv.created_at
            if paid_at <= due_date:
                on_time += 1
        elif due_date < now:
            # Still unpaid/partial and already past due — counts as not-on-time.
            considered += 1

    if considered == 0:
        return NEUTRAL_PAYMENT_CONSISTENCY_SCORE

    return round((on_time / considered) * 100, 1)


def _order_count_since(db: Session, customer_id: uuid.UUID, days: int) -> int:
    cutoff = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(func.count(Order.id))
        .filter(Order.customer_id == customer_id, Order.created_at >= cutoff)
        .scalar()
        or 0
    )


def _revenue_since(db: Session, customer_id: uuid.UUID, days: int) -> float:
    cutoff = datetime.utcnow() - timedelta(days=days)
    total = (
        db.query(func.coalesce(func.sum(Invoice.total_amount), 0))
        .filter(Invoice.customer_id == customer_id, Invoice.created_at >= cutoff)
        .scalar()
    )
    return float(total or 0)


def rank_customers_for_allocation(
    db: Session,
    tenant_id: uuid.UUID,
    sku_id: uuid.UUID | None = None,
) -> list[dict]:
    """
    Ranks customers with an OPEN demand gap by a composite allocation-priority score.

    Args:
        db: active SQLAlchemy session.
        tenant_id: tenant to scope the ranking to.
        sku_id: optional Product.id. When provided, only customers with an OPEN
            STOCK_SHORTAGE-or-any-reason demand gap for that specific product are
            considered. When omitted, all customers with any OPEN demand gap
            (any product) are considered.

    Returns:
        List of dicts, sorted by score descending. Empty list if there are no
        open demand gaps matching the filter.
    """
    gap_query = db.query(DemandGap).filter(
        DemandGap.tenant_id == tenant_id,
        DemandGap.status == "OPEN",
    )
    if sku_id is not None:
        gap_query = gap_query.filter(DemandGap.product_id == sku_id)

    gaps = gap_query.all()
    if not gaps:
        return []

    gaps_by_customer: dict[uuid.UUID, list[DemandGap]] = defaultdict(list)
    for gap in gaps:
        gaps_by_customer[gap.customer_id].append(gap)

    tenant = db.get(DistributorTenant, tenant_id)
    customers = (
        db.query(Customer)
        .filter(Customer.id.in_(gaps_by_customer.keys()))
        .all()
    )

    raw: list[dict] = []
    for customer in customers:
        customer_gaps = gaps_by_customer[customer.id]
        raw.append({
            "customer_id": customer.id,
            "customer_name": customer.name,
            "payment_consistency": _compute_payment_consistency(db, tenant, customer),
            "orders_90d": _order_count_since(db, customer.id, ORDER_FREQUENCY_WINDOW_DAYS),
            "orders_30d": _order_count_since(db, customer.id, ORDER_FREQUENCY_RECENT_WINDOW_DAYS),
            "revenue_90d": _revenue_since(db, customer.id, RELATIONSHIP_VALUE_WINDOW_DAYS),
            "open_gap_qty": sum(g.gap_qty or 0 for g in customer_gaps),
            "open_gap_revenue_at_risk": sum(float(g.revenue_at_risk or 0) for g in customer_gaps),
        })

    max_orders = max((r["orders_90d"] for r in raw), default=0) or 1
    max_revenue = max((r["revenue_90d"] for r in raw), default=0) or 1

    ranked: list[dict] = []
    for r in raw:
        frequency_score = (r["orders_90d"] / max_orders) * 100 if max_orders else 0.0
        relationship_score = (r["revenue_90d"] / max_revenue) * 100 if max_revenue else 0.0

        composite_score = (
            r["payment_consistency"] * PAYMENT_CONSISTENCY_WEIGHT
            + frequency_score * ORDER_FREQUENCY_WEIGHT
            + relationship_score * RELATIONSHIP_VALUE_WEIGHT
        )

        ranked.append({
            "customer_id": str(r["customer_id"]),
            "customer_name": r["customer_name"],
            "score": round(composite_score, 1),
            "open_gap_qty": r["open_gap_qty"],
            "open_gap_revenue_at_risk": round(r["open_gap_revenue_at_risk"], 2),
            "score_breakdown": {
                "payment_consistency": r["payment_consistency"],
                "orders_last_30_days": r["orders_30d"],
                "orders_last_90_days": r["orders_90d"],
                "order_frequency_score": round(frequency_score, 1),
                "revenue_last_90_days": round(r["revenue_90d"], 2),
                "relationship_value_score": round(relationship_score, 1),
            },
            "weights": {
                "payment_consistency": PAYMENT_CONSISTENCY_WEIGHT,
                "order_frequency": ORDER_FREQUENCY_WEIGHT,
                "relationship_value": RELATIONSHIP_VALUE_WEIGHT,
            },
        })

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked
