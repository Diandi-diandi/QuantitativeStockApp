"""
Database layer: single SQLite file with normalized schema.

Replaces the previous design of one .db file per data type and one table
per stock (daily_<sid>), which prevented JOINs and made schema evolution
painful.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from config import DB_PATH


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stocks (
    no    TEXT PRIMARY KEY,
    name  TEXT NOT NULL,
    type  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategies (
    name    TEXT PRIMARY KEY,
    content TEXT,
    type    TEXT
);

CREATE TABLE IF NOT EXISTS kbar (
    stock_no TEXT NOT NULL,
    date     TEXT NOT NULL,
    volume   INTEGER,
    money    INTEGER,
    open     REAL,
    high     REAL,
    low      REAL,
    close    REAL,
    spread   REAL,
    turnover REAL,
    PRIMARY KEY (stock_no, date)
);
CREATE INDEX IF NOT EXISTS idx_kbar_stock_date ON kbar(stock_no, date DESC);

CREATE TABLE IF NOT EXISTS institution (
    stock_no    TEXT NOT NULL,
    date        TEXT NOT NULL,
    foreign_inv INTEGER,
    inv_trust   INTEGER,
    self_dealer INTEGER,
    PRIMARY KEY (stock_no, date)
);
CREATE INDEX IF NOT EXISTS idx_institution_stock_date ON institution(stock_no, date DESC);

CREATE TABLE IF NOT EXISTS revenue (
    stock_no TEXT NOT NULL,
    date     TEXT NOT NULL,
    revenue  INTEGER,
    PRIMARY KEY (stock_no, date)
);
CREATE INDEX IF NOT EXISTS idx_revenue_stock_date ON revenue(stock_no, date DESC);

CREATE TABLE IF NOT EXISTS pbr (
    stock_no       TEXT NOT NULL,
    date           TEXT NOT NULL,
    dividend_yield REAL,
    per            REAL,
    pbr            REAL,
    PRIMARY KEY (stock_no, date)
);
CREATE INDEX IF NOT EXISTS idx_pbr_stock_date ON pbr(stock_no, date DESC);

CREATE TABLE IF NOT EXISTS foreign_inv (
    stock_no TEXT NOT NULL,
    date     TEXT NOT NULL,
    ratio    REAL,
    total    INTEGER,
    PRIMARY KEY (stock_no, date)
);
CREATE INDEX IF NOT EXISTS idx_foreign_inv_stock_date ON foreign_inv(stock_no, date DESC);

CREATE TABLE IF NOT EXISTS fin_stat (
    stock_no         TEXT NOT NULL,
    date             TEXT NOT NULL,
    eps              REAL,
    income_after_tax INTEGER,
    PRIMARY KEY (stock_no, date)
);
CREATE INDEX IF NOT EXISTS idx_fin_stat_stock_date ON fin_stat(stock_no, date DESC);

CREATE TABLE IF NOT EXISTS bs (
    stock_no TEXT NOT NULL,
    date     TEXT NOT NULL,
    equity   INTEGER,
    PRIMARY KEY (stock_no, date)
);
CREATE INDEX IF NOT EXISTS idx_bs_stock_date ON bs(stock_no, date DESC);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


# Columns of every table that has a (stock_no, date) key. Ordering matches
# the values a repository is expected to insert.
DATA_TABLES = {
    "kbar":        ["stock_no", "date", "volume", "money", "open",
                    "high", "low", "close", "spread", "turnover"],
    "institution": ["stock_no", "date", "foreign_inv", "inv_trust", "self_dealer"],
    "revenue":     ["stock_no", "date", "revenue"],
    "pbr":         ["stock_no", "date", "dividend_yield", "per", "pbr"],
    "foreign_inv": ["stock_no", "date", "ratio", "total"],
    "fin_stat":    ["stock_no", "date", "eps", "income_after_tax"],
    "bs":          ["stock_no", "date", "equity"],
}


_initialized = False


def _ensure_schema(conn: sqlite3.Connection) -> None:
    global _initialized
    if _initialized:
        return
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    _initialized = True


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """Yield a sqlite connection with schema ensured. Commits on success."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_many(table: str, rows: list[tuple]) -> int:
    """INSERT OR IGNORE many rows. Returns number of rows attempted."""
    if not rows:
        return 0
    cols = DATA_TABLES.get(table)
    if cols is None:
        raise ValueError(f"unknown data table: {table}")
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    with get_conn() as conn:
        conn.executemany(sql, rows)
    return len(rows)
