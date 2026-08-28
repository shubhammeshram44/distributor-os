"""GST-compliance helpers: sequential invoice numbering and CGST/SGST split.

Invoice numbering format: INV/{financial_year}/{sequence:03d}, e.g.
INV/2026-27/001.

Indian financial year runs Apr-Mar: if the invoice date's month is >= 4, the
FY is "{year}-{year+1 last 2 digits}"; otherwise it's "{year-1}-{year last 2
digits}".

Concurrency: the sequence number is derived by counting existing
invoice_number rows for this tenant+FY and incrementing -- under concurrent
confirmations for the same tenant within the same request-response window,
two transactions could read the same count and generate a duplicate number
(a classic count-then-insert race). A DB-level unique index on
(tenant_id, invoice_number) is the real backstop, guaranteeing no duplicate
number is ever actually persisted.

Fix for ORD-9: that backstop alone previously meant a genuine race crashed
the LOSING transaction outright with an unhandled IntegrityError -- an
otherwise perfectly valid order confirmation (credit check passed, stock
already deducted) could fail with a raw 500 purely because of an
invoice-numbering collision unrelated to its own data.
create_invoice_with_unique_number() below retries the number-generation +
insert inside a per-attempt SAVEPOINT a bounded number of times, so a race
is resolved transparently (the loser simply computes the next number and
retries) instead of surfacing as a crash. We use this retry-on-conflict
approach rather than a dedicated per-tenant counter table with
`SELECT ... FOR UPDATE` row locking, since invoice confirmation remains a
low-concurrency, per-distributor, human-triggered action in this product
today, and a bounded retry loop is a much smaller change with the same
end-to-end correctness guarantee (no duplicate numbers, no unnecessary
user-facing failure).

CGST/SGST split: standard Indian intra-state GST convention — each product's
own gst_rate (not a hardcoded 18%) is split evenly into CGST + SGST, each
applied to that line item's taxable value (allocated_quantity * unit_price).
"""
import uuid
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.invoice import Invoice

DEFAULT_GST_RATE = 18.0


def get_financial_year(dt) -> str:
    """Returns the Indian financial year string for a given datetime, e.g. '2026-27'."""
    year = dt.year
    if dt.month >= 4:
        return f"{year}-{str(year + 1)[-2:]}"
    return f"{year - 1}-{str(year)[-2:]}"


def generate_invoice_number(db: Session, tenant_id: uuid.UUID, dt) -> str:
    """Generates the next sequential invoice number for this tenant + financial year."""
    fy = get_financial_year(dt)
    prefix = f"INV/{fy}/"

    existing_count = (
        db.query(Invoice)
        .filter(
            Invoice.tenant_id == tenant_id,
            Invoice.invoice_number.like(f"{prefix}%")
        )
        .count()
    )
    sequence = existing_count + 1
    return f"{prefix}{sequence:03d}"


def create_invoice_with_unique_number(
    db: Session, tenant_id: uuid.UUID, dt, invoice_kwargs: dict, max_attempts: int = 5
) -> Invoice:
    """Creates and flushes an Invoice row with a generated sequential invoice
    number, retrying inside a per-attempt SAVEPOINT if a concurrent
    confirmation/backfill for the same tenant+financial-year already claimed
    that exact number (see ORD-9). `invoice_kwargs` must not include
    `tenant_id` or `invoice_number` -- both are set here.
    """
    last_error: IntegrityError | None = None
    for _ in range(max_attempts):
        number = generate_invoice_number(db, tenant_id, dt)
        nested = db.begin_nested()
        try:
            invoice = Invoice(tenant_id=tenant_id, invoice_number=number, **invoice_kwargs)
            db.add(invoice)
            db.flush()
            nested.commit()
            return invoice
        except IntegrityError as exc:
            nested.rollback()
            last_error = exc
            continue
    raise last_error


def compute_cgst_sgst(items, products_by_id: dict) -> tuple[float, float]:
    """Computes (cgst_amount, sgst_amount) for a set of order line items.

    Each line item's taxable value is (allocated_quantity or quantity) *
    unit_price, taxed at that line's own product.gst_rate (falling back to
    DEFAULT_GST_RATE if the product or its rate is missing), split evenly
    into CGST + SGST halves and summed across all line items.
    """
    total_gst = 0.0
    for item in items:
        qty = item.allocated_quantity if item.allocated_quantity is not None else item.quantity
        line_taxable_value = float(qty * item.unit_price)
        product = products_by_id.get(item.product_id)
        gst_rate = float(product.gst_rate) if product and product.gst_rate is not None else DEFAULT_GST_RATE
        total_gst += line_taxable_value * (gst_rate / 100.0)

    cgst_amount = round(total_gst / 2.0, 2)
    sgst_amount = round(total_gst / 2.0, 2)
    return cgst_amount, sgst_amount
