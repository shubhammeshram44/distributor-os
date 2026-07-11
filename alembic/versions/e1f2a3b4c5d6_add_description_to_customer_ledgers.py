"""add_description_to_customer_ledgers

Revision ID: e1f2a3b4c5d6
Revises: 9220f29d683d
Create Date: 2026-07-11 20:46:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.utils.migration_helpers import column_exists

# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = '9220f29d683d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable description column to customer_ledgers for audit trail.
    # Required by LedgerService.record_transaction() introduced in this release.
    bind = op.get_bind()
    if not column_exists(bind, "customer_ledgers", "description"):
        op.add_column(
            "customer_ledgers",
            sa.Column("description", sa.String(200), nullable=True)
        )


def downgrade() -> None:
    op.drop_column("customer_ledgers", "description")
