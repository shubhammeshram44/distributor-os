import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, TenantMixin

class PaymentSession(Base, TenantMixin):
    __tablename__ = "payment_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    
    # Razorpay data
    razorpay_payment_link_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_link_short_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payment_link_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Status lifecycle: PENDING → ACTIVE → PAID | EXPIRED | FAILED
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    # Razorpay payment confirmation
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_payment_sessions_invoice_id", "invoice_id"),
        Index("ix_payment_sessions_tenant_status", "tenant_id", "status"),
    )
