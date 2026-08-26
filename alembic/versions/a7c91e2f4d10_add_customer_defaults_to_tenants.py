"""add customer defaults to distributor tenants

Revision ID: a7c91e2f4d10
Revises: e9443fe44f4c
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7c91e2f4d10"
down_revision: Union[str, Sequence[str], None] = "e9443fe44f4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("distributor_tenants")}

    with op.batch_alter_table("distributor_tenants") as batch_op:
        if "default_customer_credit_limit" not in columns:
            batch_op.add_column(sa.Column(
                "default_customer_credit_limit",
                sa.Numeric(12, 2),
                nullable=False,
                server_default="5000",
            ))
        if "default_customer_payment_terms" not in columns:
            batch_op.add_column(sa.Column(
                "default_customer_payment_terms",
                sa.String(length=50),
                nullable=False,
                server_default="Net 30",
            ))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("distributor_tenants")}

    with op.batch_alter_table("distributor_tenants") as batch_op:
        if "default_customer_payment_terms" in columns:
            batch_op.drop_column("default_customer_payment_terms")
        if "default_customer_credit_limit" in columns:
            batch_op.drop_column("default_customer_credit_limit")
