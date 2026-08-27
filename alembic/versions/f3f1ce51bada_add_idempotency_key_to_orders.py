"""add_idempotency_key_to_orders

Revision ID: f3f1ce51bada
Revises: 330d5a37503e
Create Date: 2026-07-26 12:53:24.287606

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3f1ce51bada'
down_revision: Union[str, Sequence[str], None] = '330d5a37503e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade safely for legacy databases and ORM-created fresh installs."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('orders')}
    constraints = {
        constraint.get('name')
        for constraint in inspector.get_unique_constraints('orders')
        if constraint.get('name')
    }

    with op.batch_alter_table('orders', schema=None) as batch_op:
        if 'idempotency_key' not in columns:
            batch_op.add_column(
                sa.Column('idempotency_key', sa.String(length=100), nullable=True)
            )
        if 'uq_orders_idempotency_key' not in constraints:
            batch_op.create_unique_constraint(
                'uq_orders_idempotency_key', ['idempotency_key']
            )


def downgrade() -> None:
    """Downgrade only objects that currently exist."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('orders')}
    constraints = {
        constraint.get('name')
        for constraint in inspector.get_unique_constraints('orders')
        if constraint.get('name')
    }

    with op.batch_alter_table('orders', schema=None) as batch_op:
        if 'uq_orders_idempotency_key' in constraints:
            batch_op.drop_constraint('uq_orders_idempotency_key', type_='unique')
        if 'idempotency_key' in columns:
            batch_op.drop_column('idempotency_key')
