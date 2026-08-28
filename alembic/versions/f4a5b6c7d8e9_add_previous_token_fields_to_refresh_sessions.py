"""add previous token fields to refresh sessions

Revision ID: f4a5b6c7d8e9
Revises: e7f8a9b0c1d2
Create Date: 2026-08-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('refresh_sessions')]
    
    with op.batch_alter_table('refresh_sessions', schema=None) as batch_op:
        if 'previous_token_hash' not in columns:
            batch_op.add_column(sa.Column('previous_token_hash', sa.String(length=64), nullable=True))
            batch_op.create_index(batch_op.f('ix_refresh_sessions_previous_token_hash'), ['previous_token_hash'], unique=True)
        if 'previous_token_valid_until' not in columns:
            batch_op.add_column(sa.Column('previous_token_valid_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('refresh_sessions')]
    
    with op.batch_alter_table('refresh_sessions', schema=None) as batch_op:
        if 'previous_token_hash' in columns:
            batch_op.drop_index(batch_op.f('ix_refresh_sessions_previous_token_hash'))
            batch_op.drop_column('previous_token_hash')
        if 'previous_token_valid_until' in columns:
            batch_op.drop_column('previous_token_valid_until')
