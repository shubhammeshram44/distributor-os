"""add_idempotency_key_to_orders

Revision ID: f3f1ce51bada
Revises: 330d5a37503e
Create Date: 2026-07-26 12:53:24.287606

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3f1ce51bada'
down_revision: Union[str, Sequence[str], None] = '330d5a37503e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('idempotency_key', sa.String(length=100), nullable=True))
        batch_op.create_unique_constraint('uq_orders_idempotency_key', ['idempotency_key'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('uq_orders_idempotency_key', type_='unique')
        batch_op.drop_column('idempotency_key')

