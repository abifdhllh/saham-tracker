"""Write the LQ45 snapshot that the hosted page reads."""

import json
import shutil
import tempfile
from pathlib import Path

from fastapi import HTTPException

from app import board, saham
from universe import LQ45

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "static" / "data"
MIN_ROWS = 30


def _clean(value):
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if hasattr(value, "item") and not isinstance(value, (bytes, str)):
        try:
            return value.item()
        except (ValueError, AttributeError):
            return value
    return value


def main():
    payload = _clean(board(refresh=True))
    rows = payload.get("rows") or []
    if len(rows) < MIN_ROWS:
        raise SystemExit(
            "Hanya {} dari {} saham yang ketemu. File lama tidak ditimpa.".format(len(rows), len(LQ45))
        )

    tmp = Path(tempfile.mkdtemp(prefix="data-", dir=str(ROOT / "static")))
    try:
        for row in rows:
            code = row["code"]
            detail = _clean(saham(code))
            (tmp / "{}.json".format(code)).write_text(
                json.dumps(detail, ensure_ascii=False),
                encoding="utf-8",
            )
        (tmp / "board.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        if DATA.exists():
            shutil.rmtree(DATA)
        tmp.rename(DATA)
    except (HTTPException, OSError, TypeError, ValueError):
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    print("Tersimpan {} saham.".format(len(rows)))


if __name__ == "__main__":
    main()
