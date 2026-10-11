"""Personal IDX desk. Run: uvicorn app:app --app-dir the project folder."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from analysis import FUND_WEIGHT, TECH_WEIGHT, analyze_frame
from market import cached_at, load_board, load_one, normalize_code, summarize
from universe import LQ45, LQ45_PERIOD

ROOT = Path(__file__).resolve().parent


def _company_name(code: str, facts: dict) -> str:
    if code in LQ45:
        return LQ45[code]
    return facts.get("short_name") or code

app = FastAPI(title="Saham Indonesia")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def home():
    return FileResponse(
        ROOT / "static" / "index.html",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/board")
def board(refresh: bool = Query(False)):
    try:
        cached = load_board(force=refresh)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    rows = summarize(cached)
    public = [{key: value for key, value in row.items() if key != "chart"} for row in rows]
    return {
        "period": LQ45_PERIOD,
        "source": "Harga penutupan Yahoo Finance, tertunda. Bukan data resmi BEI. Setup ini untuk ayunan beberapa hari sampai empat minggu, bukan jaminan profit.",
        "weights": {"fundamental": FUND_WEIGHT, "technical": TECH_WEIGHT},
        "fetched_at": cached_at(),
        "missing": [code for code in LQ45 if code not in cached["frames"]],
        "rows": public,
    }


@app.get("/api/saham/{code}")
def saham(code: str, refresh: bool = Query(False)):
    try:
        cleaned = normalize_code(code)
        frame, facts = load_one(cleaned, force=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    row = analyze_frame(cleaned, _company_name(cleaned, facts), frame, facts)
    if row is None:
        raise HTTPException(status_code=404, detail="Riwayat harga {} terlalu pendek.".format(cleaned))
    if cleaned in LQ45:
        ranked = summarize(load_board())
        match = next((item for item in ranked if item["code"] == cleaned), None)
        if match:
            row["rank"] = match["trading"]["rank"]
            row["trading"]["rank"] = match["trading"]["rank"]
            row["invest"]["rank"] = match["invest"]["rank"]
    row["source"] = "Yahoo Finance"
    row["quote_url"] = "https://finance.yahoo.com/quote/{}.JK".format(cleaned)
    row["report_url"] = "https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan/"
    return row
