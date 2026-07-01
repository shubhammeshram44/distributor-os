"""add_payment_sessions

Revision ID: d4e5f6a7b8c9
Revises: c1a2b3d4e5f6
Create Date: 2026-07-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create table payment_sessions
    op.create_table(
        "payment_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        
        sa.Column("razorpay_payment_link_id", sa.String(100), nullable=True),
        sa.Column("payment_link_url", sa.String(500), nullable=True),
        sa.Column("payment_link_short_url", sa.String(200), nullable=True),
        sa.Column("payment_link_expires_at", sa.DateTime(), nullable=True),
        
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        
        sa.Column("razorpay_payment_id", sa.String(100), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["distributor_tenants.id"], ondelete="CASCADE"),
        
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_id")
    )

    # 2. Create indexes
    op.create_index(
        "ix_payment_sessions_invoice_id",
        "payment_sessions",
        ["invoice_id"],
        unique=False
    )
    op.create_index(
        "ix_payment_sessions_tenant_status",
        "payment_sessions",
        ["tenant_id", "status"],
        unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_payment_sessions_tenant_status", table_name="payment_sessions")
    op.drop_index("ix_payment_sessions_invoice_id", table_name="payment_sessions")
    op.drop_table("payment_sessions")
