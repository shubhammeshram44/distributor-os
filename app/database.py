import contextvars
import os
import uuid
from typing import Generator
from sqlalchemy import create_engine, event, text, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase, with_loader_criteria, declared_attr, Mapped, mapped_column

# Context variable to hold tenant ID of the current request/session
tenant_context: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar("tenant_id", default=None)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'distributor_os.db')}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

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
        orm_execute_state.statement = orm_execute_state.statement.options(
            with_loader_criteria(
                TenantMixin,
                lambda cls: cls.tenant_id == tenant_id,
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
