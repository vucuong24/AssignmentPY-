"""Bước 03. Vẽ tổng số bàn thắng của các cầu thủ đủ điều kiện theo đội."""


from importlib import import_module

import pandas as pd


# Nạp các hàm dùng chung từ bước 01. Tên file có tiền tố số.
shared = import_module("01_thu_thap_du_lieu")


shared.configure_plotting()
import matplotlib.pyplot as plt


def team_goals():
    shared.read_step_status("statistics_status.json", "02_thong_ke_histogram.py")
    totals = pd.read_csv(shared.TABLES / "team_totals.csv", index_col="Squad")
    shared.setup(shared.FIGURES)
    fig, ax = plt.subplots(figsize=(10, 7))
    totals.Gls.sort_values().plot.barh(ax=ax, color="#245caa")
    ax.set(title="FBref: goals of qualified player-team stints (2025/26)", xlabel="Goals", ylabel="")
    path = shared.FIGURES / "team_goals.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return {"figure": str(path)}


if __name__ == "__main__":
    shared.run_step(team_goals)
