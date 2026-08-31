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
        _add_column_if_missing(conn, "shop_settings", "restock_prefix", "TEXT NOT NULL DEFAULT 'RST'")
        _add_column_if_missing(conn, "shop_settings", "next_restock_seq", "INTEGER NOT NULL DEFAULT 1")
        _add_column_if_missing(conn, "shop_settings", "damage_prefix", "TEXT NOT NULL DEFAULT 'DMG'")
        _add_column_if_missing(conn, "shop_settings", "next_damage_seq", "INTEGER NOT NULL DEFAULT 1")
        _add_column_if_missing(conn, "shop_settings", "return_prefix", "TEXT NOT NULL DEFAULT 'RTN'")
        _add_column_if_missing(conn, "shop_settings", "next_return_seq", "INTEGER NOT NULL DEFAULT 1")
        _add_column_if_missing(conn, "categories", "name_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "locations", "name_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "items", "name_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "items", "description_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "purchase_order_lines", "name_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "invoice_lines", "name_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "invoice_lines", "cogs_cents", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "invoice_lines", "unit", "TEXT NOT NULL DEFAULT 'ea'")
        conn.execute(
            text(
                """
                UPDATE invoice_lines
                SET unit = COALESCE(
                    (SELECT items.unit FROM items WHERE items.sku = invoice_lines.sku),
                    'ea'
                )
                WHERE unit IS NULL OR unit = '' OR unit = 'ea'
                """
            )
        )
        _add_column_if_missing(conn, "invoices", "salesperson_name", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "invoices", "cogs_cents", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "stock_movements", "purpose", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "stock_movements", "cogs_cents", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "stock_movements", "unit_cost_cents", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "stock_movements", "restock_id", "INTEGER")
        _add_column_if_missing(conn, "stock_movements", "damage_id", "INTEGER")
        _add_column_if_missing(conn, "stock_movements", "supplier_return_id", "INTEGER")
        _add_column_if_missing(conn, "shop_settings", "operator_pin_hash", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "shop_settings", "operator_pin_salt", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "shop_settings", "allow_lan", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "shop_settings", "credit_days", "INTEGER NOT NULL DEFAULT 30")
        _add_column_if_missing(conn, "invoices", "due_date", "TEXT")
        _add_column_if_missing(conn, "credit_notes", "promised_date", "TEXT")
        _backfill_paid_invoices(conn)
        _backfill_due_dates(conn)
        conn.execute(
            text("UPDATE shop_settings SET currency_symbol = 'Rp', currency_code = 'IDR' WHERE id = 1")
        )
        _scale_quantities_to_millis(conn)
        conn.commit()


def _scale_quantities_to_millis(conn) -> None:
    """v1 stored whole units. v2 stores thousandths so 0.5 m³ is a real quantity."""
    version = int(conn.execute(text("PRAGMA user_version")).scalar() or 0)
    if version >= 2:
        return
    tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    for table, column in (
        ("items", "quantity"),
        ("items", "reorder_point"),
        ("purchase_order_lines", "quantity"),
        ("invoice_lines", "quantity"),
        ("restock_lines", "quantity"),
        ("damage_lines", "quantity"),
        ("supplier_return_lines", "quantity"),
        ("stock_lots", "qty_original"),
        ("stock_lots", "qty_remaining"),
        ("lot_consumptions", "quantity"),
        ("stock_movements", "quantity_delta"),
        ("stock_movements", "quantity_after"),
    ):
        if table not in tables:
            continue
        cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
        if column not in cols:
            continue
        conn.execute(text(f"UPDATE {table} SET {column} = {column} * 1000"))
    conn.execute(text("PRAGMA user_version = 2"))


def _backfill_paid_invoices(conn) -> None:
    tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    if "invoices" not in tables or "invoice_payments" not in tables:
        return
    conn.execute(
        text(
            """
            INSERT INTO invoice_payments (invoice_id, amount_cents, note, created_at)
            SELECT id, total_cents, 'Paid in full', COALESCE(paid_at, issued_at)
            FROM invoices
            WHERE status = 'paid'
              AND id NOT IN (SELECT invoice_id FROM invoice_payments)
            """
        )
    )


def _backfill_due_dates(conn) -> None:
    tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    if "invoices" not in tables or "shop_settings" not in tables:
        return
    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(invoices)"))}
    if "due_date" not in cols:
        return
    conn.execute(
        text(
            """
            UPDATE invoices
            SET due_date = date(
                substr(issued_at, 1, 10),
                '+' || COALESCE((SELECT credit_days FROM shop_settings LIMIT 1), 30) || ' days'
            )
            WHERE due_date IS NULL AND issued_at IS NOT NULL AND issued_at != ''
            """
        )
    )


def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    if table not in tables:
        return
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
