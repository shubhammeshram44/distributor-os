import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class DistributorTenant(Base):
    __tablename__ = "distributor_tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    whatsapp_order_phone: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    whatsapp_phone_id: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    whatsapp_access_token: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    plan_type: Mapped[str] = mapped_column(String(50), nullable=False, default="FREE")
    monthly_order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    notification_prefs: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        server_default='{"order_received": true, "order_confirmed": true, "order_dispatched": true, "payment_reminder": true, "new_order_alert_to_distributor": true, "order_delivered": true}'
    )


