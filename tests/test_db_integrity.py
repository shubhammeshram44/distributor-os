"""
Regression tests for DB-1: verifies the actual SQLAlchemy ForeignKey
metadata for every customer-referencing financial/historical table uses
ondelete="RESTRICT" rather than "CASCADE". A customer with financial
history (orders, invoices, payments, ledger entries) must never be
hard-deletable in a way that cascades away GST/financial records the
product's own compliance features depend on surviving.

This is a fast, DB-less introspection test (checks ORM Column.foreign_keys
metadata directly) so it runs everywhere in CI without needing a live
Postgres connection to exercise the actual constraint -- the live
behavior (a real DELETE being blocked, and the Alembic migration/downgrade
round-trip) was manually verified against a real postgres:16 instance
during development of this fix; this test guards against a future
regression silently reverting the ondelete value in the ORM model.
"""
from app.models.order import Order
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.ledger import CustomerLedger
from app.models.payment_promise import PaymentPromise
from app.models.payment_session import PaymentSession


def _customer_fk_ondelete(model, column_name="customer_id"):
    column = model.__table__.columns[column_name]
    fks = [fk for fk in column.foreign_keys if fk.column.table.name == "customers"]
    assert fks, f"{model.__name__}.{column_name} has no FK to customers"
    return fks[0].ondelete


def test_financial_records_use_restrict_not_cascade_on_customer_delete():
    for model in (Order, Invoice, Payment, CustomerLedger, PaymentPromise, PaymentSession):
        ondelete = _customer_fk_ondelete(model)
        assert ondelete == "RESTRICT", (
            f"{model.__name__}.customer_id must be ondelete='RESTRICT', not '{ondelete}' -- "
            "a CASCADE here would silently destroy this customer's financial/GST history "
            "the moment any delete-customer path is ever added (see DB-1)."
        )
