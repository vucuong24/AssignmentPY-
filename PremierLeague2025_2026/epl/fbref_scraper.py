"""Read browser-saved original FBref HTML. This module does not request any URL."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
from bs4 import BeautifulSoup, Comment

from .common import RAW, PROCESSED, SEASON, canonical_club, now, number, save_csv, save_json, sha256

INPUT = RAW / "fbref"
OUTPUT = PROCESSED
GROUPS = ["standard", "keeper", "keeper_adv", "shooting", "passing", "passing_types",
          "gca", "defense", "possession", "playing_time", "misc"]
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
    for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
        if "<table" in comment:
            comment.replace_with(BeautifulSoup(str(comment), "html.parser"))
    return soup




def _table(soup, group):
    table = soup.find("table", id=f"stats_{group}_9")
    if table is None:
        alternative = soup.find("table", id=f"stats_{group}")
        # Unsuffixed tables are accepted only with explicit competition evidence.
        if alternative is not None and "premier league" in str(alternative.find("caption")).lower():
            table = alternative
    return table


def parse_squad(html: str, source_url: str | None = None, squad_name: str | None = None):
    soup = soup_from_html(html)
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
                continue  # Headers, totals and opponent totals are not player rows.
            player_match = re.search(r"/players/([a-z0-9]+)/", link["href"])
            if player_match is None:
                raise ValueError("Không đọc được PlayerID từ URL hồ sơ FBref.")
            record = {"PlayerID": player_match[1], "Name": player_cell.get_text(" ", strip=True)}
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
    # Namespace extra fields so per90 percentages never collide with season totals.
    base = base.rename(columns={c: f"standard__{c}" for c in base if c not in set(CORE_MAP.values()) | {"PlayerID", "Name"}})
    for group, frame in frames.items():
        if group == "standard":
            continue
        supplement = frame.drop(columns="Name").rename(columns={
            c: SUPPLEMENT_MAP.get((group, c), f"{group}__{c}") for c in frame if c not in ["Name", "PlayerID"]
        })
        base = base.merge(supplement, on="PlayerID", how="left", validate="one_to_one")
    for col in base:
        if col in ["PlayerID", "Name", "Nation", "Position"] or col.endswith(("__nationality", "__position", "__matches")):
            continue
        if col == "Age":
            base[col] = base[col].astype("string").str.extract(r"^(\d+)", expand=False)
        base[col] = number(base[col])
    if "Nation" in base:
        base["Nation"] = base.Nation.astype("string").str.split().str[-1]
    # FBref lists unused players with games=0 but blank minutes. Only this explicit
    # zero-appearance case implies zero minutes; unknown minutes for played rows fail.
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
    # An unused registration at a club is not a played stint; blank goals/assists
    # there must not erase the player's known contributions at a different club.
    stints = stints[stints.Min.gt(0)].copy()
    if stints.empty:
        raise ValueError("Không có cầu thủ nào thi đấu trong HTML.")
    grouped = stints.groupby("PlayerID", sort=False)
    # A missing stint statistic is not assumed to be zero.
    totals = grouped[observed].agg(lambda series: series.sum(min_count=len(series)))
    for field in ["Name", "Age", "Nation", "Position"]:
        if field in stints:
            totals[field] = grouped[field].first()
    totals["Squad"] = grouped.Squad.agg(lambda s: " / ".join(dict.fromkeys(s)))
    totals = totals.reset_index()
    totals = totals[totals.Min.gt(90)].copy()
    stints = stints[stints.PlayerID.isin(totals.PlayerID) & stints.Min.gt(0)].copy()
    for frame in [totals, stints]:
        frame["90s"] = frame.Min / 90
        for column in observed:
            if column not in ["Min", "MP", "Starts"]:
                frame[f"{column}_per90"] = frame[column] * 90 / frame.Min
        frame["Source"], frame["Season"] = "FBref", SEASON
    if totals.empty:
        raise ValueError("Không có cầu thủ đủ điều kiện >90 phút trong HTML.")
    return totals.sort_values(["Name", "PlayerID"]), stints.sort_values(["Squad", "Name"])

def collect_fbref(html_dir: Path | None = None, allow_partial=False, output: Path = OUTPUT) -> dict:
    """Read local HTML only; URL fields are provenance, never download targets."""
    INPUT.mkdir(parents=True, exist_ok=True)
    default_dir = INPUT.parent / "sources"
    html_dir = Path(html_dir) if html_dir is not None else default_dir
    paths = sorted({*html_dir.glob("*.html"), *html_dir.glob("*.htm"),
                    *html_dir.glob("*.HTML"), *html_dir.glob("*.HTM")})
    if not paths:
        raise ValueError(f"Chưa có HTML trong {html_dir}. Hãy đặt các trang đội bạn đã lưu vào thư mục này.")
    frames, long_frames, infos, originals = [], [], [], []
    for path in paths:
        html = path.read_text(encoding="utf-8-sig")
        source_url = None
        sidecar = path.with_suffix(path.suffix + ".source.json")
        if sidecar.exists():
            source_url = json.loads(sidecar.read_text(encoding="utf-8")).get("url")
        try:
            frame, long, info = parse_squad(html, source_url)
        except ValueError as error:
            raise ValueError(f"{path.name}: {error}") from error
        frames.append(frame); long_frames.append(long); infos.append(info)
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
    if actual != 20 and existing.exists() and json.loads(existing.read_text(encoding="utf-8")).get("complete_league"):
        raise ValueError("Không ghi đè tập FBref đủ 20 đội bằng tập một phần. Dùng thư mục dự án riêng để thử nghiệm.")
    output.mkdir(parents=True, exist_ok=True)
    save_csv(totals, output / "result.csv")
    save_csv(stints, output / "player_team_stints.csv")
    save_csv(pd.concat(long_frames, ignore_index=True), output / "table_rows.csv")
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
