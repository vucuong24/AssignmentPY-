"""Shared statistics and plotting helpers for the saved HTML pipeline."""
from __future__ import annotations

import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .common import normalized_name

plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 160, "font.family": "DejaVu Sans"})
PALETTE = ["#245caa", "#e8932e"]


def safe_filename(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def top_bottom(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in columns:
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
            for team in frame.index[frame[col].eq(maximum)]:
                rows.append({"Attribute": col, "Aggregation": method, "Squad": team, "Value": maximum})
    return pd.DataFrame(rows)


def histogram(df: pd.DataFrame, group_name: str, directory) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for col in ["Age", "MP", "90s"]:
        values = df[col].dropna()
        fig, ax = plt.subplots(figsize=(8.5, 5))
        sns.histplot(values, bins=min(20, max(5, len(values) // 2)), kde=values.nunique() > 2,
                     color=PALETTE[0], ax=ax)
        ax.set(title=f"{col} distribution - {group_name}", xlabel=col, ylabel="Players / team stints")
        ax.grid(axis="y", alpha=.2)
        fig.tight_layout()
        fig.savefig(directory / f"{safe_filename(group_name)}_{col}.png")
        plt.close(fig)


def resolve_player(df: pd.DataFrame, query: str) -> pd.Series:
    key = normalized_name(query)
    candidates = df["Name"].map(normalized_name).eq(key) | df["PlayerID"].astype(str).eq(query)
    if "WebName" in df:
        candidates |= df["WebName"].map(normalized_name).eq(key)
    found = df[candidates]
    if len(found) != 1:
        raise ValueError(f"Tên/ID '{query}' khớp {len(found)} cầu thủ. Dùng PlayerID trong result.csv.")
    return found.iloc[0]


def percentile_scores(df: pd.DataFrame, attributes: list[str]) -> pd.DataFrame:
    if not attributes or len(attributes) != len(set(attributes)):
        raise ValueError("Danh sách thuộc tính rỗng hoặc bị lặp.")
    for col in attributes:
        if col not in df or not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(f"Thuộc tính không tồn tại hoặc không phải số: {col}")
    return df[attributes].rank(pct=True, method="average") * 100
