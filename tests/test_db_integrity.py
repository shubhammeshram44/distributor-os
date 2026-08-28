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
from app.models.product import Product
from app.models.inventory import Inventory


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


def test_products_have_unique_sku_per_tenant_constraint():
    """INV-6 regression: DB-level (tenant_id, sku_id) uniqueness must exist,
    not just an app-side check-then-insert that races under concurrency."""
    constraint_names = {c.name for c in Product.__table__.constraints}
    assert "uq_products_tenant_sku_id" in constraint_names, (
        "Product is missing the uq_products_tenant_sku_id UniqueConstraint -- "
        "duplicate SKUs per tenant could be inserted concurrently (see INV-6). "
        "Verified live against Postgres 16 during development: a second INSERT "
        "with an already-used (tenant_id, sku_id) pair raises "
        "'duplicate key value violates unique constraint uq_products_tenant_sku_id'."
    )


def test_inventory_has_nonnegative_quantity_check_constraint():
    """INV-7 regression: DB-level CHECK (quantity_on_hand >= 0) must exist as
    a last line of defense, since app-level clamping alone has already been
    shown insufficient under concurrent stock mutations."""
    constraint_names = {c.name for c in Inventory.__table__.constraints}
    assert "ck_inventory_quantity_on_hand_nonneg" in constraint_names, (
        "Inventory is missing the ck_inventory_quantity_on_hand_nonneg CHECK "
        "constraint (see INV-7). Verified live against Postgres 16 during "
        "development: INSERT ... quantity_on_hand = -5 raises 'new row for "
        "relation \"inventory\" violates check constraint "
        "\"ck_inventory_quantity_on_hand_nonneg\"'."
    )


def test_orders_have_composite_tenant_scoped_dashboard_indexes():
    """DB-3 regression: dashboard.py filters on tenant_id+created_at and
    tenant_id+status together; only single-column indexes existed before,
    forcing Postgres to filter the remainder of a tenant's order set
    row-by-row at scale."""
    index_names = {ix.name for ix in Order.__table__.indexes}
    assert "ix_orders_tenant_created_at" in index_names, (
        "Order is missing the composite ix_orders_tenant_created_at index (see DB-3)."
    )
    assert "ix_orders_tenant_status" in index_names, (
        "Order is missing the composite ix_orders_tenant_status index (see DB-3)."
    )

