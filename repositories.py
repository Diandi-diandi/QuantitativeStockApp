"""
Repository layer: one class per table. Callers never write SQL.

All queries use bound parameters, so upstream string concatenation of user
input into WHERE clauses is impossible by construction.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from db import DATA_TABLES, get_conn


class _DateAscTable:
    """Rows keyed by (stock_no, date) — `.latest(sid, n)` returns most-recent n."""
    table: str = ""

    @classmethod
    def latest(cls, sid: str, n: int = 1) -> list[tuple]:
        cols = [c for c in DATA_TABLES[cls.table] if c != "stock_no"]
        sql = (f"SELECT {', '.join(cols)} FROM {cls.table} "
               f"WHERE stock_no = ? ORDER BY date DESC LIMIT ?")
        with get_conn() as conn:
            return [tuple(r) for r in conn.execute(sql, (sid, n)).fetchall()]

    @classmethod
    def by_date(cls, sid: str, date: str) -> tuple | None:
        cols = [c for c in DATA_TABLES[cls.table] if c != "stock_no"]
        sql = (f"SELECT {', '.join(cols)} FROM {cls.table} "
               f"WHERE stock_no = ? AND date = ? LIMIT 1")
        with get_conn() as conn:
            row = conn.execute(sql, (sid, date)).fetchone()
            return tuple(row) if row else None

    @classmethod
    def latest_date_across_all(cls) -> str:
        with get_conn() as conn:
            row = conn.execute(f"SELECT MAX(date) FROM {cls.table}").fetchone()
            return row[0] if row and row[0] else "0"

    @classmethod
    def insert_many(cls, rows: Sequence[tuple]) -> int:
        if not rows:
            return 0
        cols = DATA_TABLES[cls.table]
        placeholders = ", ".join(["?"] * len(cols))
        sql = (f"INSERT OR IGNORE INTO {cls.table}({', '.join(cols)}) "
               f"VALUES ({placeholders})")
        with get_conn() as conn:
            cur = conn.executemany(sql, rows)
            return cur.rowcount


class KBarRepo(_DateAscTable):
    table = "kbar"

    @classmethod
    def by_month(cls, sid: str, yyyymm: str) -> list[tuple]:
        cols = [c for c in DATA_TABLES[cls.table] if c != "stock_no"]
        sql = (f"SELECT {', '.join(cols)} FROM {cls.table} "
               f"WHERE stock_no = ? AND date LIKE ? ORDER BY date DESC")
        with get_conn() as conn:
            return [tuple(r) for r in conn.execute(sql, (sid, f"{yyyymm}%")).fetchall()]

    @classmethod
    def close_map(cls, sid_list: Iterable[str]) -> dict[str, tuple]:
        """Return {sid: (date, close, spread, volume, prev_close)} for the two
        most recent rows per sid — batched in one query."""
        sids = list(sid_list)
        if not sids:
            return {}
        placeholders = ", ".join(["?"] * len(sids))
        sql = f"""
            SELECT stock_no, date, close, spread, volume
              FROM kbar
             WHERE stock_no IN ({placeholders})
             ORDER BY stock_no, date DESC
        """
        buckets: dict[str, list[tuple]] = {}
        with get_conn() as conn:
            for sid, date, close, spread, volume in conn.execute(sql, sids):
                buckets.setdefault(sid, []).append((date, close, spread, volume))
        result: dict[str, tuple] = {}
        for sid, rows in buckets.items():
            if not rows:
                continue
            latest = rows[0]
            prev_close = rows[1][1] if len(rows) > 1 else None
            result[sid] = (*latest, prev_close)
        return result


class InstitutionRepo(_DateAscTable):
    table = "institution"


class RevenueRepo(_DateAscTable):
    table = "revenue"


class PBRRepo(_DateAscTable):
    table = "pbr"


class ForeignInvRepo(_DateAscTable):
    table = "foreign_inv"


class FinStatRepo(_DateAscTable):
    table = "fin_stat"


class BSRepo(_DateAscTable):
    table = "bs"


class StockRepo:
    @staticmethod
    def get(sid: str) -> tuple | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT no, name, type FROM stocks WHERE no = ?", (sid,)
            ).fetchone()
            return tuple(row) if row else None

    @staticmethod
    def all_nos() -> list[str]:
        with get_conn() as conn:
            return [r[0] for r in conn.execute("SELECT no FROM stocks ORDER BY no")]

    @staticmethod
    def search(keyword: str) -> list[tuple]:
        """Match by stock no OR name. Case-insensitive substring."""
        pat = f"%{keyword}%"
        sql = ("SELECT no, name, type FROM stocks "
               "WHERE no LIKE ? OR name LIKE ? ORDER BY no")
        with get_conn() as conn:
            return [tuple(r) for r in conn.execute(sql, (pat, pat)).fetchall()]

    @staticmethod
    def upsert_many(rows: Sequence[tuple]) -> int:
        if not rows:
            return 0
        with get_conn() as conn:
            cur = conn.executemany(
                "INSERT OR REPLACE INTO stocks(no, name, type) VALUES (?, ?, ?)",
                rows,
            )
            return cur.rowcount


class StrategyRepo:
    @staticmethod
    def by_type(type_: str) -> list[str]:
        pat = f"%{type_}%"
        with get_conn() as conn:
            return [r[0] for r in conn.execute(
                "SELECT name FROM strategies WHERE type LIKE ? ORDER BY name",
                (pat,),
            )]

    @staticmethod
    def by_name(name: str) -> tuple | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT name, content, type FROM strategies WHERE name = ?", (name,)
            ).fetchone()
            return tuple(row) if row else None

    @staticmethod
    def upsert_many(rows: Sequence[tuple]) -> int:
        if not rows:
            return 0
        with get_conn() as conn:
            cur = conn.executemany(
                "INSERT OR REPLACE INTO strategies(name, content, type) VALUES (?, ?, ?)",
                rows,
            )
            return cur.rowcount


class MetaRepo:
    """Small key/value bag for per-frequency last-update tracking."""

    @staticmethod
    def get(key: str, default: str = "0") -> str:
        with get_conn() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return row[0] if row else default

    @staticmethod
    def set(key: str, value: str) -> None:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


REPO_BY_TABLE: dict[str, type[_DateAscTable]] = {
    "kbar":        KBarRepo,
    "institution": InstitutionRepo,
    "revenue":     RevenueRepo,
    "pbr":         PBRRepo,
    "foreign_inv": ForeignInvRepo,
    "fin_stat":    FinStatRepo,
    "bs":          BSRepo,
}
