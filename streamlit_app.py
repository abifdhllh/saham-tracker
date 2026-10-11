"""Streamlit view of the same LQ45 scores used by the local server."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from analysis import analyze_frame
from market import cached_at, load_board, load_one, normalize_code, summarize
from universe import LQ45, LQ45_PERIOD

st.set_page_config(page_title="Saham Indonesia", layout="wide")


def rupiah(value):
    if value is None:
        return "–"
    return "Rp {:,.0f}".format(value).replace(",", ".")


def signed(value, suffix="%"):
    if value is None:
        return "–"
    text = "{:.1f}".format(value).replace(".", ",")
    if value > 0:
        text = "+" + text
    return text + suffix


def plain(value, suffix=""):
    if value is None:
        return "–"
    return "{:.1f}".format(value).replace(".", ",") + suffix


def company_name(code, facts):
    if code in LQ45:
        return LQ45[code]
    return (facts or {}).get("short_name") or code


def load_rows(force):
    return summarize(load_board(force=force))


def view_of(row, mode):
    return row["invest"] if mode == "invest" else row["trading"]


def board_frame(rows, mode):
    records = []
    for row in rows:
        view = view_of(row, mode)
        shared = {
            "Peringkat": view["rank"],
            "Kode": row["code"],
            "Nama": row["name"],
            "Catatan": view["label"],
            "Harga": rupiah(row["price"]),
            "Perubahan": signed(row["change_pct"]),
        }
        if mode == "invest":
            shared.update({
                "Skor": view["score"],
                "Fundamental": view["fundamental"],
                "Teknikal": view["technical"],
                "Dividen": plain(row["dividend_yield"], "%"),
                "PER": plain(row["pe"], "×"),
                "ROE": plain(row["roe"], "%"),
            })
        else:
            shared.update({
                "Batas rugi": rupiah(row["stop"]),
                "Target": rupiah(row["target"]),
                "Risiko": plain(row["risk_pct"], "%"),
                "Risiko per lot": rupiah(row["risk_per_lot"]),
                "Transaksi harian": rupiah(row["avg_value"]),
            })
        records.append(shared)
    frame = pd.DataFrame(records)
    return frame.sort_values("Peringkat")


def show_parts(title, parts):
    if not parts:
        return
    st.subheader(title)
    st.dataframe(
        pd.DataFrame([{
            "Bagian": part["label"],
            "Nilai": "{}/{}".format(part["points"], part["max"]),
            "Catatan": part["note"],
        } for part in parts]),
        hide_index=True,
        use_container_width=True,
    )


def show_chart(row, mode):
    chart = row.get("chart") or {}
    if not chart.get("dates"):
        return
    if mode == "invest":
        columns = {"Harga": chart["close"], "Rata-rata 50 hari": chart["ma50"], "Rata-rata 200 hari": chart["ma200"]}
    else:
        columns = {"Harga": chart["close"], "Rata-rata 20 hari": chart["ma20"], "Rata-rata 50 hari": chart["ma50"]}
    frame = pd.DataFrame(columns, index=pd.to_datetime(chart["dates"]))
    st.line_chart(frame, height=280)


def show_detail(row, mode):
    view = view_of(row, mode)
    rank = view.get("rank")
    st.subheader("{} · {}".format(row["code"], row["name"]))
    st.caption("{}{} · harga per {}".format(
        "Peringkat {}. ".format(rank) if rank else "",
        view["label"],
        row["as_of"],
    ))
    st.write(view["summary"])
    if mode == "invest":
        cols = st.columns(4)
        cols[0].metric("Skor", view["score"])
        cols[1].metric("Fundamental", view["fundamental"])
        cols[2].metric("Teknikal", view["technical"])
        cols[3].metric("Dividen", plain(row["dividend_yield"], "%"))
        extra = st.columns(4)
        extra[0].metric("PER", plain(row["pe"], "×"))
        extra[1].metric("PBV", plain(row["pbv"], "×"))
        extra[2].metric("ROE", plain(row["roe"], "%"))
        extra[3].metric("Utang/ekuitas", plain(row["debt_ratio"], "×"))
        show_parts("Fundamental", row["fundamental_parts"])
        show_parts("Tren untuk 1–6 bulan", row["technical_parts"])
    else:
        cols = st.columns(4)
        cols[0].metric("Harga", rupiah(row["price"]))
        cols[1].metric("Batas rugi", rupiah(row["stop"]))
        cols[2].metric("Target", rupiah(row["target"]))
        cols[3].metric("Risiko per lot", rupiah(row["risk_per_lot"]))
        st.caption("Bagi uang yang sanggup kamu rugi dengan risiko per lot untuk dapat jumlah lot. Satu lot berisi 100 lembar.")
        show_parts("Aturan setup", row["swing_parts"])
    show_chart(row, mode)
    st.link_button("Lihat di Yahoo", "https://finance.yahoo.com/quote/{}.JK".format(row["code"]))
    st.link_button(
        "Laporan keuangan di BEI",
        "https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan/",
    )


st.title("Saham Indonesia")
st.write(
    "Dua cara baca daftar yang sama. Trading untuk beberapa hari sampai empat minggu. "
    "Investasi untuk dipegang sekitar 1–6 bulan. Harga dari Yahoo Finance, tertunda, bukan data resmi BEI. "
    "Angka ini bukan jaminan profit."
)

mode_label = st.radio("Mode", ["Trading", "Investasi 1–6 bulan"], horizontal=True)
mode = "invest" if mode_label.startswith("Investasi") else "trading"
filters = {
    "trading": ["Semua", "Siap dibeli", "Tunggu", "Lewati"],
    "invest": ["Semua", "Paling sesuai", "Cukup layak", "Kurang sesuai"],
}
grade_for_label = {
    "Siap dibeli": "sesuai",
    "Tunggu": "cukup",
    "Lewati": "kurang",
    "Paling sesuai": "sesuai",
    "Cukup layak": "cukup",
    "Kurang sesuai": "kurang",
}

left, right = st.columns([3, 1])
with left:
    chosen = st.radio("Saringan", filters[mode], horizontal=True)
with right:
    refresh = st.button("Muat ulang", use_container_width=True)

try:
    with st.spinner("Mengambil harga dan angka fundamental. Pertama kali sekitar satu menit."):
        rows = load_rows(force=refresh)
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

if not rows:
    st.warning("Harga belum tersedia dari Yahoo Finance.")
    st.stop()

fetched = datetime.fromtimestamp(cached_at(), tz=ZoneInfo("Asia/Jakarta"))
months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
st.caption(
    "Harga per {}. LQ45 periode {}. Diunduh {} {} {} pukul {:02d}.{:02d} WIB.".format(
        rows[0]["as_of"],
        LQ45_PERIOD,
        fetched.day,
        months[fetched.month - 1],
        fetched.year,
        fetched.hour,
        fetched.minute,
    )
)

visible = rows
if chosen != "Semua":
    grade = grade_for_label[chosen]
    visible = [row for row in rows if view_of(row, mode)["grade"] == grade]

if mode == "invest":
    top = sorted(rows, key=lambda row: row["invest"]["rank"])[:3]
    cards = st.columns(3)
    for card, row in zip(cards, top):
        card.metric("{}. {}".format(row["invest"]["rank"], row["code"]), row["invest"]["score"], row["name"])
else:
    cards = st.columns(3)
    captions = [("sesuai", "Siap dibeli"), ("cukup", "Tunggu harga mendingin"), ("kurang", "Lewati")]
    for card, (grade, caption) in zip(cards, captions):
        total = sum(1 for row in rows if row["trading"]["grade"] == grade)
        card.metric(caption, total)

st.dataframe(board_frame(visible, mode), hide_index=True, use_container_width=True)

codes = [row["code"] for row in visible]
picked = st.selectbox("Buka saham dari daftar", codes if codes else ["—"])
search = st.text_input("Atau kode lain, misalnya BBCA", max_chars=6).strip().upper()

detail = None
if search:
    known = next((row for row in rows if row["code"] == search), None)
    if known:
        detail = known
    else:
        try:
            cleaned = normalize_code(search)
            frame, facts = load_one(cleaned, force=refresh)
            detail = analyze_frame(cleaned, company_name(cleaned, facts), frame, facts)
        except (ValueError, LookupError, RuntimeError) as exc:
            st.error(str(exc))
elif codes and picked in codes:
    detail = next(row for row in visible if row["code"] == picked)

if detail:
    show_detail(detail, mode)
