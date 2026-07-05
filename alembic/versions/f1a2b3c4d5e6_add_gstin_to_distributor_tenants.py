"""add_gstin_to_distributor_tenants

Revision ID: f1a2b3c4d5e6
Revises: a71f3fa0ecce
Create Date: 2026-07-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.utils.migration_helpers import column_exists

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'a71f3fa0ecce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists(bind, "distributor_tenants", "gstin"):
        op.add_column(
            "distributor_tenants",
            sa.Column("gstin", sa.String(15), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if column_exists(bind, "distributor_tenants", "gstin"):
        op.drop_column("distributor_tenants", "gstin")
