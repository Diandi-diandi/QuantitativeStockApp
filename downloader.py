"""
FinMind download client.

One DataLoader instance is kept for the lifetime of the process, so we do
not re-authenticate on every dtype pull.

Each public method returns a tuple:
    (stock_ids_present: list[str], rows: list[tuple])
`stock_ids_present` is populated for full-market update pulls (no sid); when
sid is given it is empty. `rows` matches the column order in db.DATA_TABLES,
minus the leading stock_no.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

import requests
from FinMind.data import DataLoader


def check_connection(url: str = "https://api.finmindtrade.com/") -> bool:
    try:
        r = requests.get(url, timeout=5)
        return r.status_code < 500
    except requests.RequestException:
        return False


def _yyyymmdd_to_iso(s: str) -> str:
    return datetime.strptime(s, "%Y%m%d").strftime("%Y-%m-%d")


def _iso_to_yyyymmdd(s: str) -> str:
    return datetime.strptime(s, "%Y-%m-%d").strftime("%Y%m%d")


class FinmindClient:
    def __init__(self, api_key: str):
        self._api = DataLoader()
        self._api.login_by_token(api_key)

    # dispatch table: dtype -> (endpoint_name, transformer)
    def fetch(self, dtype: str, sid: str = "", start: str | None = None):
        handler = _HANDLERS.get(dtype)
        if handler is None:
            raise ValueError(f"unknown dtype: {dtype}")
        endpoint_name, transformer = handler
        endpoint: Callable = getattr(self._api, endpoint_name)

        if dtype == "stockno":
            df = endpoint()
        else:
            iso_start = _yyyymmdd_to_iso(start or datetime.today().strftime("%Y%m%d"))
            df = endpoint(stock_id=sid, start_date=iso_start) if sid \
                else endpoint(start_date=iso_start)

        if df is None or df.empty:
            return [], []
        return transformer(df.values.tolist(), update=(sid == "" and dtype != "stockno"))


# ---------- transformers ----------

def _transform_stockno(data, update):
    keep = []
    for x in data:
        if x[3] != "twse":
            continue
        cat = x[0]
        if cat in ("Index", "大盤"):
            kind = "indexes"
        elif cat == "ETF":
            kind = "etf"
        elif cat in ("受益證券",):
            continue
        else:
            kind = "stock"
        keep.append((x[1], x[2], kind))
    # dedupe preserving order
    seen: set[tuple] = set()
    out: list[tuple] = []
    for row in keep:
        if row not in seen:
            seen.add(row)
            out.append(row)
    return [], out


def _transform_kbar(data, update):
    sids, rows = [], []
    for x in data:
        # [date, stock_id, volume, money, open, max, min, close, spread, turnover]
        sid = x[1]
        date = _iso_to_yyyymmdd(x[0])
        rows.append((date, x[2], x[3], x[4], x[5], x[6], x[7], x[8], x[9]))
        if update:
            sids.append(sid)
    return sids, rows


def _transform_revenue(data, update):
    sids, rows = [], []
    for x in data:
        # [date, stock_id, country, revenue, revenue_month, revenue_year]
        date = f"{x[5]}{str(x[4]).zfill(2)}"
        rows.append((date, x[3]))
        if update:
            sids.append(x[1])
    return sids, rows


def _transform_pbr(data, update):
    sids, rows = [], []
    for x in data:
        # [date, stock_id, dividend_yield, PER, PBR]
        date = _iso_to_yyyymmdd(x[0])
        rows.append((date, x[2], x[3], x[4]))
        if update:
            sids.append(x[1])
    return sids, rows


def _transform_foreign_inv(data, update):
    sids, rows = [], []
    for x in data:
        # [date, stock_id, ..., ForeignInvestmentSharesRatio (7), ..., NumberOfSharesIssued (-3)]
        date = _iso_to_yyyymmdd(x[0])
        rows.append((date, x[7], x[-3]))
        if update:
            sids.append(x[1])
    return sids, rows


def _transform_institution(data, update):
    # rows: [date, stock_id, buy, name, sell]
    key_idx = 1 if update else 0
    keys = sorted({x[key_idx] for x in data})
    sids, rows = [], []
    for k in keys:
        info = [x for x in data if x[key_idx] == k]
        foreign_inv = sum(
            int(x[2]) - int(x[4]) for x in info
            if x[3] in ("Foreign_Investor", "Foreign_Dealer_Self")
        )
        inv_trust_list = [int(x[2]) - int(x[4]) for x in info if x[3] == "Investment_Trust"]
        inv_trust = inv_trust_list[0] if inv_trust_list else 0
        dealer = sum(
            int(x[2]) - int(x[4]) for x in info
            if x[3] in ("Dealer_self", "Dealer_Hedging")
        )
        date = _iso_to_yyyymmdd(info[0][0])
        rows.append((date, foreign_inv, inv_trust, dealer))
        if update:
            sids.append(k)
    return sids, rows


def _transform_fin_stat(data, update):
    # rows: [date, stock_id, type, value, origin_name]
    key_idx = 1 if update else 0
    keys = sorted({x[key_idx] for x in data})
    sids, rows = [], []
    for k in keys:
        info = [x for x in data if x[key_idx] == k]
        types = {x[2]: x[3] for x in info}
        income = types.get("IncomeAfterTaxes", types.get("IncomeAfterTax", 0))
        eps = types.get("EPS", 0)
        date = _iso_to_yyyymmdd(info[0][0])
        rows.append((date, eps, int(income) if income is not None else 0))
        if update:
            sids.append(k)
    return sids, rows


def _transform_bs(data, update):
    key_idx = 1 if update else 0
    keys = sorted({x[key_idx] for x in data})
    sids, rows = [], []
    for k in keys:
        info = [x for x in data if x[key_idx] == k]
        types = {x[2]: x[3] for x in info}
        equity = int(types.get("Equity", 0))
        date = _iso_to_yyyymmdd(info[0][0])
        rows.append((date, equity))
        if update:
            sids.append(k)
    return sids, rows


_HANDLERS: dict[str, tuple[str, Callable]] = {
    "stockno":     ("taiwan_stock_info",                    _transform_stockno),
    "kbar":        ("taiwan_stock_daily",                   _transform_kbar),
    "revenue":     ("taiwan_stock_month_revenue",           _transform_revenue),
    "institution": ("taiwan_stock_institutional_investors", _transform_institution),
    "pbr":         ("taiwan_stock_per_pbr",                 _transform_pbr),
    "foreign_inv": ("taiwan_stock_shareholding",            _transform_foreign_inv),
    "fin_stat":    ("taiwan_stock_financial_statement",     _transform_fin_stat),
    "bs":          ("taiwan_stock_balance_sheet",           _transform_bs),
}
