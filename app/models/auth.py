import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class WhatsAppVerification(Base):
    __tablename__ = "whatsapp_verifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    mobile_number: Mapped[str] = mapped_column(String(50), nullable=False)
    otp_code: Mapped[str] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    previous_token_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
