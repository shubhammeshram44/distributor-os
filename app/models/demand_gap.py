import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Integer, Numeric, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID  # Explicitly use PostgreSQL UUID dialect
from app.database import Base, TenantMixin


class DemandGap(Base, TenantMixin):
    """
    Records every instance of unmet customer demand at the point of order confirmation.

    reason_code values:
      STOCK_SHORTAGE — one or more requested line-item quantities exceeded warehouse stock;
                       partial allocation was performed and the shortfall is captured here.
      CREDIT_LIMIT   — the customer's combined outstanding balance would have exceeded their
                       credit limit; the order was rejected entirely and the full requested
                       value is recorded here.

    status lifecycle (state transitions are future scope — do NOT implement transitions here):
      OPEN        — gap recorded, not yet addressed (default for all new rows)
      RECOVERED   — gap was subsequently fulfilled (e.g. restock + re-order)
      LOST        — revenue confirmed lost (customer did not re-order)
      CANCELLED   — gap entry invalidated (e.g. order itself was cancelled)
      BACKORDERED — item is on order from supplier; demand preserved

    resolved_at is set when status leaves OPEN; reserved for future use.
    """

    __tablename__ = "demand_gaps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Parent order and customer references mapped as native postgres UUIDs
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Optional product reference — NULL for CREDIT_LIMIT rows
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Reason code: "STOCK_SHORTAGE" | "CREDIT_LIMIT"
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)

    # Status lifecycle — all new rows start as OPEN
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")

    # Timestamp for when status left OPEN (reserved for future state transitions)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # --- Supplementary detail fields (populated for STOCK_SHORTAGE; NULL for CREDIT_LIMIT) ---

    # Original quantity requested on the line item
    requested_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Quantity actually allocated from available stock (0 if none available)
    allocated_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Units of demand that could not be fulfilled (requested_qty - allocated_qty)
    gap_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Per-unit price of the line item at time of allocation
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    # --- Always-populated money field ---

    # Revenue at risk from this gap row — never null, always set regardless of reason_code:
    #   STOCK_SHORTAGE → gap_qty * unit_price
    #   CREDIT_LIMIT   → full current_order_total (original requested value before allocation)
    revenue_at_risk: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Creation timestamp — used for all time-window queries
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Compounding multi-indexes required for production aggregations and customer drills
    __table_args__ = (
        Index("ix_demand_gaps_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_demand_gaps_tenant_reason_created_at", "tenant_id", "reason_code", "created_at"),
        Index("ix_demand_gaps_tenant_customer_id", "tenant_id", "customer_id"),
    )
