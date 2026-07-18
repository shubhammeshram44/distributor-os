"""merge is_active and razorpay migration heads

Revision ID: a71f3fa0ecce
Revises: 3f8a1c2e9b47, 80d9a0a31875
Create Date: 2026-07-05 01:46:02.181763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a71f3fa0ecce'
down_revision: Union[str, Sequence[str], None] = ('3f8a1c2e9b47', '80d9a0a31875')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
