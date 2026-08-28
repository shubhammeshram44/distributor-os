import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, TenantMixin


class InventoryLedger(Base, TenantMixin):
    """Fix for INV-3: an append-only audit trail of every stock mutation.

    Mirrors the CustomerLedger pattern (app/models/ledger.py) -- inventory
    itself (Inventory.quantity_on_hand/quantity_committed) is a mutable
    current-state cache; this table is the immutable history of every
    change that produced that state, so "why does this SKU show 42 units"
    is always answerable after the fact (a real gap the audit flagged:
    previously no record survived past the in-memory logger.info() call a
    stock change might happen to make, if any).
    """
    __tablename__ = "inventory_ledgers"
    __table_args__ = (
        Index("ix_inventory_ledgers_tenant_sku_created", "tenant_id", "sku_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    # Signed delta applied to quantity_on_hand by this movement (negative for
    # a deduction, positive for a restock/restore/initial stock).
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    # quantity_on_hand immediately AFTER this movement was applied -- lets a
    # reconciliation job detect drift without replaying the whole history.
    quantity_on_hand_after: Mapped[int] = mapped_column(Integer, nullable=False)
    # e.g. "ORDER_CONFIRMED", "ORDER_CANCELLED", "ALLOCATION_APPROVED",
    # "MANUAL_RESTOCK", "INITIAL_STOCK", "CSV_IMPORT_SYNC", "ERP_SYNC".
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Free-form external reference (order.internal_order_id, a demand_gap
    # id, an import batch, etc.) -- nullable since not every movement has
    # one (e.g. a plain manual restock).
    reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
