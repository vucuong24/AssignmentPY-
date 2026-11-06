from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed" / "fbref"
TABLES = ROOT / "outputs" / "fbref" / "tables"
FIGURES = ROOT / "outputs" / "fbref" / "figures"
MODELS = ROOT / "outputs" / "fbref" / "models"
REPORTS = ROOT / "outputs" / "fbref" / "reports"
SEASON = "2025-2026"
FT_URL = "https://www.footballtransfers.com/en/transfers/confirmed/2025-2026/uk-premier-league"

CLUB_ALIASES = {
    "Man City": "Manchester City", "Man Utd": "Manchester United",
    "Manchester Utd": "Manchester United", "Spurs": "Tottenham Hotspur",
    "Tottenham": "Tottenham Hotspur", "Nott'm Forest": "Nottingham Forest",
    "Nottm Forest": "Nottingham Forest", "Nottingham": "Nottingham Forest",
    "Brighton": "Brighton & Hove Albion", "Brighton and Hove Albion": "Brighton & Hove Albion",
    "West Ham": "West Ham United", "Wolves": "Wolverhampton Wanderers",
    "Leeds": "Leeds United", "Leeds Utd": "Leeds United", "Newcastle": "Newcastle United",
    "Bournemouth": "AFC Bournemouth", "Sunderland AFC": "Sunderland",
    "Brighton & Hove Albion FC": "Brighton & Hove Albion",
    "A. Villa": "Aston Villa", "N. Forest": "Nottingham Forest",
    "B'mouth": "AFC Bournemouth", "C. Palace": "Crystal Palace",
}


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")


def save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def save_csv(frame: pd.DataFrame, path: Path, index: bool = False) -> None:
    frame.to_csv(path, index=index, encoding="utf-8-sig")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_name(value: str) -> str:
    value = str(value).replace("đ", "d").replace("Đ", "D")
    value = unicodedata.normalize("NFKD", value)
    return re.sub(r"[^a-z0-9]", "", value.encode("ascii", "ignore").decode().lower())


def canonical_club(value: str) -> str:
    value = str(value).strip()
    value = re.sub(r"\s+FC$", "", value)
    return CLUB_ALIASES.get(value, value)


def number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.replace(",", "", regex=False), errors="coerce")


