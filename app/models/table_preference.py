import uuid
import json
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, Integer, DateTime, JSON, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, TenantMixin

class TableViewPreference(Base, TenantMixin):
    """
    Durable user-level table view preferences scoped per:
    tenant_id + user_id + page_key
    """
    __tablename__ = "table_view_preferences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    page_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    preference_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="default")  # "default" | "custom"
    
    visible_columns: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
        server_default="[]"
    )
    column_order: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
        server_default="[]"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "page_key", name="uq_tenant_user_page_preference"),
        Index("ix_table_prefs_lookup", "tenant_id", "user_id", "page_key"),
    )
