import uuid
from sqlalchemy import String, ForeignKey, Float, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, TenantMixin

class Customer(Base, TenantMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[str] = mapped_column(String(100), nullable=False, default=lambda: f"CUST-{uuid.uuid4().hex[:6].upper()}")
    retailer_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Mock Retailer Store")
    address_text: Mapped[str] = mapped_column(String(512), nullable=False, default="Bengaluru")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    gstin: Mapped[str] = mapped_column(String(15), nullable=False, default="29AAAAA1111A1Z1")
    tax_group: Mapped[str] = mapped_column(String(100), nullable=False, default="GST-18")
    payment_terms: Mapped[str] = mapped_column(String(255), nullable=False, default="0-15 Days")
    credit_limit: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=100000.0)
    outstanding_balance: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)

    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)

    aliases: Mapped[list["CustomerAlias"]] = relationship(back_populates="customer", cascade="all, delete-orphan")

    @property
    def name(self) -> str:
        return self.retailer_name or "Mock Retailer Store"

    @name.setter
    def name(self, value: str):
        if not value or not isinstance(value, str):
            self.retailer_name = "Mock Retailer Store"
        else:
            self.retailer_name = value

class CustomerAlias(Base, TenantMixin):
    __tablename__ = "customer_aliases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    alias_value: Mapped[str] = mapped_column(String(255), nullable=False) # WhatsApp phone number or alternative name

    customer: Mapped[Customer] = relationship(back_populates="aliases")
