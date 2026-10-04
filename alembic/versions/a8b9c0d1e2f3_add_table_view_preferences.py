"""add table_view_preferences

Revision ID: a8b9c0d1e2f3
Revises: f4a5b6c7d8e9
Create Date: 2026-10-04 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.utils.migration_helpers import table_exists, index_exists, drop_unique_index_or_constraint

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "table_view_preferences"):
        is_pg = bind.dialect.name == "postgresql"
        uuid_type = postgresql.UUID(as_uuid=True) if is_pg else sa.CHAR(36)
        json_type = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")

        op.create_table(
            "table_view_preferences",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("tenant_id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("page_key", sa.String(length=64), nullable=False),
            sa.Column("preference_mode", sa.String(length=32), nullable=False, server_default="default"),
            sa.Column("visible_columns", json_type, nullable=False, server_default="[]"),
            sa.Column("column_order", json_type, nullable=False, server_default="[]"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["distributor_tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "user_id", "page_key", name="uq_tenant_user_page_preference"),
        )
        with op.batch_alter_table("table_view_preferences", schema=None) as batch_op:
            batch_op.create_index(
                "ix_table_prefs_lookup",
                ["tenant_id", "user_id", "page_key"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if table_exists(bind, "table_view_preferences"):
        with op.batch_alter_table("table_view_preferences", schema=None) as batch_op:
            if index_exists(bind, "table_view_preferences", "ix_table_prefs_lookup"):
                batch_op.drop_index("ix_table_prefs_lookup")
        drop_unique_index_or_constraint(bind, "table_view_preferences", "uq_tenant_user_page_preference")
        op.drop_table("table_view_preferences")
