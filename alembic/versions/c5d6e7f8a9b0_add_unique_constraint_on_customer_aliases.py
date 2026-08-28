"""add_unique_constraint_on_customer_aliases

Fix for CUST-3: onboard_customer (POST /customers) checked for an existing
CustomerAlias with the same alias_value via a plain check-then-insert
SELECT, with no application-level lock and no DB-level constraint backing
it -- a classic TOCTOU race. Two near-simultaneous requests for what is
really the same real-world customer (e.g. two salesmen submitting for the
same walk-in customer, or a retried WhatsApp/Van Sales order) could both
pass the existence check before either commits, creating two permanently
split Customer records under one tenant, each with its own independent
outstanding_balance/credit tracking -- directly undermining credit-limit
enforcement for that customer.

Adds a unique index on customer_aliases(tenant_id, alias_value): within a
single tenant, one alias value (phone number or name) must map to exactly
one customer -- this is true regardless of whether the alias represents a
phone number or a free-text name, since an alias's entire purpose is an
unambiguous lookup key. The API layer (customers.py::onboard_customer)
catches the resulting IntegrityError and returns a clean 409, closing the
race instead of just moving where duplicates would surface.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-28 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.utils.migration_helpers import index_exists

# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, Sequence[str], None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not index_exists(bind, 'customer_aliases', 'uq_customer_aliases_tenant_alias_value'):
        op.create_index(
            'uq_customer_aliases_tenant_alias_value',
            'customer_aliases',
            ['tenant_id', 'alias_value'],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if index_exists(bind, 'customer_aliases', 'uq_customer_aliases_tenant_alias_value'):
        op.drop_index('uq_customer_aliases_tenant_alias_value', table_name='customer_aliases')
