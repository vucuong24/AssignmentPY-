"""Bước 07. Quy đổi chỉ số thành phân vị và vẽ radar so sánh hai cầu thủ."""


import argparse
from importlib import import_module

import numpy as np
import pandas as pd


# Nạp các hàm dùng chung từ bước 01. Tên file có tiền tố số.
shared = import_module("01_thu_thap_du_lieu")


shared.configure_plotting()
import matplotlib.pyplot as plt


def radar(p1=None, p2=None, attributes=None, same_position=True):
    shared.setup(shared.TABLES, shared.FIGURES)
    players, quality = shared.read_fbref()
    players["WebName"] = players.Name
    # Khi không chỉ định tên, chọn người ghi nhiều bàn nhất trong các nhóm đủ người
    # rồi chọn người ghi nhiều bàn tiếp theo trong cùng nhóm vị trí.
    if not p1 and not p2:
        eligible = players.copy()
        if "Position" in eligible:
            eligible = eligible[eligible.Position.map(eligible.Position.value_counts()).ge(2)]
        if eligible.empty:
            raise ValueError("Chưa có hai cầu thủ cùng vị trí để vẽ radar.")
        a = eligible.sort_values(["Gls", "Min"], ascending=False).iloc[0]
        peers = eligible[eligible.PlayerID.ne(a.PlayerID)]
        if "Position" in peers:
            peers = peers[peers.Position.eq(a.Position)]
        b = peers.sort_values(["Gls", "Min"], ascending=False).iloc[0]
    else:
        a, b = resolve_player(players, p1), resolve_player(players, p2)
    if same_position and "Position" in players and a.Position != b.Position:
        raise ValueError("Cần hai cầu thủ cùng vị trí hoặc thêm --all-positions.")
    # Xác định nhóm tham chiếu trước khi quy đổi các chỉ số khác đơn vị thành phân vị.
    reference = players[players.Position.eq(a.Position)] if same_position and "Position" in players else players
    attributes = attributes or [c for c in ["Gls_per90", "Ast_per90", "Min", "MP"]
                                if c in reference and pd.notna(a[c]) and pd.notna(b[c])][:5]
    if len(attributes) < 3:
        raise ValueError("Cần ít nhất 3 chỉ số FBref có giá trị cho cả hai cầu thủ.")
    scores = percentile_scores(reference, attributes)
    angles = np.r_[np.linspace(0, 2*np.pi, len(attributes), endpoint=False), 0]
    fig, ax = plt.subplots(figsize=(9, 8), subplot_kw={"polar": True})
    rows = []
    for player, color in zip([a, b], ["#245caa", "#e8932e"]):
        values = scores.loc[player.name].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("Chỉ số radar có giá trị thiếu; chọn thuộc tính khác.")
        # Lặp lại giá trị đầu để nối cạnh cuối của đa giác trên biểu đồ radar.
        closed = np.r_[values, values[0]]
        ax.plot(angles, closed, "o-", label=player.Name, color=color)
        ax.fill(angles, closed, color=color, alpha=.12)
        rows.extend({"PlayerID": player.PlayerID, "Name": player.Name, "Attribute": c,
                     "RawValue": float(player[c]), "Percentile": float(scores.loc[player.name, c]),
                     "ReferenceCount": len(reference)} for c in attributes)
    ax.set_xticks(angles[:-1], attributes)
    ax.tick_params(axis="x", pad=14, labelsize=9)
    ax.set_ylim(0, 100)
    ax.set_title("FBref: percentile comparison", pad=30)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.12))
    fig.tight_layout()
    fig.savefig(shared.FIGURES / "radar.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    shared.save_csv(pd.DataFrame(rows), shared.TABLES / "radar_values.csv")
    status = {"source": "FBref", "dataset_sha256": quality["dataset_sha256"], "players": [a.Name, b.Name], "attributes": attributes, "reference_count": len(reference)}
    shared.save_json(shared.TABLES / "radar_status.json", status)
    return status


def resolve_player(df: pd.DataFrame, query: str) -> pd.Series:
    key = shared.normalized_name(query)
    candidates = df["Name"].map(shared.normalized_name).eq(key) | df["PlayerID"].astype(str).eq(query)
    if "WebName" in df:
        candidates |= df["WebName"].map(shared.normalized_name).eq(key)
    found = df[candidates]
    # Khi tên bị trùng, yêu cầu dùng mã cầu thủ để xác định đúng hồ sơ.
    if len(found) != 1:
        raise ValueError(f"Tên/ID '{query}' khớp {len(found)} cầu thủ. Dùng PlayerID trong result.csv.")
    return found.iloc[0]


def percentile_scores(df: pd.DataFrame, attributes: list[str]) -> pd.DataFrame:
    if not attributes or len(attributes) != len(set(attributes)):
        raise ValueError("Danh sách thuộc tính rỗng hoặc bị lặp.")
    for col in attributes:
        if col not in df or not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(f"Thuộc tính không tồn tại hoặc không phải số: {col}")
    # Đồng hạng lấy thứ hạng trung bình rồi chia cho số giá trị hợp lệ của từng chỉ số.
    return df[attributes].rank(pct=True, method="average") * 100


def main(argv=None):
    shared.configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p1", help="Tên đầy đủ hoặc PlayerID của cầu thủ thứ nhất")
    parser.add_argument("--p2", help="Tên đầy đủ hoặc PlayerID của cầu thủ thứ hai")
    parser.add_argument("--attributes", "--Attribute", help="Danh sách chỉ số, phân tách bằng dấu phẩy")
    parser.add_argument("--all-positions", action="store_true", help="Cho phép so sánh khác vị trí")
    args = parser.parse_args(argv)
    if bool(args.p1) != bool(args.p2):
        parser.error("Cần cung cấp cả --p1 và --p2 để chọn cặp cầu thủ.")
    attributes = [value.strip() for value in args.attributes.split(",")] if args.attributes else None
    shared.run_step(radar, p1=args.p1, p2=args.p2, attributes=attributes, same_position=not args.all_positions)


if __name__ == "__main__":
    main()
