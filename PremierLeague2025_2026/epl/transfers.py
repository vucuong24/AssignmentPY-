"""Validate and filter confirmed FootballTransfers fees from a local snapshot."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import FT_URL, canonical_club


def confirmed_fee(record: dict) -> float:
    """Unknown/missing prices are NaN; explicit free transfers are zero."""
    if record.get("unknown") or record.get("disclosed") in [0, False]:
        return np.nan
    if record.get("free") == 1:
        return 0.0
    value = (record.get("price_tag") or {}).get("value")
    if value is None or not str(record.get("amount", "")).startswith("€"):
        return np.nan
    fee = pd.to_numeric(value, errors="coerce")
    return float(fee) if pd.notna(fee) and fee >= 0 else np.nan


def prepare_confirmed(records: list[dict], clubs: set[str]):
    rows = []
    for record in records:
        rows.append({
            "TransferID": record["id"], "PlayerID_FT": record.get("player_id"),
            "Name": record.get("player_name"),
            "ClubFrom": canonical_club(record.get("club_from_name") or record.get("club_from_short_name") or "Without Club"),
            "ClubTo": canonical_club(record.get("club_to_name") or record.get("club_to_short_name") or "Without Club"),
            "Date": record.get("date_transfer"), "FeeEUR": confirmed_fee(record),
            "PriceText": record.get("amount"), "Position": record.get("position_short_name"),
            "Nationality": record.get("country_name"), "SeasonID": record.get("season_id"),
            "TypeID_Source": record.get("type_id"), "Source": "FootballTransfers", "SourceURL": FT_URL,
        })
    all_rows = pd.DataFrame(rows)
    if all_rows.TransferID.duplicated().any():
        raise ValueError("Trùng TransferID trong dữ liệu FootballTransfers.")
    dates = pd.to_datetime(all_rows["Date"], utc=True, errors="coerce")
    in_period = dates.ge(pd.Timestamp("2025-06-01", tz="UTC")) & dates.lt(pd.Timestamp("2026-07-01", tz="UTC"))
    related = all_rows.ClubFrom.isin(clubs) | all_rows.ClubTo.isin(clubs)
    included = in_period & related
    excluded = all_rows.loc[~included].copy()
    excluded["Reason"] = np.where(~in_period.loc[~included], "outside_2025_06_01_to_2026_06_30", "not_a_2025_26_PL_club")
    result = all_rows.loc[included].copy().sort_values(["Date", "Name"])
    return result, excluded
