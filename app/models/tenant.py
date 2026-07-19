import json
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
    # Distributor's own GSTIN, required on a legally valid GST Tax Invoice
    # (CGST Rules 2017, Rule 46(b)). Nullable because some small distributors
    # are unregistered dealers; PDFs must reflect that honestly rather than
    # printing a fabricated number.
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True, default=None)
    whatsapp_order_phone: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    whatsapp_phone_id: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    whatsapp_access_token: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    razorpay_key_id: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    razorpay_key_secret_enc: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    razorpay_account_name: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    razorpay_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="test")
    whatsapp_connection_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="unknown"
    )  # "connected" | "disconnected" | "unknown"
    whatsapp_disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    whatsapp_disconnect_reason: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )  # "logged_out" | "timeout" | "conflict" | "unknown"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    plan_type: Mapped[str] = mapped_column(String(50), nullable=False, default="FREE")
    monthly_order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    notification_prefs: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        server_default=json.dumps({
            # Operational
            "order_received": True,
            "order_confirmed": True,
            "order_dispatched": True,
            "order_delivered": True,
            "new_order_alert_to_distributor": True,
            "order_needs_review_alert": True,
            # Financial
            "payment_reminder": True,
            "payment_reminder_upcoming": True,
            "payment_reminder_overdue": True,
            "payment_received_confirmation": True
        })
    )


