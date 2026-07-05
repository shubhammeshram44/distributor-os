"""add is_active to products

Revision ID: 3f8a1c2e9b47
Revises: 0a4560241e1f
Create Date: 2026-06-30

"""
from alembic import op
import sqlalchemy as sa

from app.utils.migration_helpers import column_exists

# revision identifiers, used by Alembic.
revision = '3f8a1c2e9b47'
down_revision = '0a4560241e1f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_active column to products table with default True for all existing rows.
    # Skipped if already present (e.g. created by the initial-schema migration's
    # create_all() bootstrap on a fresh database).
    bind = op.get_bind()
    if not column_exists(bind, 'products', 'is_active'):
        with op.batch_alter_table('products') as batch_op:
            batch_op.add_column(
                sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'))
            )


def downgrade() -> None:
    with op.batch_alter_table('products') as batch_op:
        batch_op.drop_column('is_active')
