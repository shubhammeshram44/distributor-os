import contextvars
import os
import uuid
from typing import Generator
from sqlalchemy import create_engine, event, text, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase, with_loader_criteria, declared_attr, Mapped, mapped_column

# Context variable to hold tenant ID of the current request/session
tenant_context: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar("tenant_id", default=None)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{os.path.join(BASE_DIR, 'distributor_os.db')}"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

class SafeUUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            if dialect.name == "postgresql":
                return value
            else:
                return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except ValueError:
            return value

class Base(DeclarativeBase):
    type_annotation_map = {
        uuid.UUID: SafeUUID
    }


class TenantMixin:
    """
    Mixin class that all tenant-specific models must inherit from.
    Ensures they possess a tenant_id field and automatically applies
    multi-tenant query filtering.
    """
    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(ForeignKey("distributor_tenants.id", ondelete="CASCADE"), nullable=False)

@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filtering(orm_execute_state):
    """
    Automatically filters all select queries on TenantMixin tables
    by the active tenant_id stored in the contextvar.
    """
    tenant_id = tenant_context.get()
    if tenant_id is not None and not orm_execute_state.is_column_load:
        dialect_name = orm_execute_state.session.get_bind().dialect.name
        bind_val = str(tenant_id) if dialect_name == "sqlite" else tenant_id
        orm_execute_state.statement = orm_execute_state.statement.options(
            with_loader_criteria(
                TenantMixin,
                lambda cls: cls.tenant_id == bind_val,
                include_aliases=True
            )
        )

@event.listens_for(Session, "after_begin")
def _set_postgres_rls_context(session, transaction, connection):
    """
    For PostgreSQL connections, registers the active tenant_id inside the session-local
    settings so PostgreSQL RLS policies can isolate data at the DB driver layer.
    """
    tenant_id = tenant_context.get()
    if tenant_id is not None:
        if connection.dialect.name == "postgresql":
            connection.execute(
                text("SET LOCAL app.current_tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)}
            )

@event.listens_for(Session, "before_flush")
def _assign_tenant_id_before_flush(session, flush_context, instances):
    """
    Automatically injects the active tenant_id into any newly created TenantMixin model
    before committing the insert to the database.
    """
    tenant_id = tenant_context.get()
    if tenant_id is not None:
        for obj in session.new:
            if isinstance(obj, TenantMixin):
                # Check if tenant_id is not set or None
                if getattr(obj, "tenant_id", None) is None:
                    obj.tenant_id = tenant_id

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
