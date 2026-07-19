import uuid
from datetime import date, datetime
from sqlalchemy import String, ForeignKey, Numeric, Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, TenantMixin


class PaymentPromise(Base, TenantMixin):
    __tablename__ = "payment_promises"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    # Nullable: a promise may be general (covers multiple/unspecified invoices) rather than tied to one invoice.
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True)

    promised_date: Mapped[date] = mapped_column(Date, nullable=False)
    promised_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)

    # Lifecycle: pending -> fulfilled | broken
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
