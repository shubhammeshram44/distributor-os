"""add_customer_soft_delete_columns

Fix for CUST-4: Customer had no way to be archived/deactivated -- only
hard-delete was structurally possible, and DB-1 already made that
impossible for any customer with financial history (customer_id FKs on
orders/invoices/payments/ledger are ondelete="RESTRICT"). That left no
way at all to remove a closed-down/duplicate customer from active staff
views while still preserving their historical orders/invoices, which the
product spec requires ("Soft-delete only; historical orders/invoices
remain accessible").

Adds:
- customers.is_active (Boolean, NOT NULL, default True) -- False means
  archived/soft-deleted; excluded from list_customers by default.
- customers.deleted_at (DateTime, nullable) -- when the soft-delete
  happened; NULL for active customers.

Both columns are additive and non-breaking for existing rows (default
True / NULL respectively) -- no existing customer becomes invisible or
undeletable-in-a-new-way as a result of this migration alone.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-10 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.utils.migration_helpers import column_exists

# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table('customers', schema=None) as batch_op:
        if not column_exists(bind, 'customers', 'is_active'):
            batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
        if not column_exists(bind, 'customers', 'deleted_at'):
            batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table('customers', schema=None) as batch_op:
        if column_exists(bind, 'customers', 'deleted_at'):
            batch_op.drop_column('deleted_at')
        if column_exists(bind, 'customers', 'is_active'):
            batch_op.drop_column('is_active')
