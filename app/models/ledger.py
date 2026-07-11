import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, TenantMixin

class CustomerLedger(Base, TenantMixin):
    __tablename__ = "customer_ledgers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False) # "DEBIT" or "CREDIT"
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def credit(self) -> float:
        if self.type == "CREDIT":
            return float(self.amount)
        return 0.0

    @credit.setter
    def credit(self, val: float):
        self.type = "CREDIT"
        self.amount = val

    @property
    def debit(self) -> float:
        if self.type == "DEBIT":
            return float(self.amount)
        return 0.0

    @debit.setter
    def debit(self, val: float):
        self.type = "DEBIT"
        self.amount = val
