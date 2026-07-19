"""merge invoice_gst and payment_promises migration heads

Revision ID: 1acdb3068945
Revises: 710e0718f19f, d58e307aa4af
Create Date: 2026-07-19 11:42:25.344080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1acdb3068945'
down_revision: Union[str, Sequence[str], None] = ('710e0718f19f', 'd58e307aa4af')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
