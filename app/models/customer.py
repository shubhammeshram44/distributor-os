import uuid
from sqlalchemy import String, ForeignKey, Float, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from app.database import Base, TenantMixin
from app.utils.phone import normalize_phone_number

class Customer(Base, TenantMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[str] = mapped_column(String(100), nullable=False, default=lambda: f"CUST-{uuid.uuid4().hex[:6].upper()}")
    retailer_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Unnamed Customer")
    address_text: Mapped[str] = mapped_column(String(512), nullable=False, default="Bengaluru")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # GSTIN defaults to "PENDING" (not a fabricated government ID) until the
    # customer's real GSTIN is collected. A legal Tax Invoice must never print
    # a fake-but-real-looking GSTIN for a customer we don't actually have one for.
    gstin: Mapped[str] = mapped_column(String(15), nullable=False, default="PENDING")
    tax_group: Mapped[str] = mapped_column(String(100), nullable=False, default="GST-18")
    payment_terms: Mapped[str] = mapped_column(String(255), nullable=False, default="0-15 Days")
    credit_limit: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=100000.0)
    outstanding_balance: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)

    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    whatsapp_notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    aliases: Mapped[list["CustomerAlias"]] = relationship(back_populates="customer", cascade="all, delete-orphan")

    @validates("phone_number")
    def validate_phone_number(self, key, value):
        return normalize_phone_number(value) if value else None

    @property
    def name(self) -> str:
        return self.retailer_name or "Unnamed Customer"

    @name.setter
    def name(self, value: str):
        if not value or not isinstance(value, str):
            self.retailer_name = "Unnamed Customer"
        else:
            self.retailer_name = value

class CustomerAlias(Base, TenantMixin):
    __tablename__ = "customer_aliases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    alias_value: Mapped[str] = mapped_column(String(255), nullable=False) # WhatsApp phone number or alternative name

    customer: Mapped[Customer] = relationship(back_populates="aliases")

    @validates("alias_value")
    def validate_alias_value(self, key, value):
        # We only normalize it if it looks like a phone number (i.e. has digits)
        # to prevent normalizing purely textual aliases if any exist
        if value and any(c.isdigit() for c in value):
            return normalize_phone_number(value)
        return value

