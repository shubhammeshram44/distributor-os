import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, TenantMixin

class Invoice(Base, TenantMixin):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    gstin: Mapped[str] = mapped_column(String(15), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    irn_status: Mapped[str] = mapped_column(String(50), default="Pending")
    qr_code_status: Mapped[str] = mapped_column(String(50), default="Pending")

    # Payment allocation columns
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(50), default="UNPAID", nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # GST compliance columns
    cgst_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True, default=None)
    sgst_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True, default=None)
    # Sequential financial-year invoice number, e.g. "INV/2026-27/001".
    # Nullable for legacy rows created before this field existed. Unique per
    # tenant (enforced by a DB-level composite unique index; see the
    # 710e0718f19f migration).
    invoice_number: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
