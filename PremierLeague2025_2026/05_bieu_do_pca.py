"""Bước 05. Vẽ các cầu thủ trên hai trục PCA đã tính ở bước 04."""


from importlib import import_module

import pandas as pd
import seaborn as sns


# Nạp các hàm dùng chung từ bước 01. Tên file có tiền tố số.
shared = import_module("01_thu_thap_du_lieu")


shared.configure_plotting()
import matplotlib.pyplot as plt


def pca_clusters():
    status = shared.read_step_status("clustering_metrics.json", "04_kmeans_elbow_silhouette.py")
    result = pd.read_csv(shared.OUTPUT / "result_with_clusters.csv", usecols=["PC1", "PC2", "Cluster"])
    shared.setup(shared.FIGURES)
    variance = status["pca_explained_variance"]
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.scatterplot(data=result, x="PC1", y="PC2", hue="Cluster", palette="tab10", ax=ax)
    ax.set(title="FBref: K-means projected into PCA", xlabel=f"PC1 ({variance[0]:.1%})",
           ylabel=f"PC2 ({variance[1]:.1%})")
    path = shared.FIGURES / "pca_clusters.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return {"figure": str(path)}


if __name__ == "__main__":
    shared.run_step(pca_clusters)
