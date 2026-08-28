"""fix_cascade_delete_on_customer_financial_records

Fix for DB-1: orders.customer_id, invoices.customer_id, payments.customer_id,
customer_ledgers.customer_id, payment_promises.customer_id, and
payment_sessions.customer_id were all declared with `ondelete="CASCADE"`
back to customers.id. There is currently no customer-delete endpoint
anywhere in the API, but the schema was pre-wired so that the moment
anyone adds one (or runs an ad-hoc cleanup script/`db.delete(customer)`
-- a pattern already used elsewhere in this codebase for other models),
it would cascade-erase that customer's entire Orders, GST Invoices,
Payments, and ledger history -- permanently destroying legally-required
financial records the product's own GST/Tally compliance features depend
on surviving (spec requirement: "soft-delete only, historical orders/
invoices remain accessible").

Changes these six foreign keys from ON DELETE CASCADE to ON DELETE
RESTRICT: a customer with any financial history can no longer be
hard-deleted at all (the DB itself will refuse), forcing any future
customer-removal feature to implement actual soft-delete (a status flag)
rather than a destructive DELETE. This is a pure safety hardening with no
behavior change for any currently-shipped feature (no delete endpoint
exists to be affected).

Revision ID: b4c5d6e7f8a9
Revises: a7c91e2f4d10
Create Date: 2026-08-28 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, Sequence[str], None] = 'a7c91e2f4d10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table_name, local_column) pairs whose FK to customers.id must be
# RESTRICT instead of CASCADE. Constraint names are looked up at runtime
# via the inspector since they were originally created with
# op.create_foreign_key(None, ...) (auto-generated names), matching the
# project's existing convention (see 9eb6a140e6af_initial_schema.py).
_TARGETS = [
    ("orders", "customer_id"),
    ("invoices", "customer_id"),
    ("payments", "customer_id"),
    ("customer_ledgers", "customer_id"),
    ("payment_promises", "customer_id"),
    ("payment_sessions", "customer_id"),
]


def _find_fk_constraint_name(inspector, table_name: str, column_name: str, ref_table: str = "customers") -> str | None:
    if table_name not in inspector.get_table_names():
        return None
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("referred_table") == ref_table and column_name in (fk.get("constrained_columns") or []):
            return fk.get("name")
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, column_name in _TARGETS:
        constraint_name = _find_fk_constraint_name(inspector, table_name, column_name)
        if not constraint_name:
            # Nothing to do: either the table doesn't exist yet, or the FK
            # is already something other than a plain CASCADE-on-customers
            # constraint (e.g. already fixed by a prior partial run).
            continue
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            constraint_name, table_name, "customers",
            [column_name], ["id"], ondelete="RESTRICT"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, column_name in _TARGETS:
        constraint_name = _find_fk_constraint_name(inspector, table_name, column_name)
        if not constraint_name:
            continue
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            constraint_name, table_name, "customers",
            [column_name], ["id"], ondelete="CASCADE"
        )
