import uuid
from sqlalchemy import String, ForeignKey, Float, Numeric, Boolean, event, select, UniqueConstraint
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
    __table_args__ = (
        # Fix for CUST-3: within a single tenant, one alias value must map
        # to exactly one customer -- prevents the TOCTOU race in
        # onboard_customer (two near-simultaneous requests for the same
        # real-world customer creating two permanently split Customer
        # records) at the database level, not just the application layer.
        UniqueConstraint("tenant_id", "alias_value", name="uq_customer_aliases_tenant_alias_value"),
    )

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


@event.listens_for(Customer, "before_insert")
def apply_inline_van_sales_defaults(mapper, connection, target: Customer):
    """Keep Van Sales inline creation consistent with tenant customer defaults.

    The current Van Sales endpoint identifies its inline-created customer by
    explicitly setting credit_limit=0 and payment_terms="Net 0". Treat that
    combination as the inline-creation signature, then replace those temporary
    placeholders with the distributor's configured defaults before persistence.
    """
    if float(target.credit_limit or 0) != 0 or target.payment_terms != "Net 0":
        return

    from app.models.tenant import DistributorTenant

    defaults = connection.execute(
        select(
            DistributorTenant.default_customer_credit_limit,
            DistributorTenant.default_customer_payment_terms,
        ).where(DistributorTenant.id == target.tenant_id)
    ).first()

    target.credit_limit = float(defaults[0]) if defaults and defaults[0] is not None else 5000.0
    target.payment_terms = defaults[1] if defaults and defaults[1] else "Net 30"
    target._created_from_van_sales_inline = True


@event.listens_for(Customer, "after_insert")
def create_inline_van_sales_phone_alias(mapper, connection, target: Customer):
    """Create the WhatsApp/customer identity alias for inline Van Sales customers."""
    if not getattr(target, "_created_from_van_sales_inline", False) or not target.phone_number:
        return

    normalized_phone = normalize_phone_number(target.phone_number)
    if not normalized_phone:
        return

    existing = connection.execute(
        select(CustomerAlias.id).where(
            CustomerAlias.tenant_id == target.tenant_id,
            CustomerAlias.alias_value == normalized_phone,
        )
    ).first()
    if existing:
        return

    connection.execute(
        CustomerAlias.__table__.insert().values(
            id=uuid.uuid4(),
            tenant_id=target.tenant_id,
            customer_id=target.id,
            alias_value=normalized_phone,
        )
    )
