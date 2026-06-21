import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Integer, Numeric, DateTime, JSON, select, desc
from sqlalchemy.orm import Mapped, mapped_column, relationship, object_session
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
        return sum(float(item.quantity * item.unit_price) for item in self.line_items)
    @property
    def payment_status(self) -> str:
        session = object_session(self)
        if session is not None:
            from app.models.invoice import Invoice
            inv = session.query(Invoice).filter(Invoice.order_id == self.id).first()
            if inv:
                return inv.payment_status
        return "UNPAID"

    @payment_status.setter
    def payment_status(self, value: str):
        pass

    line_items: Mapped[list["OrderLineItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    ledger_entries: Mapped[list["OrderStateLedger"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    @property
    def current_status(self) -> str:
        """
        Dynamically fetches the current order status by checking the latest transition in the OrderStateLedger.
        Defaults to 'Draft' if no ledger entries exist.
        """
        session = object_session(self)
        if session is not None:
            # Query the database for the most recent ledger entry
            stmt = (
                select(OrderStateLedger.to_status)
                .where(OrderStateLedger.order_id == self.id)
                .order_by(desc(OrderStateLedger.timestamp))
                .limit(1)
            )
            res = session.execute(stmt).scalar()
            if res:
                if res == "NEEDS_REVIEW":
                    return "Needs Review"
                return res

        # Fallback to in-memory collection if session is not available or query returns empty
        if self.ledger_entries:
            sorted_entries = sorted(self.ledger_entries, key=lambda e: e.timestamp, reverse=True)
            val = sorted_entries[0].to_status
            if val == "NEEDS_REVIEW":
                return "Needs Review"
            return val
        return "Draft"

class OrderLineItem(Base, TenantMixin):
    __tablename__ = "order_line_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

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
