"""add_payment_promises

Revision ID: d58e307aa4af
Revises: f2a3b4c5d6e7
Create Date: 2026-07-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.utils.migration_helpers import table_exists, index_exists

# revision identifiers, used by Alembic.
revision: str = 'd58e307aa4af'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Create table payment_promises
    if not table_exists(bind, "payment_promises"):
        op.create_table(
            "payment_promises",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),

            sa.Column("promised_date", sa.Date(), nullable=False),
            sa.Column("promised_amount", sa.Numeric(10, 2), nullable=True),
            sa.Column("raw_message", sa.Text(), nullable=False),

            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),

            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),

            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["distributor_tenants.id"], ondelete="CASCADE"),

            sa.PrimaryKeyConstraint("id"),
        )

    # 2. Create indexes
    if not index_exists(bind, "payment_promises", "ix_payment_promises_customer_id"):
        op.create_index(
            "ix_payment_promises_customer_id",
            "payment_promises",
            ["customer_id"],
            unique=False
        )
    if not index_exists(bind, "payment_promises", "ix_payment_promises_tenant_status"):
        op.create_index(
            "ix_payment_promises_tenant_status",
            "payment_promises",
            ["tenant_id", "status"],
            unique=False
        )


def downgrade() -> None:
    op.drop_index("ix_payment_promises_tenant_status", table_name="payment_promises")
    op.drop_index("ix_payment_promises_customer_id", table_name="payment_promises")
    op.drop_table("payment_promises")
