"""Bước 08. Lọc giao dịch và ghép hồ sơ FootballTransfers với FBref."""


import json
from importlib import import_module

import numpy as np
import pandas as pd


# Nạp các hàm dùng chung từ bước 01. Tên file có tiền tố số.
shared = import_module("01_thu_thap_du_lieu")


FT_URL = "https://www.footballtransfers.com/en/transfers/confirmed/2025-2026/uk-premier-league"


def transfers():
    shared.setup(shared.TABLES)
    players, quality = shared.read_fbref()
    stints = pd.read_csv(shared.OUTPUT / "player_team_stints.csv", dtype={"PlayerID": str, "SquadID": str})
    raw = shared.RAW / "footballtransfers_2025_2026.json"
    if not raw.exists():
        raise ValueError("Chưa có bản lưu giao dịch gốc FootballTransfers. Quy trình hiện tại chỉ đọc tệp, không tự truy cập URL.")
    # Kiểm tra mã băm của JSON trước khi dùng dữ liệu phí chuyển nhượng.
    provenance = raw.with_suffix(".json.source.json")
    if not provenance.exists() or json.loads(provenance.read_text(encoding="utf-8")).get("sha256") != shared.sha256(raw):
        raise ValueError("JSON FootballTransfers thiếu nguồn/hash hợp lệ; tải lại từ trang gốc.")
    records = json.loads(raw.read_text(encoding="utf-8"))
    confirmed, excluded = prepare_confirmed(records, set(stints.Squad))
    shared.save_csv(confirmed, shared.OUTPUT / "transfer_values.csv")
    shared.save_csv(excluded, shared.TABLES / "excluded_transfers.csv")
    # Chỉ ghép khi tên chuẩn hóa khớp duy nhất và đội đi hoặc đội đến khớp hồ sơ FBref.
    lookup = {}
    for _, row in players.iterrows():
        lookup.setdefault(shared.normalized_name(row.Name), []).append(row.PlayerID)
    confirmed["FBrefPlayerID"] = confirmed.Name.map(lambda name: lookup.get(shared.normalized_name(name), [None])[0]
                                                     if len(lookup.get(shared.normalized_name(name), [])) == 1 else None)
    membership = stints.groupby("PlayerID").Squad.agg(set).to_dict()
    for index, row in confirmed[confirmed.FBrefPlayerID.notna()].iterrows():
        known = membership.get(str(row.FBrefPlayerID), set())
        if not known.intersection({shared.canonical_club(row.ClubFrom), shared.canonical_club(row.ClubTo)}):
            confirmed.at[index, "FBrefPlayerID"] = None
    joined = confirmed.merge(players, left_on="FBrefPlayerID", right_on="PlayerID", how="left",
                             suffixes=("_Transfer", "_FBref"), validate="many_to_one")
    shared.save_csv(joined, shared.OUTPUT / "transfers_with_fbref.csv")
    status = {"source": "FootballTransfers direct + FBref", "dataset_sha256": quality["dataset_sha256"], "raw_transfers": len(records),
              "included": len(confirmed), "matched_by_unique_name_and_club": int(confirmed.FBrefPlayerID.notna().sum()),
              "unknown_fees": int(confirmed.FeeEUR.isna().sum()),
              "raw_file_sha256": shared.sha256(raw),
              "note": "Ghép chính xác tên chuẩn hóa duy nhất và kiểm tra đội; không ghép mờ, không dùng giá FPL."}
    shared.save_json(shared.TABLES / "transfer_status.json", status)
    return status


def confirmed_fee(record: dict) -> float:
    """Unknown/missing prices are NaN; explicit free transfers are zero."""
    # Ưu tiên cờ chưa công bố nếu các cờ trạng thái trong nguồn mâu thuẫn.
    if record.get("unknown") or record.get("disclosed") in [0, False]:
        return np.nan
    if record.get("free") == 1:
        return 0.0
    # Lấy số tiền từ trường số và chỉ chấp nhận bản ghi có đơn vị euro.
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
            "ClubFrom": shared.canonical_club(record.get("club_from_name") or record.get("club_from_short_name") or "Without Club"),
            "ClubTo": shared.canonical_club(record.get("club_to_name") or record.get("club_to_short_name") or "Without Club"),
            "Date": record.get("date_transfer"), "FeeEUR": confirmed_fee(record),
            "PriceText": record.get("amount"), "Position": record.get("position_short_name"),
            "Nationality": record.get("country_name"), "SeasonID": record.get("season_id"),
            "TypeID_Source": record.get("type_id"), "Source": "FootballTransfers", "SourceURL": FT_URL,
        })
    all_rows = pd.DataFrame(rows)
    if all_rows.TransferID.duplicated().any():
        raise ValueError("Trùng TransferID trong dữ liệu FootballTransfers.")
    dates = pd.to_datetime(all_rows["Date"], utc=True, errors="coerce")
    # Chọn giao dịch trong khoảng 01/06/2025 đến hết 30/06/2026 theo UTC.
    in_period = dates.ge(pd.Timestamp("2025-06-01", tz="UTC")) & dates.lt(pd.Timestamp("2026-07-01", tz="UTC"))
    # Giữ giao dịch nếu ít nhất một đội tham gia thuộc danh sách Premier League.
    related = all_rows.ClubFrom.isin(clubs) | all_rows.ClubTo.isin(clubs)
    included = in_period & related
    excluded = all_rows.loc[~included].copy()
    excluded["Reason"] = np.where(~in_period.loc[~included], "outside_2025_06_01_to_2026_06_30", "not_a_2025_26_PL_club")
    result = all_rows.loc[included].copy().sort_values(["Date", "Name"])
    return result, excluded


if __name__ == "__main__":
    shared.run_step(transfers)
