"""Bước 06. Vẽ bản đồ nhiệt tâm cụm trên thang đã chuẩn hóa."""


from importlib import import_module

import joblib
import pandas as pd
import seaborn as sns


# Nạp các hàm dùng chung từ bước 01. Tên file có tiền tố số.
shared = import_module("01_thu_thap_du_lieu")


shared.configure_plotting()
import matplotlib.pyplot as plt


def cluster_profiles():
    shared.read_step_status("clustering_metrics.json", "04_kmeans_elbow_silhouette.py")
    model = joblib.load(shared.MODELS / "clustering.joblib")
    shared.setup(shared.FIGURES)
    centers = model["kmeans"].cluster_centers_
    features = model["features"]
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.heatmap(pd.DataFrame(centers, columns=features), center=0, cmap="vlag", annot=True, fmt=".1f", ax=ax)
    ax.set(title="FBref: standardized cluster centers", ylabel="Cluster")
    path = shared.FIGURES / "cluster_profiles.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return {"figure": str(path)}


if __name__ == "__main__":
    shared.run_step(cluster_profiles)
