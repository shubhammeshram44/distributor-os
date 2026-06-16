import uuid
from sqlalchemy import String, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, TenantMixin

class User(Base, TenantMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email_or_phone: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False) # "SUPER_ADMIN", "FINANCE", "OPERATOR", "DRIVER"
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True, default=None)

