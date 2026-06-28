"""add_shipment_created_at_and_indexes

Revision ID: b44937b13012
Revises: 5cdd58b4bf04
Create Date: 2026-06-28 19:36:20.968845

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b44937b13012'
down_revision: Union[str, Sequence[str], None] = '5cdd58b4bf04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_at column with default CURRENT_TIMESTAMP
    op.add_column(
        'shipments',
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False)
    )
    # Create index on (tenant_id, order_id)
    op.create_index(
        'ix_shipments_tenant_order',
        'shipments',
        ['tenant_id', 'order_id'],
        unique=False
    )
    # Create index on (created_at)
    op.create_index(
        'ix_shipments_created_at',
        'shipments',
        ['created_at'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_shipments_created_at', table_name='shipments')
    op.drop_index('ix_shipments_tenant_order', table_name='shipments')
    op.drop_column('shipments', 'created_at')
