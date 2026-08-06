"""
One-shot migration from the legacy per-stock-table SQLite files to the new
unified schema.

Legacy layout:
    db/kbar.db          daily_2330, daily_2317, ...
    db/institution.db   daily_2330, ...
    db/revenue.db       ...
    db/other_info.db    stockno, strategy

New layout:
    db/quantstock.db    kbar(stock_no, date, ...), institution(...), stocks, strategies

The script is idempotent: it refuses to run if quantstock.db already contains
data, so re-running does not double-insert.

Usage:
    python migrate.py            # migrate
    python migrate.py --dry-run  # report row counts without writing
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

from config import BACKUP_DIR, DB_DIR, DB_PATH
from db import DATA_TABLES, get_conn

LEGACY_DATA_DBS = {
    "kbar":        ["volume", "money", "open", "high", "low", "close", "spread", "turnover"],
    "institution": ["foreign_inv", "inv_trust", "self_dealer"],
    "revenue":     ["revenue"],
    "pbr":         ["dividend_yield", "per", "pbr"],
    "foreign_inv": ["ratio", "total"],
    "fin_stat":    ["eps", "IncomeAfterTax"],
    "bs":          ["equity"],
}


def _legacy_stock_tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'daily_%'"
    )
    return [row[0] for row in cur.fetchall()]


def _target_has_data() -> bool:
    with get_conn() as conn:
        for t in DATA_TABLES:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            if n:
                return True
        for t in ("stocks", "strategies"):
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            if n:
                return True
    return False


def _backup_legacy() -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    for f in DB_DIR.glob("*.db"):
        if f.name == DB_PATH.name:
            continue
        dst = BACKUP_DIR / f.name
        if not dst.exists():
            shutil.copy2(f, dst)
            print(f"  backup {f.name} -> {dst}")


def _migrate_other_info(dry_run: bool) -> tuple[int, int]:
    src = DB_DIR / "other_info.db"
    if not src.exists():
        return 0, 0
    n_stock = n_strat = 0
    with sqlite3.connect(src) as srcconn:
        srcconn.row_factory = sqlite3.Row
        stockno_rows = list(srcconn.execute("SELECT no, name, type FROM stockno"))
        try:
            strat_rows = list(srcconn.execute("SELECT name, content, type FROM strategy"))
        except sqlite3.OperationalError:
            strat_rows = []
    if dry_run:
        return len(stockno_rows), len(strat_rows)
    with get_conn() as dst:
        dst.executemany(
            "INSERT OR IGNORE INTO stocks(no, name, type) VALUES (?, ?, ?)",
            [(r["no"], r["name"], r["type"]) for r in stockno_rows],
        )
        n_stock = dst.total_changes
        dst.executemany(
            "INSERT OR IGNORE INTO strategies(name, content, type) VALUES (?, ?, ?)",
            [(r["name"], r["content"], r["type"]) for r in strat_rows],
        )
        n_strat = dst.total_changes - n_stock
    return n_stock, n_strat


def _migrate_data_table(name: str, cols: list[str], dry_run: bool) -> int:
    src = DB_DIR / f"{name}.db"
    if not src.exists():
        return 0
    target_cols = DATA_TABLES[name]  # stock_no, date, ...
    col_sql = ", ".join(target_cols)
    placeholders = ", ".join(["?"] * len(target_cols))
    total = 0
    with sqlite3.connect(src) as srcconn:
        tables = _legacy_stock_tables(srcconn)
        batch: list[tuple] = []
        for tbl in tables:
            sid = tbl[len("daily_"):]
            select_sql = f"SELECT date, {', '.join(cols)} FROM {tbl}"
            try:
                rows = srcconn.execute(select_sql).fetchall()
            except sqlite3.OperationalError:
                continue
            for row in rows:
                batch.append((sid, *row))
            total += len(rows)
    if dry_run or not batch:
        return total
    with get_conn() as dst:
        dst.executemany(
            f"INSERT OR IGNORE INTO {name}({col_sql}) VALUES ({placeholders})",
            batch,
        )
    return total


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv

    if not any((DB_DIR / f"{t}.db").exists() for t in LEGACY_DATA_DBS) \
       and not (DB_DIR / "other_info.db").exists():
        print("No legacy .db files found; nothing to migrate.")
        return 0

    if not dry_run and _target_has_data():
        print(f"Refusing to run: {DB_PATH} already has data. "
              "Delete it first if you really want to re-migrate.")
        return 1

    if not dry_run:
        print("Backing up legacy .db files...")
        _backup_legacy()

    print("\nMigrating stocks + strategies from other_info.db...")
    n_stock, n_strat = _migrate_other_info(dry_run)
    print(f"  stocks: {n_stock}, strategies: {n_strat}")

    print("\nMigrating per-stock tables into unified tables...")
    for name, cols in LEGACY_DATA_DBS.items():
        n = _migrate_data_table(name, cols, dry_run)
        print(f"  {name}: {n} rows")

    print("\nDone." + (" (dry run — nothing written)" if dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
