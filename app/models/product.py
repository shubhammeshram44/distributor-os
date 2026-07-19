import uuid
from sqlalchemy import String, ForeignKey, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, TenantMixin

class Product(Base, TenantMixin):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    pack_size: Mapped[str] = mapped_column(String(50), nullable=False)
    base_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, server_default="1")
    # GST rate as a percentage (e.g. 18.0 for 18%). Real-world rates vary by
    # product (5/12/18/28%) — default matches the previous hardcoded value so
    # existing rows keep the same invoice behavior until a distributor edits them.
    gst_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=18.0, server_default="18.0")
    # HSN (Harmonized System of Nomenclature) code, required per line item on a
    # compliant GST tax invoice. Nullable since not every distributor has it on
    # file yet; the PDF simply omits it when unset.
    hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)

    aliases: Mapped[list["ProductAlias"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    prices: Mapped[list["ProductPrice"]] = relationship(back_populates="product", cascade="all, delete-orphan")

class ProductPrice(Base, TenantMixin):
    __tablename__ = "product_prices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    tier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    product: Mapped[Product] = relationship(back_populates="prices")

class ProductAlias(Base, TenantMixin):
    __tablename__ = "product_aliases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    alias_name: Mapped[str] = mapped_column(String(255), nullable=False)

    product: Mapped[Product] = relationship(back_populates="aliases")

class ProductSupplierMapping(Base, TenantMixin):
    __tablename__ = "product_supplier_mappings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False) # Maps to Supplier profile in Customer table
    is_primary: Mapped[bool] = mapped_column(default=True)

