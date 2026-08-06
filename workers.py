"""
Background workers.

The old code called .run() directly on QThread subclasses, which meant every
'thread' actually ran on the UI thread — signal.emit degenerated to a direct
slot call and only processEvents() kept the UI barely responsive. These
workers are meant to be launched with .start(); results come back through
custom signals.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from PyQt5 import QtCore

from config import API_KEY
from downloader import FinmindClient
from repositories import (
    BSRepo, FinStatRepo, ForeignInvRepo, InstitutionRepo, KBarRepo,
    MetaRepo, PBRRepo, RevenueRepo, StockRepo,
)
from strategies import by_label as strategy_by_label

# Tables grouped by download cadence.
DATA_FREQS: dict[str, list[str]] = {
    "daily_db":   ["kbar", "institution", "pbr", "foreign_inv"],
    "monthly_db": ["revenue"],
    "quarter_db": ["fin_stat", "bs"],
}
FREQ_LABELS = {"daily_db": "日資料", "monthly_db": "月資料", "quarter_db": "季資料"}

_REPO_BY_TABLE = {
    "kbar":        KBarRepo,
    "institution": InstitutionRepo,
    "pbr":         PBRRepo,
    "foreign_inv": ForeignInvRepo,
    "revenue":     RevenueRepo,
    "fin_stat":    FinStatRepo,
    "bs":          BSRepo,
}


def _meta_key(table: str) -> str:
    return f"latest_{table}"


# --------------------------------------------------------------------------
# Check-latest (synchronous — indexed MAX(date) is fast)
# --------------------------------------------------------------------------

def check_latest() -> dict[str, str]:
    """Return latest date per freq group. Uses MetaRepo if set,
    otherwise falls back to MAX(date) per table."""
    result: dict[str, str] = {}
    for freq, tables in DATA_FREQS.items():
        latest = "0"
        for t in tables:
            cached = MetaRepo.get(_meta_key(t), default="")
            if cached:
                d = cached
            else:
                d = _REPO_BY_TABLE[t].latest_date_across_all()
                if d != "0":
                    MetaRepo.set(_meta_key(t), d)
            if d > latest:
                latest = d
        result[freq] = latest
    return result


# --------------------------------------------------------------------------
# Update — network I/O, must be threaded
# --------------------------------------------------------------------------

class UpdateDataWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(str, int, int, int, int)
    finished_with_result = QtCore.pyqtSignal(bool, dict)  # (ok, per-freq latest)

    def __init__(self, latest_by_freq: dict[str, str], parent=None):
        super().__init__(parent)
        self.latest_by_freq = latest_by_freq

    def run(self) -> None:  # noqa: D401 — QThread API
        try:
            client = FinmindClient(API_KEY)
            known_stocks: set[str] = set(StockRepo.all_nos())
            out: dict[str, str] = dict(self.latest_by_freq)

            for freq, tables in DATA_FREQS.items():
                label = FREQ_LABELS[freq]
                # start = day after latest known date
                latest = self.latest_by_freq.get(freq, "0")
                if latest == "0":
                    start = "20190101"
                else:
                    dt = datetime.strptime(latest, "%Y%m%d")
                    start = dt.strftime("%Y%m%d")

                for i, table in enumerate(tables, start=1):
                    self.progress.emit(f"{label} 下載中", i, len(tables), 0, 1)
                    sids_present, rows = client.fetch(table, sid="", start=start)
                    if not rows:
                        self.progress.emit(f"{label} {table} 無新資料", i, len(tables), 1, 1)
                        continue

                    # If known_stocks is empty (first run), just take everything.
                    if known_stocks and sids_present:
                        # rows[i] corresponds to sids_present[i]
                        filtered = [
                            (sid, *row)
                            for sid, row in zip(sids_present, rows)
                            if sid in known_stocks
                        ]
                    else:
                        filtered = [(sid, *row) for sid, row in zip(sids_present, rows)]

                    repo = _REPO_BY_TABLE[table]
                    n = repo.insert_many(filtered)

                    # Update MetaRepo with the newest date seen
                    if rows:
                        # rows tuples begin with date
                        newest = max(r[0] for r in rows)
                        MetaRepo.set(_meta_key(table), newest)
                        out[freq] = max(out[freq], newest)

                    self.progress.emit(
                        f"{label} {table} 完成 (+{n})", i, len(tables), 1, 1
                    )

            self.finished_with_result.emit(True, out)
        except Exception as e:  # surface to controller instead of dying silently
            print(f"[UpdateDataWorker] error: {e}")
            self.finished_with_result.emit(False, self.latest_by_freq)


# --------------------------------------------------------------------------
# Quant strategy runner
# --------------------------------------------------------------------------

class QuantWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(str, int, int)
    finished_with_result = QtCore.pyqtSignal(str, list)  # (trading_date, sid_list)

    def __init__(self, strategy_label: str, parent=None):
        super().__init__(parent)
        self.strategy_label = strategy_label

    def run(self) -> None:
        strat = strategy_by_label(self.strategy_label)
        if strat is None:
            self.finished_with_result.emit(
                datetime.today().strftime("%Y%m%d"), []
            )
            return
        all_sids = StockRepo.all_nos()
        matched: list[str] = []
        trading_date = "0"
        for i, sid in enumerate(all_sids):
            try:
                good, latest = strat.run(sid)
            except Exception:
                good, latest = False, "0"
            if good:
                matched.append(sid)
            if latest > trading_date:
                trading_date = latest
            self.progress.emit(self.strategy_label, i + 1, len(all_sids))

        if trading_date == "0":
            trading_date = datetime.today().strftime("%Y%m%d")
        self.finished_with_result.emit(trading_date, matched)


# --------------------------------------------------------------------------
# Per-stock detail bundle (synchronous — small, fast queries)
# --------------------------------------------------------------------------

def fetch_stock_bundle(sid: str) -> dict:
    """Pull all detail data for one stock in one shot. Returns a dict of
    already-shaped rows for the controller to hand to the view."""
    return {
        "kbar60":       KBarRepo.latest(sid, 60),
        "kbar2":        KBarRepo.latest(sid, 2),
        "revenue":      RevenueRepo.latest(sid, 36),
        "pbr":          PBRRepo.latest(sid, 20),
        "institution":  InstitutionRepo.latest(sid, 30),
        "foreign_inv":  ForeignInvRepo.latest(sid, 30),
        "fin_stat":     FinStatRepo.latest(sid, 12),
    }


def batch_stock_summary(sids: Iterable[str]) -> list[tuple]:
    """One IN-list query instead of per-stock N+1. Returns rows shaped for
    the search/quant summary table:
        (name, close, spread, ratio_str, volume_int)
    """
    sids = list(sids)
    if not sids:
        return []
    kbar_map = KBarRepo.close_map(sids)
    out: list[tuple] = []
    for sid in sids:
        info = StockRepo.get(sid)
        km = kbar_map.get(sid)
        if info is None or km is None:
            continue
        date, close, spread, volume, prev_close = km
        try:
            ratio = f"{round(spread * 100 / prev_close, 2)}%" if prev_close else "--"
        except (TypeError, ZeroDivisionError):
            ratio = "--"
        display = f"{info[0]} {info[1]}"
        out.append((display, close, spread, ratio, volume))
    return out
