import uuid
from sqlalchemy import String, ForeignKey, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, TenantMixin

class Inventory(Base, TenantMixin):
    __tablename__ = "inventory"
    __table_args__ = (
        # INV-7: last line of defense against negative stock. All known
        # decrement call sites already clamp with min()/max(0, ...), but a
        # DB-level CHECK closes the gap against any future/overlooked call
        # site or a direct DB write bypassing the app layer entirely.
        CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_quantity_on_hand_nonneg"),
    )

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
