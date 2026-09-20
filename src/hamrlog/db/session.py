"""Engine and session management.

A single module-level engine is created on startup. SQLite is the default, but
``HAMRLOG_DATABASE_URL`` switches the whole application to PostgreSQL or any
other SQLAlchemy backend without touching the rest of the code, which is what
a future web frontend or API would need.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from ..paths import database_path, ensure_dirs
from .migrations import add_missing_columns
from .models import CURRENT_SCHEMA_VERSION, Base, SchemaVersion

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def default_database_url() -> str:
    """Database URL from the environment, or the local SQLite file."""
    url = os.environ.get("HAMRLOG_DATABASE_URL")
    if url:
        return url
    ensure_dirs()
    # as_posix() keeps the URL valid on Windows, where paths use backslashes.
    return f"sqlite:///{database_path().as_posix()}"


def init_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Create the engine, the schema and the session factory.

    Safe to call more than once; later calls with the same URL reuse the
    existing engine.
    """
    global _engine, _session_factory

    target = url or default_database_url()
    if _engine is not None and str(_engine.url) == target:
        return _engine

    connect_args = {}
    if target.startswith("sqlite"):
        # The TUI touches the database from worker threads during exports.
        connect_args["check_same_thread"] = False

    _engine = create_engine(target, echo=echo, future=True, connect_args=connect_args)

    if target.startswith("sqlite"):
        _enable_sqlite_pragmas(_engine)

    Base.metadata.create_all(_engine)
    # Existing databases predate any column added since they were created.
    add_missing_columns(_engine)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    _stamp_schema_version()
    return _engine


def _enable_sqlite_pragmas(engine: Engine) -> None:
    """Turn on foreign keys and WAL so concurrent readers do not block."""

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def _stamp_schema_version() -> None:
    """Record the schema revision so future upgrades know where to start."""
    with session_scope() as session:
        row = session.scalars(select(SchemaVersion).limit(1)).first()
        if row is None:
            session.add(SchemaVersion(version=CURRENT_SCHEMA_VERSION))
        elif row.version != CURRENT_SCHEMA_VERSION:
            row.version = CURRENT_SCHEMA_VERSION


def session_factory() -> sessionmaker[Session]:
    """Return the configured session factory, initialising the engine if needed."""
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session context: commits on success, rolls back on error."""
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose() -> None:
    """Close pooled connections. Used by tests and on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
