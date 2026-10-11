"""Fetch IDX prices and fundamentals from Yahoo Finance. Kept in memory only."""

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Optional

import pandas as pd
import yfinance as yf

from analysis import analyze_frame, rank_rows
from universe import LQ45

TTL_SECONDS = 30 * 60
CODE_RE = re.compile(r"^[A-Z]{2,6}$")

_lock = threading.Lock()
_cache = {"at": 0.0, "frames": {}, "facts": {}}  # type: Dict[str, object]
_extra = {}  # type: Dict[str, object]

def normalize_code(code: str) -> str:
    cleaned = (code or "").strip().upper()
    if not CODE_RE.match(cleaned):
        raise ValueError("Kode saham tidak dikenali. Contoh: BBCA")
    return cleaned


def _extract(raw: pd.DataFrame, code: str) -> Optional[pd.DataFrame]:
    symbol = "{}.JK".format(code)
    if raw is None or raw.empty:
        return None

    frame = None
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = raw.columns.get_level_values(0)
        level1 = raw.columns.get_level_values(1)
        if symbol in level0:
            frame = raw[symbol]
        elif symbol in level1:
            frame = raw.xs(symbol, axis=1, level=1)
    else:
        frame = raw

    if frame is None or not isinstance(frame, pd.DataFrame) or "Close" not in frame.columns:
        return None

    close = frame["Close"].dropna()
    if close.empty:
        return None
    return frame.loc[close.index]


def _download(codes):
    symbols = ["{}.JK".format(code) for code in codes]
    raw = yf.download(
        symbols if len(symbols) > 1 else symbols[0],
        period="2y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    frames = {}
    for code in codes:
        frame = _extract(raw, code)
        if frame is not None:
            frames[code] = frame
    return frames


def _empty_facts() -> dict:
    return {
        "sector": None,
        "industry": None,
        "short_name": None,
        "trailing_pe": None,
        "price_to_book": None,
        "dividend_yield": None,
        "payout_ratio": None,
        "return_on_equity": None,
        "debt_to_equity": None,
        "profit_margins": None,
        "earnings_growth": None,
        "revenue_growth": None,
        "trailing_eps": None,
        "dividend_years": [],
    }


def _facts_for_code(code: str) -> dict:
    facts = _empty_facts()
    try:
        ticker = yf.Ticker("{}.JK".format(code))
        info = ticker.info or {}
        dividends = ticker.dividends
    except Exception:
        return facts

    facts["sector"] = info.get("sector")
    facts["industry"] = info.get("industry")
    facts["short_name"] = info.get("shortName")
    facts["trailing_pe"] = info.get("trailingPE")
    facts["price_to_book"] = info.get("priceToBook")
    facts["dividend_yield"] = info.get("dividendYield")
    facts["payout_ratio"] = info.get("payoutRatio")
    facts["return_on_equity"] = info.get("returnOnEquity")
    facts["debt_to_equity"] = info.get("debtToEquity")
    facts["profit_margins"] = info.get("profitMargins")
    facts["revenue_growth"] = info.get("revenueGrowth")
    facts["trailing_eps"] = info.get("trailingEps")
    growth = info.get("earningsGrowth")
    if growth is None:
        growth = info.get("earningsQuarterlyGrowth")
    facts["earnings_growth"] = growth

    if dividends is not None and len(dividends):
        first_year = datetime.now().year - 4
        facts["dividend_years"] = sorted({
            int(year) for year in dividends.index.year if int(year) >= first_year
        })
    return facts


def _fetch_facts(codes) -> Dict[str, dict]:
    found = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for code, facts in pool.map(lambda item: (item, _facts_for_code(item)), codes):
            found[code] = facts
    return found


def load_board(force: bool = False):
    now = time.time()
    with _lock:
        fresh = _cache["frames"] and now - _cache["at"] < TTL_SECONDS
        if fresh and not force:
            return _cache
        frames = _download(list(LQ45.keys()))
        if not frames:
            raise RuntimeError(
                "Yahoo Finance tidak mengembalikan harga. Coba lagi beberapa menit lagi."
            )
        facts = _fetch_facts(list(frames.keys()))
        _cache["frames"] = frames
        _cache["facts"] = facts
        _cache["at"] = time.time()
        return _cache


def load_one(code: str, force: bool = False):
    code = normalize_code(code)
    if code in LQ45:
        cached = load_board(force=force)
        frame = cached["frames"].get(code)
        if frame is None:
            raise LookupError("Harga {} tidak tersedia dari Yahoo Finance.".format(code))
        facts = cached["facts"].get(code) or _empty_facts()
        return frame, facts

    with _lock:
        cached = _extra.get(code)
        cached_at = _extra.get(code + ":at", 0)
        if cached is not None and not force and time.time() - cached_at < TTL_SECONDS:
            return cached["frame"], cached["facts"]

    frames = _download([code])
    frame = frames.get(code)
    if frame is None:
        raise LookupError("Kode {} tidak ketemu di Yahoo Finance.".format(code))
    facts = _facts_for_code(code)
    with _lock:
        _extra[code] = {"frame": frame, "facts": facts}
        _extra[code + ":at"] = time.time()
    return frame, facts


def summarize(cached):
    rows = []
    frames = cached["frames"]
    facts = cached["facts"]
    for code, name in LQ45.items():
        frame = frames.get(code)
        if frame is None:
            continue
        row = analyze_frame(code, name, frame, facts.get(code))
        if row is not None:
            rows.append(row)
    return rank_rows(rows)


def cached_at() -> float:
    return float(_cache["at"] or 0)
