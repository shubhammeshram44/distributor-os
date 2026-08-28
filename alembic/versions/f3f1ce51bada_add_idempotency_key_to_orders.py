"""add_idempotency_key_to_orders

Fix (found while working on an unrelated DB-1 migration in this same PR):
on a genuinely fresh database, the initial-schema migration's fast path
(`Base.metadata.create_all(checkfirst=True)`, see
9eb6a140e6af_initial_schema.py) already creates `orders.idempotency_key`
and its unique index, since the current ORM model (app/models/order.py)
already declares this column with `unique=True, index=True`. This
migration then tried to unconditionally `add_column()` the same column,
causing `psycopg2.errors.DuplicateColumn` and failing the entire
migration chain on every fresh-DB run -- the exact same class of bug
previously fixed for `whatsapp_connection_status` (see
9220f29d683d_add_whatsapp_connection_status_columns.py) and other
migrations in this project. Guarded with the project's existing
column_exists() helper, matching that established pattern.

Revision ID: f3f1ce51bada
Revises: 330d5a37503e
Create Date: 2026-07-26 12:53:24.287606

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.utils.migration_helpers import column_exists


# revision identifiers, used by Alembic.
revision: str = 'f3f1ce51bada'
down_revision: Union[str, Sequence[str], None] = '330d5a37503e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if not column_exists(bind, 'orders', 'idempotency_key'):
        with op.batch_alter_table('orders', schema=None) as batch_op:
            batch_op.add_column(sa.Column('idempotency_key', sa.String(length=100), nullable=True))

    inspector = sa.inspect(bind)
    existing_constraint_names = {
        uc['name'] for uc in inspector.get_unique_constraints('orders')
    }
    existing_index_names = {
        ix['name'] for ix in inspector.get_indexes('orders')
    }
    # The fast-path create_all() above creates a UNIQUE INDEX (from the
    # ORM's `unique=True, index=True`), not a named UNIQUE CONSTRAINT --
    # different mechanism, different catalog entry, so both must be
    # checked independently before this migration adds its own constraint.
    if 'uq_orders_idempotency_key' not in existing_constraint_names and \
            'uq_orders_idempotency_key' not in existing_index_names:
        with op.batch_alter_table('orders', schema=None) as batch_op:
            batch_op.create_unique_constraint('uq_orders_idempotency_key', ['idempotency_key'])


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_constraint_names = {
        uc['name'] for uc in inspector.get_unique_constraints('orders')
    }
    if 'uq_orders_idempotency_key' in existing_constraint_names:
        with op.batch_alter_table('orders', schema=None) as batch_op:
            batch_op.drop_constraint('uq_orders_idempotency_key', type_='unique')
    if column_exists(bind, 'orders', 'idempotency_key'):
        with op.batch_alter_table('orders', schema=None) as batch_op:
            batch_op.drop_column('idempotency_key')

