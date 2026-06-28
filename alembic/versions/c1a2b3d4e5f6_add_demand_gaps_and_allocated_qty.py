"""add_demand_gaps_and_allocated_qty

Revision ID: c1a2b3d4e5f6
Revises: b44937b13012, acdc75aa00ff
Create Date: 2026-06-28 18:00:00.000000

Merges the two existing branch heads (b44937b13012 and acdc75aa00ff) and adds:
  1. allocated_quantity (nullable Integer) to order_line_items
  2. demand_gaps table with status, resolved_at, and revenue_at_risk columns
  3. Three indexes on demand_gaps for common query patterns
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # Import PostgreSQL dialect features


# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = ("b44937b13012", "acdc75aa00ff")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add allocated_quantity to order_line_items
    # ------------------------------------------------------------------
    op.add_column(
        "order_line_items",
        sa.Column("allocated_quantity", sa.Integer(), nullable=True),
    )
    # No backfill — existing rows get NULL which the ORM treats as "= quantity"
    # for backward-compatible billing (see Order.total_amount property).

    # ------------------------------------------------------------------
    # 2. Create demand_gaps table
    # ------------------------------------------------------------------
    op.create_table(
        "demand_gaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason_code", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("requested_qty", sa.Integer(), nullable=True),
        sa.Column("allocated_qty", sa.Integer(), nullable=True),
        sa.Column("gap_qty", sa.Integer(), nullable=True),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("revenue_at_risk", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["distributor_tenants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 3. Indexes on demand_gaps
    # ------------------------------------------------------------------
    # Primary time-window query: latest gaps for a tenant
    op.create_index(
        "ix_demand_gaps_tenant_created",
        "demand_gaps",
        ["tenant_id", "created_at"],
        unique=False,
    )
    # Reason-code + time-window breakdown (rollup endpoint)
    op.create_index(
        "ix_demand_gaps_reason",
        "demand_gaps",
        ["tenant_id", "reason_code", "created_at"],
        unique=False,
    )
    # Per-customer drill-down (future use)
    op.create_index(
        "ix_demand_gaps_tenant_customer",
        "demand_gaps",
        ["tenant_id", "customer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_demand_gaps_tenant_customer", table_name="demand_gaps")
    op.drop_index("ix_demand_gaps_reason", table_name="demand_gaps")
    op.drop_index("ix_demand_gaps_tenant_created", table_name="demand_gaps")
    op.drop_table("demand_gaps")
    op.drop_column("order_line_items", "allocated_quantity")
