import uuid
from sqlalchemy import String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, TenantMixin

class Inventory(Base, TenantMixin):
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_committed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    @property
    def physical_stock(self) -> int:
        return self.quantity_on_hand

    @physical_stock.setter
    def physical_stock(self, value: int):
        self.quantity_on_hand = value
