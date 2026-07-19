import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Integer, Numeric, DateTime, JSON, select, desc, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship, object_session, Session
from sqlalchemy.ext.hybrid import hybrid_property
from app.database import Base, TenantMixin

class Order(Base, TenantMixin):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    internal_order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False) # "WhatsApp", "Portal", "ERP"
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    invoice_type: Mapped[str] = mapped_column(String(50), nullable=False, default="UNSPECIFIED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    raw_source_text: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    delivery_source: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    # ONE-TIME DATA MIGRATION:
    # UPDATE orders SET status = 'pending_review' WHERE status = 'NEEDS_REVIEW';
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Draft")

    @hybrid_property
    def customer_mobile(self) -> str:
        session = object_session(self)
        if session is not None:
            from app.models.customer import CustomerAlias
            alias = session.query(CustomerAlias).filter(CustomerAlias.customer_id == self.customer_id).first()
            if alias:
                return alias.alias_value
        return ""

    @customer_mobile.expression
    def customer_mobile(cls):
        from app.models.customer import CustomerAlias
        return (
            select(CustomerAlias.alias_value)
            .where(CustomerAlias.customer_id == cls.customer_id)
            .correlate_except(CustomerAlias)
            .scalar_subquery()
        )

    @property
    def total_amount(self) -> float:
        return sum(
            float(
                (item.allocated_quantity if item.allocated_quantity is not None else item.quantity)
                * item.unit_price
            )
            for item in self.line_items
        )
    @property
    def payment_status(self) -> str:
        if hasattr(self, "_payment_status") and self._payment_status is not None:
            return self._payment_status
        session = object_session(self)
        if session is not None:
            from app.models.invoice import Invoice
            inv = session.query(Invoice).filter(Invoice.order_id == self.id).first()
            if inv:
                return inv.payment_status
        return "UNPAID"

    @payment_status.setter
    def payment_status(self, value: str):
        # Cache an explicit override; the getter reads _payment_status first and
        # otherwise derives status from the Invoice. Having a setter also avoids
        # AttributeError on payment_service sync writes.
        self._payment_status = value

    line_items: Mapped[list["OrderLineItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    ledger_entries: Mapped[list["OrderStateLedger"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    customer: Mapped["Customer"] = relationship()

    @property
    def current_status(self) -> str:
        val = self.status
        if val in ("NEEDS_REVIEW", "pending_review"):
            return "Needs Review"
        return val or "Draft"

    @current_status.setter
    def current_status(self, value: str):
        self.status = value

class OrderLineItem(Base, TenantMixin):
    __tablename__ = "order_line_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=True, default=None)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Quantity actually fulfilled after partial-allocation logic during Confirmation.
    # NULL means the row pre-dates demand-gap tracking — treat as fully allocated (= quantity).
    allocated_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    unmatched_raw_text: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)

    order: Mapped[Order] = relationship(back_populates="line_items")
    product: Mapped["Product"] = relationship()

class OrderStateLedger(Base, TenantMixin):
    __tablename__ = "order_state_ledger"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True) # e.g. None for new orders, or "Draft"
    to_status: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "Draft", "Confirmed", "Picked", "Dispatched"
    updated_by: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. "user_12", "system_whatsapp_agent"
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True) # For partial fulfillments/shortfalls

    order: Mapped[Order] = relationship(back_populates="ledger_entries")


class BulkJob(Base):
    __tablename__ = "bulk_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    result_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


@event.listens_for(Session, "before_flush")
def before_flush(session, flush_context, instances):
    for obj in session.new | session.dirty:
        if isinstance(obj, OrderStateLedger):
            order = session.get(Order, obj.order_id)
            if order:
                order.status = obj.to_status

