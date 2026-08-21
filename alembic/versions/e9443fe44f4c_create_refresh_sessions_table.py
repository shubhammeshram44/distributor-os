"""create refresh sessions table

Revision ID: e9443fe44f4c
Revises: f3f1ce51bada
Create Date: 2026-08-21 23:24:15.587689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9443fe44f4c'
down_revision: Union[str, Sequence[str], None] = 'f3f1ce51bada'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'refresh_sessions' not in tables:
        op.create_table(
            'refresh_sessions',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('user_id', sa.UUID(), nullable=False),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('last_used_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('absolute_expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('refresh_sessions', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_refresh_sessions_token_hash'), ['token_hash'], unique=True)
            batch_op.create_index(batch_op.f('ix_refresh_sessions_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'refresh_sessions' in tables:
        with op.batch_alter_table('refresh_sessions', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_refresh_sessions_user_id'))
            batch_op.drop_index(batch_op.f('ix_refresh_sessions_token_hash'))
        op.drop_table('refresh_sessions')
