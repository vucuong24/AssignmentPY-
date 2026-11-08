"""Bước 02. Tính thống kê theo giải và theo đội, rồi vẽ histogram."""


import re
from importlib import import_module

import pandas as pd
import seaborn as sns


# Nạp các hàm dùng chung từ bước 01. Tên file có tiền tố số.
shared = import_module("01_thu_thap_du_lieu")


shared.configure_plotting()
import matplotlib.pyplot as plt


def statistics():
    shared.setup(shared.TABLES, shared.FIGURES)
    players, quality = shared.read_fbref()
    stints = pd.read_csv(shared.OUTPUT / "player_team_stints.csv", dtype={"PlayerID": str, "SquadID": str})
    # Toàn giải đếm mỗi cầu thủ một lần. Theo đội dùng từng lượt cầu thủ tại đội đó.
    columns = [c for c in players.select_dtypes("number") if c not in ["PlayerID", "SquadID"] and players[c].notna().any()]
    shared.save_csv(top_bottom(players, columns), shared.TABLES / "top3_bottom3.csv")
    shared.save_csv(players[columns].agg(["median", "mean", "std"]).T.rename_axis("Attribute").reset_index(), shared.TABLES / "league_statistics.csv")
    team = stints.groupby("Squad")[columns].agg(["median", "mean", "std"])
    team.columns = [f"{c}_{s}" for c, s in team.columns]
    league = pd.DataFrame([{f"{c}_{s}": getattr(players[c], s)() for c in columns for s in ["median", "mean", "std"]}], index=["all"])
    shared.save_csv(pd.concat([league, team]).rename_axis("Squad"), shared.TABLES / "results2.csv", index=True)
    # Cộng các chỉ số tích lũy như bàn thắng. Tuổi dùng trung bình của từng đội.
    sums = [c for c in shared.ADDITIVE if c in columns]
    totals = stints.groupby("Squad")[sums].sum(min_count=1)
    shared.save_csv(totals, shared.TABLES / "team_totals.csv", index=True)
    age = stints.groupby("Squad")[["Age"]].mean() if "Age" in stints else pd.DataFrame()
    shared.save_csv(team_leaders(totals, age), shared.TABLES / "team_leaders.csv")
    histogram_count = 0
    plot_columns = [c for c in ["Age", "MP", "90s"] if c in players and players[c].notna().any()]
    # Hàm vẽ dùng cả ba cột Age, MP và 90s. Chỉ gọi khi mỗi cột đều có dữ liệu.
    if len(plot_columns) == 3:
        histogram(players, "All league", shared.FIGURES / "histograms")
        for club, group in stints.groupby("Squad"):
            histogram(group, club, shared.FIGURES / "histograms")
        histogram_count = len(plot_columns) * (quality["teams"] + 1)
    status = {"source": "FBref", "dataset_sha256": quality["dataset_sha256"], "numeric_columns": columns, "histogram_count": histogram_count,
              "missing_histogram_columns": sorted(set(["Age", "MP", "90s"]) - set(plot_columns)),
              "note": "Tổng đội chỉ cộng chỉ số tích lũy; không cộng phần trăm hoặc tỷ lệ mỗi 90 phút."}
    shared.save_json(shared.TABLES / "statistics_status.json", status)
    return status


def safe_filename(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def top_bottom(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in columns:
        # Bỏ ô thiếu và dùng tên, mã cầu thủ để xếp nhất quán khi bằng giá trị.
        valid = df.dropna(subset=[column]).sort_values([column, "Name", "PlayerID"], kind="stable")
        for direction, chosen in [("bottom", valid.head(3)), ("top", valid.sort_values(
            [column, "Name", "PlayerID"], ascending=[False, True, True], kind="stable"
        ).head(3))]:
            for rank, (_, row) in enumerate(chosen.iterrows(), 1):
                rows.append({"Attribute": column, "Direction": direction, "Rank": rank,
                             "PlayerID": row["PlayerID"], "Name": row["Name"], "Squad": row["Squad"],
                             "Value": row[column]})
    return pd.DataFrame(rows)


def team_leaders(totals: pd.DataFrame, means: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, frame in [("sum_of_qualified_player_stints", totals), ("mean_of_qualified_player_stints", means)]:
        for col in frame:
            maximum = frame[col].max()
            # Giữ mọi đội cùng đạt giá trị lớn nhất.
            for team in frame.index[frame[col].eq(maximum)]:
                rows.append({"Attribute": col, "Aggregation": method, "Squad": team, "Value": maximum})
    return pd.DataFrame(rows)


def histogram(df: pd.DataFrame, group_name: str, directory) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for col in ["Age", "MP", "90s"]:
        values = df[col].dropna()
        fig, ax = plt.subplots(figsize=(8.5, 5))
        # Giới hạn số khoảng theo cỡ mẫu. Chỉ vẽ đường mật độ khi đủ giá trị khác nhau.
        sns.histplot(values, bins=min(20, max(5, len(values) // 2)), kde=values.nunique() > 2,
                     color="#245caa", ax=ax)
        ax.set(title=f"{col} distribution - {group_name}", xlabel=col, ylabel="Players / team stints")
        ax.grid(axis="y", alpha=.2)
        fig.tight_layout()
        fig.savefig(directory / f"{safe_filename(group_name)}_{col}.png")
        plt.close(fig)


if __name__ == "__main__":
    shared.run_step(statistics)
