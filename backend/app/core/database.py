"""SQLAlchemy database engine, session factory and declarative base.

PostgreSQL / Supabase notes
---------------------------
Supabase sets ``statement_timeout = 2min`` at the role level via
``ALTER ROLE … SET statement_timeout``.  This overrides any connection-string
``options`` we pass, but it does NOT override a ``SET statement_timeout = 0``
issued *after* the connection is established.

We use a SQLAlchemy ``connect`` event listener to run
``SET statement_timeout = 0`` on every new raw DBAPI connection.  This fires
before the connection is handed to any ORM session, so all DDL and DML on
that connection — including the startup migrations and bulk seed inserts —
run without a statement timeout.

Other reliability settings for Supabase:
  pool_pre_ping=True   — validate connections before use (evicts stale ones)
  pool_recycle=280     — recycle before Supabase's ~300 s idle eviction
  pool_size=5          — keep a small pool; free tier limits total connections
  max_overflow=5       — up to 10 total connections
"""
from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _make_engine():
    """Build the SQLAlchemy engine with dialect-appropriate settings."""
    url = settings.sqlalchemy_database_url

    if settings.is_sqlite:
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
            future=True,
        )
    else:
        # PostgreSQL / Supabase
        eng = create_engine(
            url,
            connect_args={
                "connect_timeout": 15,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 5,
                "keepalives_count": 5,
            },
            pool_pre_ping=True,
            pool_recycle=280,
            pool_size=5,
            max_overflow=5,
            future=True,
        )

        # Override Supabase's role-level statement_timeout after each
        # new raw connection is established.  This fires before the
        # connection enters the pool and before any session uses it.
        @event.listens_for(eng, "connect")
        def _on_connect(dbapi_conn, connection_record):  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            try:
                cursor.execute("SET statement_timeout = 0")
                cursor.execute("SET idle_in_transaction_session_timeout = 0")
                dbapi_conn.commit()
            finally:
                cursor.close()

        return eng


engine = _make_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Additive migrations — columns added after the initial schema.
# Tuple: (table_name, column_name, PostgreSQL DDL, SQLite DDL)
# ---------------------------------------------------------------------------
_ADDITIVE_MIGRATIONS: list[tuple[str, str, str, str]] = [
    ("exceptions", "actioned_by",  "TEXT",                      "TEXT"),
    ("exceptions", "actioned_at",  "TIMESTAMP WITH TIME ZONE",  "DATETIME"),
    ("exceptions", "action_notes", "TEXT",                      "TEXT"),
]


def _migrate_db() -> None:
    """Apply additive column migrations idempotently.

    PostgreSQL: ``ALTER TABLE … ADD COLUMN IF NOT EXISTS`` — no pre-check.
    SQLite:     inspect first; only issue ALTER when the column is absent.
    """
    is_postgresql = engine.dialect.name == "postgresql"
    insp = inspect(engine)

    with engine.connect() as conn:
        try:
            existing_tables = set(insp.get_table_names())
        except Exception:
            existing_tables = set()

        for table, column, pg_ddl, sqlite_ddl in _ADDITIVE_MIGRATIONS:
            if table not in existing_tables:
                continue

            if is_postgresql:
                sql = (
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN IF NOT EXISTS {column} {pg_ddl}"
                )
                logger.info("Migrating (pg): %s", sql)
                conn.execute(text(sql))
                conn.commit()
            else:
                existing_cols = {c["name"] for c in insp.get_columns(table)}
                if column not in existing_cols:
                    sql = f"ALTER TABLE {table} ADD COLUMN {column} {sqlite_ddl}"
                    logger.info("Migrating (sqlite): %s", sql)
                    conn.execute(text(sql))
                    conn.commit()


def init_db() -> None:
    """Create all tables (idempotent) then apply additive column migrations."""
    from app.models import audit, exception, transaction  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_db()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
