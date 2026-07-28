"""add_rbac_models_and_user_email

Revision ID: ce90c9684491
Revises: f3f1ce51bada
Create Date: 2026-07-28 23:47:36.720293

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.database


# revision identifiers, used by Alembic.
revision: str = 'ce90c9684491'
down_revision: Union[str, Sequence[str], None] = 'f3f1ce51bada'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('permissions',
    sa.Column('id', app.database.SafeUUID(length=36), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key')
    )
    op.create_table('role_permissions',
    sa.Column('id', app.database.SafeUUID(length=36), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('permission_key', sa.String(length=100), nullable=False),
    sa.Column('is_allowed', sa.Boolean(), nullable=False),
    sa.Column('tenant_id', app.database.SafeUUID(length=36), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['distributor_tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'role', 'permission_key', name='uq_tenant_role_permission')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email')

    op.drop_table('role_permissions')
    op.drop_table('permissions')
