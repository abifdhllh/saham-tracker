"""Personal score for Indonesian stocks: business quality plus price trend."""

import math
from typing import List, Optional

import pandas as pd

FUND_WEIGHT = 0.55
TECH_WEIGHT = 0.45
BANKS = {"BBCA", "BBNI", "BBRI", "BBTN", "BMRI"}


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period, min_periods=period).mean()
    avg_loss = loss.rolling(period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, math.inf)
    return 100 - (100 / (1 + rs))


def _num(value, digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
        if pd.isna(number) or math.isinf(number):
            return None
    except (TypeError, ValueError):
        return None
    return round(number, digits)


def _pct(latest: float, past: float) -> Optional[float]:
    if past is None or past == 0 or pd.isna(past):
        return None
    return _num((latest - past) / past * 100, 2)


def _id(value, digits: int = 1) -> str:
    if value is None:
        return "–"
    return ("{:." + str(digits) + "f}").format(value).replace(".", ",")


def _part(label: str, points: float, maximum: int, note: str) -> dict:
    return {
        "label": label,
        "points": int(round(points)),
        "max": maximum,
        "note": note,
    }


def _score(parts: List[dict]) -> int:
    maximum = sum(part["max"] for part in parts)
    if maximum <= 0:
        return 0
    earned = sum(part["points"] for part in parts)
    return int(round(earned / maximum * 100))


def grade_for(total: int) -> dict:
    if total >= 70:
        return {"grade": "sesuai", "label": "Paling sesuai"}
    if total >= 55:
        return {"grade": "cukup", "label": "Cukup layak"}
    return {"grade": "kurang", "label": "Kurang sesuai"}


def _is_bank(code: str, facts: dict) -> bool:
    if code in BANKS:
        return True
    industry = (facts.get("industry") or "").lower()
    return "bank" in industry


def _debt_ratio(raw) -> Optional[float]:
    value = _num(raw, 4)
    if value is None or value < 0 or value > 1000:
        return None
    if value >= 1:
        return value / 100.0
    return value


def _usable_pbv(raw) -> Optional[float]:
    value = _num(raw, 2)
    if value is None or value <= 0 or value > 80:
        return None
    return value


def score_technical(price, ma50, ma200, rsi_now, drawdown) -> List[dict]:
    parts = []
    if ma200 is None or price is None:
        return [_part("Tren harga", 0, 100, "Riwayat belum cukup untuk rata-rata 200 hari.")]

    dist = (price - ma200) / ma200 * 100
    if 0 <= dist <= 12:
        trend_points, trend_note = 30, "Harga {}% di atas rata-rata 200 hari, belum terlalu jauh.".format(_id(dist))
    elif dist <= 20:
        trend_points, trend_note = 20, "Harga {}% di atas rata-rata 200 hari. Mulai jauh.".format(_id(dist))
    elif dist > 20:
        trend_points, trend_note = 12, "Harga {}% di atas rata-rata 200 hari. Sudah mahal untuk dikejar.".format(_id(dist))
    elif dist >= -8:
        trend_points, trend_note = 14, "Harga {}% di bawah rata-rata 200 hari. Tren baru melemah.".format(_id(abs(dist)))
    else:
        trend_points, trend_note = 4, "Harga {}% di bawah rata-rata 200 hari.".format(_id(abs(dist)))
    parts.append(_part("Tren 200 hari", trend_points, 30, trend_note))

    if ma50 is None:
        parts.append(_part("Arah rata-rata", 0, 15, "Rata-rata 50 hari belum tersedia."))
        parts.append(_part("Harga terhadap 50 hari", 0, 15, "Rata-rata 50 hari belum tersedia."))
    else:
        if ma50 > ma200:
            parts.append(_part("Arah rata-rata", 15, 15, "Rata-rata 50 hari masih di atas rata-rata 200 hari."))
        else:
            parts.append(_part("Arah rata-rata", 4, 15, "Rata-rata 50 hari sudah di bawah rata-rata 200 hari."))
        if price > ma50:
            parts.append(_part("Harga terhadap 50 hari", 15, 15, "Harga masih di atas rata-rata 50 hari."))
        else:
            parts.append(_part("Harga terhadap 50 hari", 4, 15, "Harga sudah di bawah rata-rata 50 hari."))

    if rsi_now is None:
        parts.append(_part("RSI", 0, 25, "RSI belum bisa dihitung."))
    elif 40 <= rsi_now <= 60:
        parts.append(_part("RSI", 25, 25, "RSI {}: zona netral, masih ada ruang.".format(_id(rsi_now, 0))))
    elif 30 <= rsi_now < 40 or 60 < rsi_now <= 68:
        parts.append(_part("RSI", 16, 25, "RSI {}: agak condong ke satu sisi.".format(_id(rsi_now, 0))))
    elif rsi_now > 75:
        parts.append(_part("RSI", 4, 25, "RSI {}: sedang panas.".format(_id(rsi_now, 0))))
    elif rsi_now > 68:
        parts.append(_part("RSI", 8, 25, "RSI {}: mulai panas.".format(_id(rsi_now, 0))))
    else:
        parts.append(_part("RSI", 10, 25, "RSI {}: sedang lemah. Bukan perintah beli.".format(_id(rsi_now, 0))))

    if drawdown is None:
        parts.append(_part("Jarak dari puncak", 0, 15, "Puncak satu tahun belum tersedia."))
    elif drawdown >= -10:
        parts.append(_part("Jarak dari puncak", 15, 15, "Harga {}% dari puncak satu tahun.".format(_id(drawdown))))
    elif drawdown >= -20:
        parts.append(_part("Jarak dari puncak", 10, 15, "Harga {}% dari puncak satu tahun.".format(_id(drawdown))))
    elif drawdown >= -35:
        parts.append(_part("Jarak dari puncak", 6, 15, "Harga {}% dari puncak satu tahun.".format(_id(drawdown))))
    else:
        parts.append(_part("Jarak dari puncak", 2, 15, "Harga {}% dari puncak satu tahun.".format(_id(drawdown))))
    return parts


def score_fundamental(code: str, facts: Optional[dict]) -> List[dict]:
    facts = facts or {}
    bank = _is_bank(code, facts)
    eps = _num(facts.get("trailing_eps"), 2)
    margin = _num(facts.get("profit_margins"), 4)
    roe = _num(facts.get("return_on_equity"), 4)
    earn_g = _num(facts.get("earnings_growth"), 4)
    rev_g = _num(facts.get("revenue_growth"), 4)
    div_yield = _num(facts.get("dividend_yield"), 2)
    payout = _num(facts.get("payout_ratio"), 3)
    pe = _num(facts.get("trailing_pe"), 2)
    pbv = _usable_pbv(facts.get("price_to_book"))
    debt = None if bank else _debt_ratio(facts.get("debt_to_equity"))
    years = facts.get("dividend_years") or []
    year_count = len(years)

    parts = []

    if eps is None and margin is None:
        parts.append(_part("Laba", 0, 20, "Laba tidak tersedia dari sumber data."))
    elif (eps is not None and eps > 0) or (margin is not None and margin > 0.02):
        parts.append(_part("Laba", 20, 20, "Perusahaan sedang mencetak laba."))
    elif eps is not None and eps > 0:
        parts.append(_part("Laba", 14, 20, "Laba per saham positif."))
    else:
        parts.append(_part("Laba", 0, 20, "Laba masih negatif atau tipis."))

    if roe is None:
        parts.append(_part("Imbal ekuitas", 0, 20, "ROE tidak tersedia."))
    elif roe > 0.8 and (pbv or 0) >= 8:
        parts.append(_part(
            "Imbal ekuitas",
            8,
            20,
            "ROE {}% terlihat tinggi karena ekuitasnya kecil. Jangan dibaca mentah.".format(_id(roe * 100)),
        ))
    elif roe >= 0.15:
        parts.append(_part("Imbal ekuitas", 20, 20, "ROE {}%. Modal bekerja dengan baik.".format(_id(roe * 100))))
    elif roe >= 0.10:
        parts.append(_part("Imbal ekuitas", 14, 20, "ROE {}%.".format(_id(roe * 100))))
    elif roe > 0:
        parts.append(_part("Imbal ekuitas", 6, 20, "ROE {}%, masih tipis.".format(_id(roe * 100))))
    else:
        parts.append(_part("Imbal ekuitas", 0, 20, "ROE {}%.".format(_id(roe * 100))))

    if earn_g is None:
        parts.append(_part("Pertumbuhan laba", 0, 15, "Pertumbuhan laba tidak tersedia."))
    elif earn_g >= 0.5:
        parts.append(_part(
            "Pertumbuhan laba",
            12,
            15,
            "Laba naik {}%. Kenaikan sebesar ini sering tidak berulang.".format(_id(earn_g * 100, 0)),
        ))
    elif earn_g > 0.05:
        parts.append(_part("Pertumbuhan laba", 15, 15, "Laba naik {}%.".format(_id(earn_g * 100, 0))))
    elif earn_g > 0:
        parts.append(_part("Pertumbuhan laba", 10, 15, "Laba naik {}%.".format(_id(earn_g * 100, 0))))
    elif earn_g > -0.1:
        parts.append(_part("Pertumbuhan laba", 5, 15, "Laba turun {}%.".format(_id(abs(earn_g) * 100, 0))))
    else:
        parts.append(_part("Pertumbuhan laba", 0, 15, "Laba turun {}%.".format(_id(abs(earn_g) * 100, 0))))

    if rev_g is None:
        parts.append(_part("Pertumbuhan pendapatan", 0, 10, "Pertumbuhan pendapatan tidak tersedia."))
    elif rev_g > 0.05:
        parts.append(_part("Pertumbuhan pendapatan", 10, 10, "Pendapatan naik {}%.".format(_id(rev_g * 100, 0))))
    elif rev_g > 0:
        parts.append(_part("Pertumbuhan pendapatan", 7, 10, "Pendapatan naik {}%.".format(_id(rev_g * 100, 0))))
    else:
        parts.append(_part("Pertumbuhan pendapatan", 2, 10, "Pendapatan turun {}%.".format(_id(abs(rev_g) * 100, 0))))

    if year_count >= 4:
        parts.append(_part("Riwayat dividen", 12, 12, "Dividen tercatat di {} dari 5 tahun terakhir.".format(year_count)))
    elif year_count >= 2:
        parts.append(_part("Riwayat dividen", 7, 12, "Dividen tercatat di {} dari 5 tahun terakhir.".format(year_count)))
    elif year_count == 1:
        parts.append(_part("Riwayat dividen", 3, 12, "Dividen baru tercatat di 1 dari 5 tahun terakhir."))
    else:
        parts.append(_part("Riwayat dividen", 0, 12, "Tidak ada dividen tercatat dalam 5 tahun terakhir."))

    if div_yield is None:
        parts.append(_part("Imbal dividen", 0, 13, "Imbal dividen tidak tersedia."))
    elif div_yield <= 0:
        parts.append(_part("Imbal dividen", 0, 13, "Tidak ada dividen berjalan."))
    elif payout is not None and payout > 1:
        parts.append(_part(
            "Imbal dividen",
            4,
            13,
            "Imbal dividen {}%, tetapi pembayaran {}% dari laba. Sulit dipertahankan.".format(
                _id(div_yield), _id(payout * 100, 0)
            ),
        ))
    elif 2 <= div_yield <= 9:
        parts.append(_part("Imbal dividen", 13, 13, "Imbal dividen {}%, masuk akal untuk pendapatan pasif.".format(_id(div_yield))))
    elif div_yield < 2:
        parts.append(_part("Imbal dividen", 6, 13, "Imbal dividen {}%, kecil untuk tujuan pasif.".format(_id(div_yield))))
    else:
        parts.append(_part("Imbal dividen", 7, 13, "Imbal dividen {}%. Sangat tinggi, cek apakah laba sedang turun.".format(_id(div_yield))))

    if pe is None or pe <= 0:
        parts.append(_part("Valuasi laba", 0, 15, "PER tidak tersedia atau laba negatif."))
    elif pe <= 12:
        parts.append(_part("Valuasi laba", 15, 15, "PER {} kali.".format(_id(pe))))
    elif pe <= 20:
        parts.append(_part("Valuasi laba", 12, 15, "PER {} kali.".format(_id(pe))))
    elif pe <= 30:
        parts.append(_part("Valuasi laba", 7, 15, "PER {} kali, sudah tidak murah.".format(_id(pe))))
    else:
        parts.append(_part("Valuasi laba", 2, 15, "PER {} kali, mahal terhadap laba saat ini.".format(_id(pe))))

    raw_pbv = _num(facts.get("price_to_book"), 2)
    if pbv is None:
        note = "PBV tidak dipakai."
        if raw_pbv is not None and (raw_pbv <= 0 or raw_pbv > 80):
            note = "PBV {} tidak masuk akal, jadi diabaikan.".format(_id(raw_pbv, 0))
        elif raw_pbv is None:
            note = "PBV tidak tersedia."
        parts.append(_part("Harga terhadap buku", 0, 10, note))
    elif bank:
        if pbv <= 3.2:
            parts.append(_part("Harga terhadap buku", 10, 10, "PBV {} kali. Wajar untuk bank.".format(_id(pbv))))
        elif pbv <= 5:
            parts.append(_part("Harga terhadap buku", 7, 10, "PBV {} kali. Bank berkualitas sering di harga ini.".format(_id(pbv))))
        else:
            parts.append(_part("Harga terhadap buku", 3, 10, "PBV {} kali, mahal untuk bank.".format(_id(pbv))))
    elif pbv <= 1.5:
        parts.append(_part("Harga terhadap buku", 10, 10, "PBV {} kali.".format(_id(pbv))))
    elif pbv <= 3:
        parts.append(_part("Harga terhadap buku", 7, 10, "PBV {} kali.".format(_id(pbv))))
    elif pbv <= 8:
        parts.append(_part("Harga terhadap buku", 4, 10, "PBV {} kali, sudah premium.".format(_id(pbv))))
    else:
        parts.append(_part("Harga terhadap buku", 2, 10, "PBV {} kali, sangat mahal terhadap buku.".format(_id(pbv))))

    if bank:
        pass
    elif debt is None:
        parts.append(_part("Utang", 0, 10, "Rasio utang tidak tersedia."))
    elif debt < 0.8:
        parts.append(_part("Utang", 10, 10, "Utang {} kali ekuitas.".format(_id(debt, 2))))
    elif debt < 1.5:
        parts.append(_part("Utang", 6, 10, "Utang {} kali ekuitas.".format(_id(debt, 2))))
    elif debt < 3:
        parts.append(_part("Utang", 3, 10, "Utang {} kali ekuitas, sudah berat.".format(_id(debt, 2))))
    else:
        parts.append(_part("Utang", 0, 10, "Utang {} kali ekuitas.".format(_id(debt, 2))))

    return parts


def trend_status(dist200: Optional[float], rsi_now: Optional[float]) -> dict:
    if dist200 is None:
        return {"status": "tinjau", "label": "Tren belum terbaca"}
    if dist200 > 0 and dist200 <= 15 and (rsi_now is None or rsi_now < 70):
        return {"status": "akumulasi", "label": "Tren naik"}
    if dist200 > 0:
        return {"status": "tunggu", "label": "Harga sudah jauh"}
    return {"status": "tinjau", "label": "Di bawah tren"}


def analyze_frame(code: str, name: str, frame: pd.DataFrame, facts: Optional[dict] = None) -> Optional[dict]:
    if frame is None or frame.empty or "Close" not in frame.columns:
        return None

    close = frame["Close"].dropna()
    if len(close) < 30:
        return None

    ma50_series = close.rolling(50).mean()
    ma200_series = close.rolling(200).mean()
    rsi_series = rsi(close)

    price = float(close.iloc[-1])
    ma50 = _num(ma50_series.iloc[-1], 2)
    ma200 = _num(ma200_series.iloc[-1], 2)
    rsi_now = _num(rsi_series.iloc[-1], 1)
    window = close.iloc[-252:]
    high_52 = float(window.max()) if len(window) else None
    drawdown = _pct(price, high_52) if high_52 else None
    dist200 = _num((price - ma200) / ma200 * 100, 2) if ma200 else None

    technical_parts = score_technical(price, ma50, ma200, rsi_now, drawdown)
    fundamental_parts = score_fundamental(code, facts)
    technical_score = _score(technical_parts)
    fundamental_score = _score(fundamental_parts)
    facts = facts or {}
    swing = swing_plan(frame.reindex(close.index), close, price, rsi_now)
    invest_total = int(round(technical_score * TECH_WEIGHT + fundamental_score * FUND_WEIGHT))
    invest_grade = grade_for(invest_total)
    chart_close = close.iloc[-126:]
    invest_summary = (
        "Untuk dipegang sekitar 1–6 bulan. Skor {} dari 100: fundamental {} (laba, dividen, valuasi, utang) "
        "dan teknikal {} (tren 50 dan 200 hari). Tinjau lagi tiap laporan kuartal, atau kalau harga jatuh jauh dari rata-rata 200 hari."
    ).format(invest_total, fundamental_score, technical_score)

    def points(series: pd.Series):
        return [_num(value, 2) for value in series.tolist()]

    return {
        "code": code,
        "name": name,
        "industry": facts.get("industry"),
        "price": _num(price, 2),
        "change_pct": _pct(price, float(close.iloc[-2]) if len(close) > 1 else None),
        "week_pct": _pct(price, float(close.iloc[-6]) if len(close) > 5 else None),
        "month_pct": _pct(price, float(close.iloc[-22]) if len(close) > 21 else None),
        "ma50": ma50,
        "ma200": ma200,
        "dist200": dist200,
        "drawdown": drawdown,
        "rsi": rsi_now,
        "pe": _num(facts.get("trailing_pe"), 1) if _num(facts.get("trailing_pe"), 1) and _num(facts.get("trailing_pe"), 1) > 0 else None,
        "pbv": _usable_pbv(facts.get("price_to_book")),
        "roe": _num((facts.get("return_on_equity") or 0) * 100, 1) if facts.get("return_on_equity") is not None else None,
        "dividend_yield": _num(facts.get("dividend_yield"), 2) if facts.get("dividend_yield") not in (None, 0) else None,
        "payout": _num((facts.get("payout_ratio") or 0) * 100, 0) if facts.get("payout_ratio") is not None else None,
        "earnings_growth": _num((facts.get("earnings_growth") or 0) * 100, 1) if facts.get("earnings_growth") is not None else None,
        "revenue_growth": _num((facts.get("revenue_growth") or 0) * 100, 1) if facts.get("revenue_growth") is not None else None,
        "debt_ratio": None if _is_bank(code, facts) else _num(_debt_ratio(facts.get("debt_to_equity")), 2),
        "dividend_years": len(facts.get("dividend_years") or []),
        "as_of": pd.Timestamp(close.index[-1]).strftime("%Y-%m-%d"),
        "technical_score": technical_score,
        "fundamental_score": fundamental_score,
        "total_score": swing["swing_score"],
        "grade": swing["grade"],
        "label": swing["label"],
        "summary": swing["summary"],
        "trading": {
            "grade": swing["grade"],
            "label": swing["label"],
            "summary": swing["summary"],
            "score": swing["swing_score"],
        },
        "invest": {
            "grade": invest_grade["grade"],
            "label": invest_grade["label"],
            "summary": invest_summary,
            "score": invest_total,
            "fundamental": fundamental_score,
            "technical": technical_score,
        },
        "ma20": swing["ma20"],
        "dist_ma20": swing["dist_ma20"],
        "stop": swing["stop"],
        "target": swing["target"],
        "risk_pct": swing["risk_pct"],
        "reward_pct": swing["reward_pct"],
        "risk_per_lot": swing["risk_per_lot"],
        "reward_per_lot": swing["reward_per_lot"],
        "avg_value": swing["avg_value"],
        "technical_parts": technical_parts,
        "fundamental_parts": fundamental_parts,
        "swing_parts": swing["swing_parts"],
        "chart": {
            "dates": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in chart_close.index],
            "close": points(chart_close),
            "ma20": points(swing["ma20_series"].reindex(chart_close.index)),
            "ma50": points(swing["ma50_series"].reindex(chart_close.index)),
            "ma200": points(ma200_series.reindex(chart_close.index)),
        },
    }


def _idr_words(value: Optional[float]) -> str:
    if value is None:
        return "tidak tersedia"
    if value >= 1_000_000_000_000:
        return "Rp {} triliun".format(_id(value / 1_000_000_000_000, 1))
    if value >= 1_000_000_000:
        return "Rp {} miliar".format(_id(value / 1_000_000_000, 1))
    if value >= 1_000_000:
        return "Rp {} juta".format(_id(value / 1_000_000, 1))
    return "Rp {}".format(_id(value, 0))


def swing_plan(frame: pd.DataFrame, close: pd.Series, price: float, rsi_now: Optional[float]) -> dict:
    """Daily swing setup: a few days to about four weeks, decided after the close."""
    aligned = frame.reindex(close.index)
    high = aligned["High"] if "High" in aligned.columns else close
    low = aligned["Low"] if "Low" in aligned.columns else close
    volume = aligned["Volume"] if "Volume" in aligned.columns else None

    ma20_series = close.rolling(20).mean()
    ma50_series = close.rolling(50).mean()
    ma20 = _num(ma20_series.iloc[-1], 2)
    ma50 = _num(ma50_series.iloc[-1], 2)
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr_now = _num(true_range.rolling(14).mean().iloc[-1], 2)
    swing_low = _num(low.iloc[-10:].min(), 2) if len(low) >= 10 else None

    avg_value = None
    if volume is not None:
        traded = (close * volume).iloc[-20:].dropna()
        if len(traded):
            avg_value = float(traded.mean())

    stop_candidates = []
    if swing_low is not None and swing_low < price:
        stop_candidates.append(swing_low)
    if atr_now is not None:
        stop_candidates.append(price - 1.5 * atr_now)
    stop = min(stop_candidates) if stop_candidates else None
    risk_pct = _num((price - stop) / price * 100, 2) if stop and price else None
    target = None
    reward_pct = None
    if stop is not None and price > stop:
        target = _num(price + 2 * (price - stop), 2)
        reward_pct = _pct(target, price)

    dist_ma20 = _num((price - ma20) / ma20 * 100, 2) if ma20 else None
    uptrend = bool(ma20 and ma50 and price > ma20 and ma20 > ma50)
    liquid = avg_value is not None and avg_value >= 5_000_000_000
    pullback = dist_ma20 is not None and -1 <= dist_ma20 <= 4
    extended = dist_ma20 is not None and dist_ma20 > 6
    rsi_ok = rsi_now is not None and 40 <= rsi_now <= 62
    rsi_hot = rsi_now is not None and rsi_now >= 68
    risk_ok = risk_pct is not None and 3 <= risk_pct <= 8

    parts = []
    if uptrend:
        parts.append(_part("Tren pendek", 40, 40, "Harga di atas rata-rata 20 hari, dan rata-rata 20 hari di atas 50 hari."))
    else:
        parts.append(_part("Tren pendek", 0, 40, "Tren beberapa minggu belum naik. Setup beli dilewati."))
    if pullback:
        parts.append(_part("Jarak ke rata-rata 20 hari", 25, 25, "Harga {}% dari rata-rata 20 hari, masih dekat untuk dibeli.".format(_id(dist_ma20))))
    elif extended:
        parts.append(_part("Jarak ke rata-rata 20 hari", 4, 25, "Harga {}% di atas rata-rata 20 hari. Mengejar di sini sering telat.".format(_id(dist_ma20))))
    elif dist_ma20 is not None:
        parts.append(_part("Jarak ke rata-rata 20 hari", 10, 25, "Harga {}% dari rata-rata 20 hari.".format(_id(dist_ma20))))
    else:
        parts.append(_part("Jarak ke rata-rata 20 hari", 0, 25, "Rata-rata 20 hari belum tersedia."))
    if rsi_ok:
        parts.append(_part("RSI", 15, 15, "RSI {}: masih ada ruang, belum panas.".format(_id(rsi_now, 0))))
    elif rsi_hot:
        parts.append(_part("RSI", 2, 15, "RSI {}: sedang panas untuk beli baru.".format(_id(rsi_now, 0))))
    elif rsi_now is None:
        parts.append(_part("RSI", 0, 15, "RSI belum bisa dihitung."))
    else:
        parts.append(_part("RSI", 8, 15, "RSI {}.".format(_id(rsi_now, 0))))
    if liquid:
        parts.append(_part("Likuiditas", 20, 20, "Nilai transaksi harian rata-rata {}. Masih mudah dijual.".format(_idr_words(avg_value))))
    elif avg_value is not None and avg_value >= 1_000_000_000:
        parts.append(_part("Likuiditas", 8, 20, "Nilai transaksi harian rata-rata {}. Cukup untuk posisi kecil.".format(_idr_words(avg_value))))
    else:
        parts.append(_part("Likuiditas", 0, 20, "Nilai transaksi harian rata-rata {}. Terlalu sepi untuk keluar dengan cepat.".format(_idr_words(avg_value))))

    if uptrend and pullback and rsi_ok and liquid and risk_ok:
        grade, label = "sesuai", "Siap dibeli"
        summary = (
            "Setup ayunan siap dicek. Beli di dekat harga tutup ini, batas rugi sudah ditentukan, "
            "targetnya dua kali jarak batas itu. Perkiraan dipegang beberapa hari sampai empat minggu. "
            "Kalau harga penutupan jatuh di bawah batas rugi, ide ini batal."
        )
    elif uptrend and (extended or rsi_hot or (risk_pct is not None and risk_pct < 3)):
        grade, label = "cukup", "Tunggu harga mendingin"
        summary = (
            "Tren pendek masih naik, tetapi harga sudah jauh, RSI panas, atau batas ruginya terlalu rapat untuk biaya transaksi. "
            "Tunggu harga kembali mendekati rata-rata 20 hari."
        )
    elif uptrend and not liquid:
        grade, label = "kurang", "Lewati, transaksi sepi"
        summary = "Trennya naik, tetapi nilai transaksi harian terlalu kecil. Profit di layar sulit diambil karena susah dijual."
    else:
        grade, label = "kurang", "Lewati"
        summary = "Belum ada setup beli untuk jangka beberapa hari sampai beberapa minggu. Melewatkan juga keputusan."

    if risk_ok and stop is not None and target is not None:
        parts.append(_part(
            "Batas rugi dan target",
            15,
            15,
            "Batas rugi {} ({}%). Target {} ({}%). Satu target kena menutup dua batas rugi.".format(
                _id(stop, 0), _id(risk_pct), _id(target, 0), _id(reward_pct)
            ),
        ))
    elif risk_pct is not None and risk_pct < 3:
        parts.append(_part("Batas rugi dan target", 4, 15, "Jarak batas rugi hanya {}%. Di saham Indonesia ini mudah tersentuh biaya dan noise.".format(_id(risk_pct))))
    elif risk_pct is not None:
        parts.append(_part("Batas rugi dan target", 6, 15, "Jarak batas rugi {}%. Lebar, jadi ukuran posisi harus kecil.".format(_id(risk_pct))))
    else:
        parts.append(_part("Batas rugi dan target", 0, 15, "Batas rugi belum bisa dihitung."))

    score = _score(parts)
    return {
        "ma20": ma20,
        "dist_ma20": dist_ma20,
        "stop": _num(stop, 2),
        "target": target,
        "risk_pct": risk_pct,
        "reward_pct": reward_pct,
        "risk_per_lot": _num((price - stop) * 100, 0) if stop is not None else None,
        "reward_per_lot": _num((target - price) * 100, 0) if target is not None else None,
        "avg_value": _num(avg_value, 0) if avg_value is not None else None,
        "swing_score": score,
        "grade": grade,
        "label": label,
        "summary": summary,
        "swing_parts": parts,
        "ma20_series": ma20_series,
        "ma50_series": ma50_series,
    }


def rank_rows(rows: List[dict]) -> List[dict]:
    order = {"sesuai": 0, "cukup": 1, "kurang": 2}
    trading = sorted(
        rows,
        key=lambda row: (order.get(row["trading"]["grade"], 9), -row["trading"]["score"], row["code"]),
    )
    for index, row in enumerate(trading, start=1):
        row["trading"]["rank"] = index
        row["rank"] = index
    invest = sorted(
        rows,
        key=lambda row: (-row["invest"]["score"], -row["invest"]["fundamental"], row["code"]),
    )
    for index, row in enumerate(invest, start=1):
        row["invest"]["rank"] = index
    return trading
