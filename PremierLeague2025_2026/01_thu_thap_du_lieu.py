"""Bước 01. Trích bảng FBref, chuẩn hóa hồ sơ và lưu CSV."""


import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import pandas as pd
from bs4 import BeautifulSoup, Comment


# Tính đường dẫn từ vị trí file Python để có thể chạy từ terminal ở thư mục khác.
ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed" / "fbref"
TABLES = ROOT / "outputs" / "fbref" / "tables"
FIGURES = ROOT / "outputs" / "fbref" / "figures"
MODELS = ROOT / "outputs" / "fbref" / "models"
SEASON = "2025-2026"

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
    # Dùng UTF-8 có BOM để Excel nhận đúng dấu tiếng Việt khi mở CSV.
    frame.to_csv(path, index=index, encoding="utf-8-sig")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_name(value: str) -> str:
    # Bỏ dấu, khoảng trắng và dấu câu để so khớp tên từ hai nguồn.
    value = str(value).replace("đ", "d").replace("Đ", "D")
    value = unicodedata.normalize("NFKD", value)
    return re.sub(r"[^a-z0-9]", "", value.encode("ascii", "ignore").decode().lower())


def canonical_club(value: str) -> str:
    value = str(value).strip()
    value = re.sub(r"\s+FC$", "", value)
    return CLUB_ALIASES.get(value, value)


def number(series: pd.Series) -> pd.Series:
    # Xóa dấu phân cách hàng nghìn. Ô trống hoặc sai định dạng được giữ là thiếu.
    return pd.to_numeric(series.astype("string").str.replace(",", "", regex=False), errors="coerce")


# Các bảng FBref và quy tắc tổng hợp cầu thủ.


INPUT = RAW / "fbref"
OUTPUT = PROCESSED
TEAM_CSV_DIR = "cau_thu_theo_doi"
GROUPS = ["standard", "keeper", "keeper_adv", "shooting", "passing", "passing_types",
          "gca", "defense", "possession", "playing_time", "misc"]
# Đổi tên trường data-stat của FBref thành tên cột dùng trong CSV.
CORE_MAP = {
    "age": "Age", "nationality": "Nation", "position": "Position", "games": "MP",
    "games_starts": "Starts", "minutes": "Min", "minutes_90s": "90s",
    "goals": "Gls", "assists": "Ast", "goals_assists": "G+A", "goals_pens": "G-PK",
    "pens_made": "PK", "pens_att": "PKatt", "cards_yellow": "CrdY", "cards_red": "CrdR",
    "xg": "xG", "npxg": "npxG", "xg_assist": "xAG", "npxg_xg_assist": "npxG+xAG",
    "progressive_carries": "PrgC", "progressive_passes": "PrgP", "progressive_passes_received": "PrgR",
}
SUPPLEMENT_MAP = {
    ("keeper", "gk_saves"): "Saves", ("keeper", "gk_clean_sheets"): "CleanSheets",
    ("shooting", "shots"): "Sh", ("shooting", "shots_on_target"): "SoT",
    ("passing", "passes_completed"): "Cmp", ("passing", "passes"): "Att",
    ("passing", "assisted_shots"): "KP", ("passing", "pass_xa"): "xA",
    ("defense", "tackles"): "Tkl", ("defense", "interceptions"): "Int",
    ("defense", "clearances"): "Clr", ("possession", "touches"): "Touches",
    ("possession", "carries"): "Carries", ("misc", "ball_recoveries"): "Recov",
}
# Chỉ các chỉ số tích lũy mới được cộng khi một cầu thủ thi đấu cho nhiều đội.
ADDITIVE = ["MP", "Starts", "Min", "Gls", "Ast", "G+A", "G-PK", "PK", "PKatt", "CrdY", "CrdR",
            "xG", "npxG", "xAG", "npxG+xAG", "PrgC", "PrgP", "PrgR"] + list(SUPPLEMENT_MAP.values())


def fbref_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or parts.netloc not in ["fbref.com", "www.fbref.com"]:
        raise ValueError("Chỉ nhận URL HTTPS trên tên miền fbref.com.")
    if parts.query or parts.fragment:
        raise ValueError("Hãy dùng URL FBref gốc không có query/fragment.")
    if not re.search(r"/en/(squads/[a-z0-9]+/2025-2026/|comps/9/2025-2026/)", parts.path):
        raise ValueError("URL phải thuộc Premier League hoặc trang đội mùa 2025-2026.")
    if "/all_comps/" in parts.path:
        raise ValueError("Không dùng trang All Competitions; cần trang Premier League.")
    return url.strip()


def soup_from_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and "just a moment" in soup.title.get_text().lower():
        raise ValueError("HTML là trang chặn truy cập, không phải thống kê FBref.")
    # FBref có thể đặt bảng trong chú thích HTML. Đưa bảng ra để tìm như bảng thường.
    for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
        if "<table" in comment:
            comment.replace_with(BeautifulSoup(str(comment), "html.parser"))
    return soup


def _table(soup, group):
    table = soup.find("table", id=f"stats_{group}_9")
    if table is None:
        alternative = soup.find("table", id=f"stats_{group}")
        # Bảng không có hậu tố mã giải chỉ được dùng khi chú thích ghi rõ Premier League.
        if alternative is not None and "premier league" in str(alternative.find("caption")).lower():
            table = alternative
    return table


def parse_squad(html: str, source_url: str | None = None, squad_name: str | None = None):
    soup = soup_from_html(html)
    # Đối chiếu URL nguồn và tiêu đề để xác nhận đúng đội, mùa giải và giải đấu.
    canonical = soup.select_one('link[rel="canonical"][href]')
    if canonical is not None:
        canonical_url = fbref_url(canonical["href"])
        canonical_id = re.search(r"/squads/([a-z0-9]+)/", canonical_url)
        supplied_id = re.search(r"/squads/([a-z0-9]+)/", source_url or "")
        if canonical_id is None or (source_url and (supplied_id is None or canonical_id[1] != supplied_id[1])):
            raise ValueError("HTML không khớp đội trong URL được khai báo.")
        source_url = canonical_url
    if not source_url:
        raise ValueError("HTML thiếu canonical URL; cần khai báo URL đội trong sidecar .source.json.")
    source_url = fbref_url(source_url)
    match = re.search(r"/squads/([a-z0-9]+)/", source_url)
    if not match:
        raise ValueError("Cần HTML trang đội, không phải bảng tổng giải.")
    squad_id = match[1]
    heading = soup.select_one("h1") or soup.title
    title = heading.get_text(" ", strip=True) if heading else ""
    title_match = re.search(r"2025\s*[-/–]\s*2026\s+(.+?)\s+Stats", title)
    if not title_match:
        raise ValueError("Không xác nhận được mùa 2025-2026 và tên đội trong tiêu đề HTML.")
    title_name = canonical_club(title_match[1].strip())
    if squad_name and canonical_club(squad_name) != title_name:
        raise ValueError("Tên đội trong bảng xếp hạng không khớp tiêu đề trang đội.")
    name = title_name
    frames = {}
    availability = {}
    long_rows = []
    for group in GROUPS:
        table = _table(soup, group)
        availability[group] = table is not None
        if table is None:
            continue
        records = []
        for tr in table.select("tbody tr"):
            player_cell = tr.select_one('[data-stat="player"]')
            if player_cell is None:
                continue
            link = player_cell.select_one('a[href*="/en/players/"]')
            if link is None:
                continue  # Bỏ dòng tổng và tiêu đề vì chúng không có liên kết hồ sơ cầu thủ.
            player_match = re.search(r"/players/([a-z0-9]+)/", link["href"])
            if player_match is None:
                raise ValueError("Không đọc được PlayerID từ URL hồ sơ FBref.")
            record = {"PlayerID": player_match[1], "Name": player_cell.get_text(" ", strip=True)}
            # Dùng data-stat thay cho vị trí cột vì thứ tự có thể khác giữa các bảng.
            for cell in tr.select("td[data-stat]"):
                stat = cell["data-stat"]
                if stat in record:
                    raise ValueError(f"Trùng data-stat {stat} trong cùng dòng {group}.")
                record[stat] = cell.get_text(" ", strip=True)
            records.append(record)
            long_rows.append({"SquadID": squad_id, "Squad": name, "Group": group, "SourceURL": source_url,
                              **record})
        frame = pd.DataFrame(records)
        if frame.empty:
            if group == "standard":
                raise ValueError("Bảng standard không có dòng cầu thủ thật.")
            availability[group] = False
            continue
        if frame.PlayerID.duplicated().any():
            raise ValueError(f"Trùng PlayerID trong bảng {group} của {name}.")
        frames[group] = frame
    if "standard" not in frames:
        raise ValueError(f"{name}: không có stats_standard_9; không dùng bảng giải khác làm thay thế.")
    base = frames["standard"].rename(columns=CORE_MAP)
    required = {"PlayerID", "Name", "Min", "MP", "Gls"}
    if not required.issubset(base):
        raise ValueError(f"{name}: bảng standard thiếu {sorted(required-set(base))}.")
    # Thêm tiền tố nhóm cho trường phụ để tỷ lệ và số liệu tích lũy không trùng tên.
    base = base.rename(columns={c: f"standard__{c}" for c in base if c not in set(CORE_MAP.values()) | {"PlayerID", "Name"}})
    for group, frame in frames.items():
        if group == "standard":
            continue
        supplement = frame.drop(columns="Name").rename(columns={
            c: SUPPLEMENT_MAP.get((group, c), f"{group}__{c}") for c in frame if c not in ["Name", "PlayerID"]
        })
        # Ghép trái theo PlayerID để giữ cả cầu thủ không xuất hiện ở bảng phụ.
        base = base.merge(supplement, on="PlayerID", how="left", validate="one_to_one")
    for col in base:
        if col in ["PlayerID", "Name", "Nation", "Position"] or col.endswith(("__nationality", "__position", "__matches")):
            continue
        if col == "Age":
            base[col] = base[col].astype("string").str.extract(r"^(\d+)", expand=False)
        base[col] = number(base[col])
    if "Nation" in base:
        base["Nation"] = base.Nation.astype("string").str.split().str[-1]
    # Chỉ suy ra 0 phút khi nguồn ghi 0 lần ra sân và không có lần đá chính.
    # Thiếu số phút ở các dòng khác khiến quá trình kiểm tra thất bại.
    unused = base.MP.eq(0)
    if "Starts" in base:
        unused &= base.Starts.fillna(0).eq(0)
    base.loc[base.Min.isna() & unused, "Min"] = 0
    if base.Min.isna().any() or base.Min.lt(0).any():
        raise ValueError(f"{name}: số phút thiếu, không hợp lệ hoặc âm.")
    base["SquadID"], base["Squad"] = squad_id, name
    base["Source"], base["Season"], base["SourceURL"] = "FBref", SEASON, source_url
    info = {"SquadID": squad_id, "Squad": name, "URL": source_url, "tables": availability,
            "rows": len(base), "numeric_columns": [c for c in base.select_dtypes("number")]}
    return base, pd.DataFrame(long_rows), info


def make_totals(stints: pd.DataFrame):
    if stints.duplicated(["PlayerID", "SquadID"]).any():
        raise ValueError("Trùng cầu thủ-đội giữa các HTML; hãy loại tệp trùng.")
    observed = [c for c in ADDITIVE if c in stints]
    # Bỏ lượt đăng ký chưa thi đấu để ô bàn thắng hay kiến tạo trống ở đội đó
    # không làm mất số liệu đã ghi nhận ở đội khác.
    stints = stints[stints.Min.gt(0)].copy()
    if stints.empty:
        raise ValueError("Không có cầu thủ nào thi đấu trong HTML.")
    grouped = stints.groupby("PlayerID", sort=False)
    # min_count buộc tổng phải đủ giá trị ở mọi đội cầu thủ từng thi đấu.
    totals = grouped[observed].agg(lambda series: series.sum(min_count=len(series)))
    for field in ["Name", "Age", "Nation", "Position"]:
        if field in stints:
            totals[field] = grouped[field].first()
    totals["Squad"] = grouped.Squad.agg(lambda s: " / ".join(dict.fromkeys(s)))
    totals = totals.reset_index()
    # Lọc theo tổng phút cả mùa sau khi gộp, rồi lấy lại các lượt theo đội của nhóm này.
    totals = totals[totals.Min.gt(90)].copy()
    stints = stints[stints.PlayerID.isin(totals.PlayerID) & stints.Min.gt(0)].copy()
    # Tính lại chỉ số mỗi 90 phút từ số phút tương ứng với mỗi bảng.
    for frame in [totals, stints]:
        frame["90s"] = frame.Min / 90
        for column in observed:
            if column not in ["Min", "MP", "Starts"]:
                frame[f"{column}_per90"] = frame[column] * 90 / frame.Min
        frame["Source"], frame["Season"] = "FBref", SEASON
    if totals.empty:
        raise ValueError("Không có cầu thủ đủ điều kiện >90 phút trong HTML.")
    return totals.sort_values(["Name", "PlayerID"]), stints.sort_values(["Squad", "Name"])


def summarize_collected_tables(table_rows: pd.DataFrame) -> pd.DataFrame:
    titles = {
        "standard": "Thống kê cầu thủ",
        "keeper": "Thủ môn",
        "keeper_adv": "Thủ môn nâng cao",
        "shooting": "Dứt điểm",
        "passing": "Chuyền bóng",
        "passing_types": "Loại đường chuyền",
        "gca": "Tạo cơ hội",
        "defense": "Phòng ngự",
        "possession": "Kiểm soát bóng",
        "playing_time": "Thời gian thi đấu",
        "misc": "Thống kê khác",
    }
    field_labels = {
        "age": "Tuổi", "position": "Vị trí", "games": "Số trận",
        "minutes": "Số phút", "goals": "Bàn thắng", "assists": "Kiến tạo",
        "gk_goals_against": "Bàn thua", "gk_saves": "Cứu thua",
        "gk_save_pct": "Tỷ lệ cứu thua", "gk_clean_sheets": "Trận sạch lưới",
        "shots": "Số cú sút", "shots_on_target": "Sút trúng đích",
        "shots_on_target_pct": "Tỷ lệ sút trúng đích", "shots_per90": "Cú sút mỗi 90 phút",
        "minutes_per_game": "Phút mỗi trận", "games_starts": "Số trận đá chính",
        "games_complete": "Số trận đá đủ", "games_subs": "Số lần vào sân thay người",
        "cards_yellow": "Thẻ vàng", "cards_red": "Thẻ đỏ", "fouls": "Phạm lỗi",
        "offsides": "Việt vị", "interceptions": "Cắt bóng", "tackles_won": "Tắc bóng thành công",
    }
    metadata = {"SquadID", "Squad", "Group", "SourceURL", "PlayerID", "Name", "matches"}
    summary = []
    # Mỗi dòng mô tả một loại bảng thực sự có hồ sơ trích xuất trước khi lọc phút.
    groups = table_rows.groupby("Group", sort=False)
    for group, rows in groups:
        fields = [
            field for field in rows.columns
            if field not in metadata and rows[field].dropna().ne("").any()
        ]
        examples = [field for field in field_labels if field in fields]
        examples.extend(field for field in fields if field not in field_labels)
        summary.append({
            "Mã bảng FBref": group,
            "Tên bảng": titles[group],
            "Số đội có dữ liệu": rows["SquadID"].nunique(),
            "Số dòng trước lọc": len(rows),
            "Chỉ số tiêu biểu": " / ".join(field_labels.get(field, field) for field in examples[:6]),
        })
    return pd.DataFrame(summary)


def save_team_csvs(stints: pd.DataFrame, directory: Path) -> None:
    # Chọn các cột để demo, giữ toàn bộ hồ sơ theo đội trước khi lọc số phút.
    labels = {
        "Name": "Cầu thủ", "Squad": "Đội", "Position": "Vị trí", "Nation": "Quốc tịch",
        "Age": "Tuổi", "MP": "Số trận", "Starts": "Đá chính", "Min": "Số phút",
        "Gls": "Bàn thắng", "Ast": "Kiến tạo", "Sh": "Cú sút", "SoT": "Sút trúng đích",
        "Saves": "Cứu thua", "CleanSheets": "Trận sạch lưới",
        "CrdY": "Thẻ vàng", "CrdR": "Thẻ đỏ", "PlayerID": "Mã cầu thủ",
    }
    columns = [column for column in labels if column in stints]
    directory.mkdir(parents=True, exist_ok=True)
    for (team, squad_id), rows in stints.groupby(["Squad", "SquadID"], sort=True):
        slug = re.sub(r"[^a-z0-9]+", "_", team.casefold()).strip("_")
        table = rows.sort_values(["Min", "Name"], ascending=[False, True])
        save_csv(table[columns].rename(columns=labels), directory / f"{slug}_{squad_id}.csv")


def collect_fbref(html_dir: Path | None = None, allow_partial=False, output: Path = OUTPUT) -> dict:
    """Read local HTML only; URL fields are provenance, never download targets."""
    INPUT.mkdir(parents=True, exist_ok=True)
    default_dir = RAW.parent / "sources"
    html_dir = Path(html_dir) if html_dir is not None else default_dir
    paths = sorted({*html_dir.glob("*.html"), *html_dir.glob("*.htm"),
                    *html_dir.glob("*.HTML"), *html_dir.glob("*.HTM")})
    if not paths:
        raise ValueError(f"Chưa có HTML trong {html_dir}. Hãy đặt các trang đội bạn đã lưu vào thư mục này.")
    frames, long_frames, infos, originals = [], [], [], []
    for path in paths:
        html = path.read_text(encoding="utf-8-sig")
        source_url = None
        # Tệp metadata đi kèm cung cấp URL nguồn khi HTML thiếu URL canonical.
        sidecar = path.with_suffix(path.suffix + ".source.json")
        if sidecar.exists():
            source_url = json.loads(sidecar.read_text(encoding="utf-8")).get("url")
        try:
            frame, long, info = parse_squad(html, source_url)
        except ValueError as error:
            raise ValueError(f"{path.name}: {error}") from error
        frames.append(frame)
        long_frames.append(long)
        infos.append(info)
        originals.append({"file": str(path.resolve()), "sha256": sha256(path), "URL": info["URL"],
                          "method": "browser-saved original FBref HTML"})
        print(f"Đọc {path.name}: {info['Squad']}, {len(frame)} hồ sơ, "
              f"{sum(info['tables'].values())} bảng.", flush=True)
    if not frames:
        raise ValueError("Chưa có HTML trang đội FBref hợp lệ để xử lý.")
    raw_stints = pd.concat(frames, ignore_index=True)
    actual = int(raw_stints.SquadID.nunique())
    if not allow_partial and actual != 20:
        raise ValueError(f"Đọc được {actual}/20 đội. Chưa xuất kết quả toàn giải; bổ sung HTML của các đội còn lại.")
    if len(infos) != actual:
        raise ValueError("Có nhiều HTML cho cùng đội; chỉ giữ một bản đúng mùa/giải.")
    if raw_stints.Squad.nunique() != actual:
        raise ValueError("Mã đội và tên đội không có quan hệ một-một; kiểm tra lại HTML.")
    totals, stints = make_totals(raw_stints)
    if len(totals.PlayerID.unique()) < 2:
        raise ValueError("Không đủ cầu thủ để phân tích.")
    output = Path(output)
    existing = output / "data_quality.json"
    # Khi thử dữ liệu một phần, bảo vệ bộ kết quả đủ 20 đội khỏi bị ghi đè.
    if actual != 20 and existing.exists() and json.loads(existing.read_text(encoding="utf-8")).get("complete_league"):
        raise ValueError("Không ghi đè tập FBref đủ 20 đội bằng tập một phần. Dùng thư mục dự án riêng để thử nghiệm.")
    output.mkdir(parents=True, exist_ok=True)
    save_csv(totals, output / "result.csv")
    save_csv(stints, output / "player_team_stints.csv")
    table_rows = pd.concat(long_frames, ignore_index=True)
    save_csv(table_rows, output / "table_rows.csv")
    save_csv(summarize_collected_tables(table_rows), output / "tong_hop_bang_thu_thap.csv")
    save_team_csvs(raw_stints, output / TEAM_CSV_DIR)
    # Lưu mã băm kết quả và thông tin các HTML để kiểm tra nguồn ở các bước sau.
    quality = {"source": "FBref", "season": SEASON, "complete_league": actual == 20,
               "dataset_sha256": sha256(output / "result.csv"),
               "teams": actual, "expected_teams": 20, "players_over_90": len(totals), "stints": len(stints),
               "collected_at": now(), "team_tables": infos, "raw_sources": originals,
               "missing_requested_metrics": [c for c in ["xG", "xAG", "PrgP", "npxG"] if c not in totals or totals[c].isna().all()],
               "aggregation_note": "Tổng mùa dùng PlayerID; giữ riêng đội. Chỉ cộng các chỉ số tích lũy đã định nghĩa. Chỉ số thiếu không được gán 0.",
               "supplement_note": "Các cột bảng phụ có namespace giữ trong stints/table_rows; tỷ lệ không được cộng thành tổng mùa."}
    save_json(output / "data_quality.json", quality)
    save_json(INPUT / "collection_status.json", {"status": "complete" if actual == 20 else "partial",
              "teams": actual, "checked_at": now(), "source": "FBref", "output": str(output)})
    return quality


# Các bước sau dùng chung cách đọc, kiểm tra và lưu dữ liệu.


def read_fbref_quality():
    meta = OUTPUT / "data_quality.json"
    if not meta.exists():
        raise ValueError("Chưa có dữ liệu FBref đã xử lý. Hãy chạy 01_thu_thap_du_lieu.py trước.")
    quality = json.loads(meta.read_text(encoding="utf-8"))
    if quality.get("source") != "FBref":
        raise ValueError("Sai nguồn: quy trình này chỉ nhận dữ liệu FBref.")
    # Kiểm tra CSV có còn đúng là bản được tạo từ lần chuẩn bị đã ghi trong metadata.
    if quality.get("dataset_sha256") != sha256(OUTPUT / "result.csv"):
        raise ValueError("CSV FBref không khớp hash đã ghi; hãy chạy lại bước 01 từ HTML gốc.")
    return quality


def read_fbref():
    quality = read_fbref_quality()
    players = pd.read_csv(OUTPUT / "result.csv", dtype={"PlayerID": str})
    return players, quality


def read_step_status(filename, script):
    quality = read_fbref_quality()
    path = TABLES / filename
    if path.exists():
        status = json.loads(path.read_text(encoding="utf-8"))
        if status.get("dataset_sha256") == quality["dataset_sha256"]:
            return status
    raise ValueError(f"Hãy chạy {script} cho bộ dữ liệu FBref hiện tại trước.")


def setup(*directories):
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def configure_plotting():
    import matplotlib

    # Dùng bộ vẽ không cần cửa sổ vì các biểu đồ được lưu thành PNG.
    matplotlib.use("Agg")
    matplotlib.rcParams.update({"figure.dpi": 110, "savefig.dpi": 160, "font.family": "DejaVu Sans"})


def configure_console():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def run_step(action, **kwargs):
    configure_console()
    try:
        result = action(**kwargs)
    except (ValueError, OSError) as error:
        print(f"Lỗi: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


def thu_thap_du_lieu(html_dir=None, allow_partial=False):
    quality = collect_fbref(html_dir=html_dir, allow_partial=allow_partial)
    return {
        "teams": quality["teams"],
        "players_over_90": quality["players_over_90"],
        "team_csv_directory": str(OUTPUT / TEAM_CSV_DIR),
        "files": [
            str(OUTPUT / name)
            for name in (
                "tong_hop_bang_thu_thap.csv", "result.csv", "player_team_stints.csv",
                "table_rows.csv", "data_quality.json",
            )
        ],
    }


def main(argv=None):
    configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html-dir", type=Path, help="Thư mục chứa HTML FBref đã lưu")
    parser.add_argument("--allow-partial", action="store_true", help="Cho phép thử với ít hơn 20 đội")
    args = parser.parse_args(argv)
    run_step(thu_thap_du_lieu, html_dir=args.html_dir, allow_partial=args.allow_partial)


if __name__ == "__main__":
    main()
