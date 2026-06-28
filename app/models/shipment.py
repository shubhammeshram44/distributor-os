import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship, object_session
from app.database import Base, TenantMixin

class Shipment(Base, TenantMixin):
    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    carrier: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. "Delhivery", "Blue Dart"
    tracking_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Created")
    destination: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    order: Mapped["Order"] = relationship()

    @property
    def payment_status(self) -> str:
        if hasattr(self, "_payment_status") and self._payment_status is not None:
            return self._payment_status
        session = object_session(self)
        if session is not None:
            from app.models.invoice import Invoice
            inv = session.query(Invoice).filter(Invoice.order_id == self.order_id).first()
            if inv:
                return inv.payment_status
        return "UNPAID"

    @payment_status.setter
    def payment_status(self, value: str):
        self._payment_status = value
