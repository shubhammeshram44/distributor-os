"""add_customer_scoped_performance_indexes

Adds the customer-scoped indexes needed for fast dashboard/collections/payment
reconciliation queries and inventory/WhatsApp lookups. Uses the project's
index_exists() idempotency helper (see app/utils/migration_helpers.py) since
this chain must apply cleanly against both a fresh DB and an existing one
that may already have some of these objects created out-of-band.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-18 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.utils.migration_helpers import index_exists

# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Orders: customer-scoped lookups (credit limit aggregation, customer detail page)
    if not index_exists(bind, 'orders', 'ix_orders_customer_id'):
        op.create_index('ix_orders_customer_id', 'orders', ['customer_id'])

    # Invoices: customer-scoped lookups used by payment reconciliation/collections
    if not index_exists(bind, 'invoices', 'ix_invoices_customer_created_at'):
        op.create_index('ix_invoices_customer_created_at', 'invoices', ['customer_id', 'created_at'])

    # Payments: customer-scoped, most-recent-first (collections, reconciliation)
    if not index_exists(bind, 'payments', 'ix_payments_customer_created_at'):
        op.create_index('ix_payments_customer_created_at', 'payments', ['customer_id', sa.text('created_at DESC')])

    # Inventory: looked up per line-item during order confirmation/deduction
    if not index_exists(bind, 'inventory', 'ix_inventory_tenant_sku'):
        op.create_index('ix_inventory_tenant_sku', 'inventory', ['tenant_id', 'sku_id'])

    # Customer aliases: WhatsApp sender-phone resolution on every inbound message
    if not index_exists(bind, 'customer_aliases', 'ix_customer_aliases_alias_value'):
        op.create_index('ix_customer_aliases_alias_value', 'customer_aliases', ['alias_value'])


def downgrade() -> None:
    bind = op.get_bind()

    if index_exists(bind, 'customer_aliases', 'ix_customer_aliases_alias_value'):
        op.drop_index('ix_customer_aliases_alias_value', table_name='customer_aliases')

    if index_exists(bind, 'inventory', 'ix_inventory_tenant_sku'):
        op.drop_index('ix_inventory_tenant_sku', table_name='inventory')

    if index_exists(bind, 'payments', 'ix_payments_customer_created_at'):
        op.drop_index('ix_payments_customer_created_at', table_name='payments')

    if index_exists(bind, 'invoices', 'ix_invoices_customer_created_at'):
        op.drop_index('ix_invoices_customer_created_at', table_name='invoices')

    if index_exists(bind, 'orders', 'ix_orders_customer_id'):
        op.drop_index('ix_orders_customer_id', table_name='orders')
