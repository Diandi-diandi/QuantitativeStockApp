"""
Strategy registry. Kills the eval() dispatch in the old Model.

Each strategy is a plain function returning (matched: bool, date: str).
The registry is the source of truth: on app start, StrategyRegistry.sync_db()
upserts these definitions into the strategies table so the UI can pull
label + description from a single place.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from numpy import array, average

from indicators import bbands, sma, stoch
from repositories import (
    BSRepo, FinStatRepo, ForeignInvRepo, InstitutionRepo, KBarRepo,
    PBRRepo, StrategyRepo,
)

# category codes match the values in strategies.type
CATEGORIES = {
    "fund":   "基本面",
    "tech":   "技術面",
    "chip":   "籌碼面",
    "others": "其他",
}


@dataclass(frozen=True)
class Strategy:
    label: str
    category: str
    description: str
    run: Callable[[str], tuple[bool, str]]


_REGISTRY: dict[str, Strategy] = {}


def register(label: str, category: str, description: str):
    def deco(fn):
        _REGISTRY[label] = Strategy(label=label, category=category,
                                    description=description, run=fn)
        return fn
    return deco


def all_strategies() -> list[Strategy]:
    return list(_REGISTRY.values())


def by_label(label: str) -> Strategy | None:
    return _REGISTRY.get(label)


def sync_db() -> None:
    """Push registry definitions into the strategies table."""
    rows = [(s.label, s.description, s.category) for s in _REGISTRY.values()]
    StrategyRepo.upsert_many(rows)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _kbar_asc(rows: list[tuple]) -> dict[str, "array"]:
    """rows: latest-first (date, volume, money, open, high, low, close, spread, turnover)
    Returns dict of numpy arrays in ascending order."""
    rows = rows[::-1]
    return {
        "date":   array([r[0] for r in rows]),
        "volume": array([int(r[1]) for r in rows]),
        "money":  array([int(r[2]) for r in rows]),
        "open":   array([float(r[3]) for r in rows]),
        "high":   array([float(r[4]) for r in rows]),
        "low":    array([float(r[5]) for r in rows]),
        "close":  array([float(r[6]) for r in rows]),
        "spread": array([float(r[7]) for r in rows]),
    }


def _daily_ratio(spread: float, prev_close: float) -> float:
    return round(spread / prev_close, 2) if prev_close else 0.0


# --------------------------------------------------------------------------
# Fundamental strategies
# --------------------------------------------------------------------------

@register("PBR/ROE", "fund", "ROE > 8% 且 PBR < 2")
def pbr_roe(sid: str) -> tuple[bool, str]:
    fin = FinStatRepo.latest(sid, 4)
    pbr = PBRRepo.latest(sid, 1)
    if not fin or not pbr:
        return False, "0"
    val_pbr = pbr[0][-1]
    roe_year: list[float] = []
    for row in fin:
        qt, _, income = row
        bs = BSRepo.by_date(sid, qt)
        if bs and bs[-1] and int(bs[-1]) != 0:
            roe_year.append(round(int(income) / int(bs[-1]), 2))
    avg_roe = average(roe_year) if roe_year else 0
    if avg_roe > 0.08 and val_pbr < 2:
        return True, pbr[0][0]
    return False, "0"


@register("殖利率/PER", "fund", "殖利率 > 8% 且本益比 < 15")
def dividend_per(sid: str) -> tuple[bool, str]:
    rows = PBRRepo.latest(sid, 1)
    if not rows:
        return False, "0"
    _, dividend, per, _ = rows[0]
    if dividend > 8 and per < 15:
        return True, rows[0][0]
    return False, "0"


# --------------------------------------------------------------------------
# Technical strategies
# --------------------------------------------------------------------------

@register("均線策略", "tech", "5日均線 > 10日均線 且 當日漲幅 > 5%")
def macross(sid: str) -> tuple[bool, str]:
    rows = KBarRepo.latest(sid, 10)
    if len(rows) < 10:
        return False, "0"
    k = _kbar_asc(rows)
    sma5 = sma(k["close"], 5)
    sma10 = sma(k["close"], 10)
    ratio = _daily_ratio(k["spread"][-1], k["close"][-2])
    if sma5[-1] > sma10[-1] and ratio > 0.05:
        return True, k["date"][-1]
    return False, "0"


@register("KD指標", "tech", "K > D 且 過去3日中至少一日 D > 20 且 當日漲幅 > 3%")
def kd(sid: str) -> tuple[bool, str]:
    rows = KBarRepo.latest(sid, 15)
    if not rows:
        return False, "0"
    k = _kbar_asc(rows)
    K, D = stoch(k["high"], k["low"], k["close"], fastk_period=9)
    ratio = _daily_ratio(k["spread"][-1], k["close"][-2])
    if D[-1] > 20 and K[-1] > D[-1] and any(d > 20 for d in D[-3:]) and ratio > 0.03:
        return True, k["date"][-1]
    return False, "0"


def _bbands(sid: str, mode: str) -> tuple[bool, str]:
    rows = KBarRepo.latest(sid, 20)
    if len(rows) < 20:
        return False, "0"
    k = _kbar_asc(rows)
    ub, _, lb = bbands(k["close"], 20)
    close = k["close"][-1]
    if (mode == "l" and close < lb[-1]) or (mode == "u" and close > ub[-1]):
        return True, k["date"][-1]
    return False, "0"


@register("布林通道策略--上界", "tech", "收盤價突破布林通道上界")
def bb_upper(sid: str) -> tuple[bool, str]:
    return _bbands(sid, "u")


@register("布林通道策略--下界", "tech", "收盤價跌破布林通道下界")
def bb_lower(sid: str) -> tuple[bool, str]:
    return _bbands(sid, "l")


# --------------------------------------------------------------------------
# Chip strategies
# --------------------------------------------------------------------------

@register("外資買超", "chip", "外資單日買超突破 30 日布林上界 且 外資持股比 > 20%")
def foreign_overbuy(sid: str) -> tuple[bool, str]:
    ins = InstitutionRepo.latest(sid, 30)
    ratio_rows = ForeignInvRepo.latest(sid, 1)
    if len(ins) < 30 or not ratio_rows:
        return False, "0"
    ins_asc = ins[::-1]
    overbuy = array([float(r[1]) for r in ins_asc])
    ub, _, _ = bbands(overbuy, 30)
    _, ratio, _ = ratio_rows[0]
    if overbuy[-1] > ub[-1] and ratio > 20:
        return True, ratio_rows[0][0]
    return False, "0"
