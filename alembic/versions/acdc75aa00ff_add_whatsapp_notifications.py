"""add_whatsapp_notifications

Revision ID: acdc75aa00ff
Revises: 07ea26748075
Create Date: 2026-06-27 21:41:08.633104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import app.database

# revision identifiers, used by Alembic.
revision: str = 'acdc75aa00ff'
down_revision: Union[str, Sequence[str], None] = '07ea26748075'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('whatsapp_message_logs',
        sa.Column('id', app.database.SafeUUID(length=36), nullable=False),
        sa.Column('tenant_id', app.database.SafeUUID(length=36), nullable=True),
        sa.Column('customer_id', app.database.SafeUUID(length=36), nullable=True),
        sa.Column('order_id', app.database.SafeUUID(length=36), nullable=True),
        sa.Column('event', sa.String(length=100), nullable=False),
        sa.Column('to_phone', sa.String(length=50), nullable=False),
        sa.Column('message_body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['distributor_tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('whatsapp_notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')))

    with op.batch_alter_table('distributor_tenants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notification_prefs', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), server_default='{"order_received": true, "order_confirmed": true, "order_dispatched": true, "payment_reminder": true, "new_order_alert_to_distributor": true}', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('distributor_tenants', schema=None) as batch_op:
        batch_op.drop_column('notification_prefs')

    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_column('whatsapp_notifications_enabled')

    op.drop_table('whatsapp_message_logs')
