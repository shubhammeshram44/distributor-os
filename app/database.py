import contextvars
import os
import uuid
import logging
from typing import Generator, Callable, TypeVar, Any
from functools import wraps
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase, with_loader_criteria, declared_attr, Mapped, mapped_column
from sqlalchemy.exc import DBAPIError, OperationalError

# Tenacity imports for resilient retries
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

# Set up logging
logger = logging.getLogger("uvicorn.error")

# Try importing driver-specific operational error for psycopg2
try:
    import psycopg2
    PSYCOPG2_OPERATIONAL_ERROR = psycopg2.OperationalError
except ImportError:
    PSYCOPG2_OPERATIONAL_ERROR = None

# Context variable to hold tenant ID of the current request/session
tenant_context: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar("tenant_id", default=None)

# 1. Capture environment targets defensively across multi-case properties
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("database_url")

# 2. Production fail-safe: Ensure the string is never None during boot evaluation
if not DATABASE_URL:
    # Use a localized fallback tracking database so the container completes initialization safely
    DATABASE_URL = "sqlite:///./fallback_local_stub.db"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. Compile connection parameters defensively
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# 4. Configure pooling parameters dynamically for high-throughput scaling
engine_kwargs = {
    "connect_args": connect_args,
}

if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_timeout": float(os.getenv("DB_POOL_TIMEOUT", "30.0")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
        "pool_pre_ping": True
    })
else:
    # SQLite fallback pre-ping
    engine_kwargs.update({
        "pool_pre_ping": True
    })

# Construct the engine with advanced connection pooling
engine = create_engine(
    DATABASE_URL,
    **engine_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---------------------------------------------------------------------------
# Transient Database Error Handler & Tenacity Decorator
# ---------------------------------------------------------------------------

def is_transient_db_error(exception: Exception) -> bool:
    """
    Proactively identify transient database errors eligible for retry.
    Triggers retry on:
    - Connection resets, closed connections, SSL connection unexpected closures.
    - psycopg2.OperationalError / OperationalError.
    """
    # 1. Direct match on connection error types
    if isinstance(exception, (ConnectionResetError, BrokenPipeError)):
        logger.warning(f"Transient network error detected: {type(exception).__name__}. Retrying db operation...")
        return True

    # 2. Match on SQLAlchemy OperationalError
    if isinstance(exception, OperationalError):
        logger.warning(f"SQLAlchemy OperationalError detected: {exception}. Retrying db operation...")
        return True

    # 3. Match on driver-specific psycopg2 OperationalError
    if PSYCOPG2_OPERATIONAL_ERROR and isinstance(exception, PSYCOPG2_OPERATIONAL_ERROR):
        logger.warning(f"psycopg2 OperationalError detected: {exception}. Retrying db operation...")
        return True

    # 4. Check nested DBAPIError exceptions (SQLAlchemy wraps raw driver exceptions)
    if isinstance(exception, DBAPIError):
        orig = exception.orig
        if orig:
            if isinstance(orig, (ConnectionResetError, BrokenPipeError)):
                logger.warning("Nested connection reset error detected. Retrying...")
                return True
            if PSYCOPG2_OPERATIONAL_ERROR and isinstance(orig, PSYCOPG2_OPERATIONAL_ERROR):
                logger.warning("Nested psycopg2 OperationalError detected. Retrying...")
                return True
        
        # Check error message strings for connection drops
        err_msg = str(exception).lower()
        transient_phrases = [
            "ssl connection has been closed",
            "connection reset",
            "server closed the connection",
            "operationalerror",
            "connection refused",
            "timeout"
        ]
        if any(phrase in err_msg for phrase in transient_phrases):
            logger.warning(f"Transient error phrase matched in exception: {exception}. Retrying...")
            return True

    return False

# Configure Tenacity Retry Strategy
# Max 3 retries (total 4 attempts), exponential backoff: 0.1s -> 0.2s -> 0.4s -> 0.8s
# Total wait time is less than 2s to prevent holding webhook sockets open.
db_retry = retry(
    retry=retry_if_exception(is_transient_db_error),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=0.8),
    reraise=True
)

F = TypeVar("F", bound=Callable[..., Any])

def with_db_retry(func: F) -> F:
    """
    Decorator to wrap database operations with tenacity retry logic for transient errors.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return db_retry(func)(*args, **kwargs)
    return wrapper  # type: ignore

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

@contextmanager
def db_session_context() -> Generator[Session, None, None]:
    """
    Robust database session context manager ensuring clean closure of database connections.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a database session and guaranteeing connection return.
    """
    with db_session_context() as db:
        yield db
