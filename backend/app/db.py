from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.paths import sqlite_path


def database_url() -> str:
    return os.environ.get("DATABASE_URL") or f"sqlite:///{sqlite_path()}"


def make_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "", 1)
        if path not in (":memory:",) and not path.startswith("file:"):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _connection_record):  # noqa: ARG001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        _add_column_if_missing(conn, "shop_settings", "currency_code", "TEXT NOT NULL DEFAULT 'IDR'")
        _add_column_if_missing(conn, "categories", "name_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "locations", "name_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "items", "name_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "items", "description_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "purchase_order_lines", "name_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "invoice_lines", "name_id", "TEXT NOT NULL DEFAULT ''")
        conn.execute(
            text("UPDATE shop_settings SET currency_symbol = 'Rp', currency_code = 'IDR' WHERE id = 1")
        )
        conn.commit()


def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
    if column not in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def replace_sqlite_file(engine: Engine, payload: bytes) -> Engine:
    """Swap the on-disk SQLite file and return a new engine bound to it."""
    database = engine.url.database
    if not database or database == ":memory:":
        raise ValueError("Backup restore needs a file database")
    path = Path(database)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        conn.commit()
    engine.dispose()
    for extra in (Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        if extra.exists():
            extra.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    new_engine = make_engine(f"sqlite:///{path}")
    init_db(new_engine)
    return new_engine
