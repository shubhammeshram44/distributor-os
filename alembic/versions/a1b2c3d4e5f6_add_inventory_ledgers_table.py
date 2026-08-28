"""add_inventory_ledgers_table

Fix for INV-3: no inventory audit/movement trail existed at all --
Inventory.quantity_on_hand/quantity_committed are mutated directly at
every stock-affecting call site (order confirmation, order cancellation,
allocation-queue approval, manual restock, CSV import, ERP sync) with no
history surviving past whatever an in-memory log line happened to record.
"Why does this SKU show 42 units on hand" was unanswerable after the
fact -- a real gap for inventory disputes, shrinkage investigation, and
basic data-integrity confidence.

Adds inventory_ledgers: an append-only table recording every stock
movement's signed delta, the resulting quantity_on_hand, a movement_type
tag, and an optional reference (order id, import batch, etc.) -- mirrors
the existing customer_ledgers / CustomerLedger pattern already used for
the equivalent financial audit trail.

Revision ID: a1b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-09-11 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.utils.migration_helpers import table_exists, index_exists

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, 'inventory_ledgers'):
        op.create_table(
            'inventory_ledgers',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('sku_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('quantity_delta', sa.Integer(), nullable=False),
            sa.Column('quantity_on_hand_after', sa.Integer(), nullable=False),
            sa.Column('movement_type', sa.String(50), nullable=False),
            sa.Column('reference_id', sa.String(100), nullable=True),
            sa.Column('notes', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['sku_id'], ['products.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['tenant_id'], ['distributor_tenants.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )

    if not index_exists(bind, 'inventory_ledgers', 'ix_inventory_ledgers_tenant_sku_created'):
        op.create_index(
            'ix_inventory_ledgers_tenant_sku_created',
            'inventory_ledgers',
            ['tenant_id', 'sku_id', 'created_at'],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if index_exists(bind, 'inventory_ledgers', 'ix_inventory_ledgers_tenant_sku_created'):
        op.drop_index('ix_inventory_ledgers_tenant_sku_created', table_name='inventory_ledgers')
    if table_exists(bind, 'inventory_ledgers'):
        op.drop_table('inventory_ledgers')
