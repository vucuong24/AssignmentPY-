"""Bước 04. Chạy K-means, lưu tọa độ PCA và vẽ Elbow cùng Silhouette."""


import argparse
from importlib import import_module

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# Nạp các hàm dùng chung từ bước 01. Tên file có tiền tố số.
shared = import_module("01_thu_thap_du_lieu")


shared.configure_plotting()
import matplotlib.pyplot as plt


def clustering(k=5):
    shared.setup(shared.TABLES, shared.FIGURES, shared.MODELS)
    players, quality = shared.read_fbref()
    preferred = ["Age", "Min", "Gls_per90", "Ast_per90"]
    # Giữ đặc trưng có dữ liệu ở ít nhất 60% cầu thủ và có độ biến thiên.
    features = [c for c in preferred if c in players and players[c].notna().mean() >= .6 and players[c].nunique() > 1]
    if len(features) < 3 or not 2 <= k < len(players):
        raise ValueError("Không đủ đặc trưng/cầu thủ FBref cho K-means và PCA.")
    # Điền trung vị và đưa các chỉ số về cùng thang đo trước khi tính khoảng cách.
    preprocess = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    x = preprocess.fit_transform(players[features])
    if len(np.unique(x, axis=0)) < k:
        raise ValueError("Số bộ đặc trưng khác nhau ít hơn số cụm yêu cầu.")
    model = KMeans(n_clusters=k, random_state=42, n_init=20).fit(x)
    # PCA dùng để vẽ trên hai trục. Nhãn cụm vẫn lấy từ K-means trên dữ liệu chuẩn hóa.
    pca = PCA(n_components=2).fit(x)
    result = players.copy()
    result["Cluster"] = model.labels_
    result[["PC1", "PC2"]] = pca.transform(x)
    # Tính inertia và silhouette cho nhiều giá trị k để đối chiếu với cấu hình đã chọn.
    diagnostics = []
    for candidate in range(2, min(10, len(players)-1, len(np.unique(x, axis=0))-1)+1):
        trial = KMeans(n_clusters=candidate, random_state=42, n_init=20).fit(x)
        if len(set(trial.labels_)) > 1:
            diagnostics.append({"k": candidate, "inertia": float(trial.inertia_),
                                "silhouette": float(silhouette_score(x, trial.labels_))})
    diagnostic = pd.DataFrame(diagnostics, columns=["k", "inertia", "silhouette"])
    shared.save_csv(diagnostic, shared.TABLES / "kmeans_diagnostics.csv")
    shared.save_csv(result, shared.OUTPUT / "result_with_clusters.csv")
    profiles = result.groupby("Cluster")[features].mean()
    profiles.insert(0, "Count", result.groupby("Cluster").size())
    shared.save_csv(profiles, shared.TABLES / "cluster_profiles.csv", index=True)
    shared.save_csv(pd.DataFrame(pca.components_.T, index=features, columns=["PC1", "PC2"]), shared.TABLES / "pca_components.csv", index=True)
    if "Position" in result:
        shared.save_csv(pd.crosstab(result.Cluster, result.Position), shared.TABLES / "cluster_positions.csv", index=True)
    joblib.dump({"source": "FBref", "features": features, "preprocess": preprocess, "kmeans": model, "pca": pca}, shared.MODELS / "clustering.joblib")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(diagnostic.k, diagnostic.inertia, "o-")
    axes[0].set(title="Elbow", xlabel="k", ylabel="Inertia")
    axes[1].plot(diagnostic.k, diagnostic.silhouette, "o-")
    axes[1].set(title="Silhouette", xlabel="k", ylabel="Score")
    fig.tight_layout()
    fig.savefig(shared.FIGURES / "kmeans_diagnostics.png", dpi=160)
    plt.close(fig)
    summary = {"source": "FBref", "dataset_sha256": quality["dataset_sha256"], "k": k, "features": features,
               "silhouette": float(silhouette_score(x, model.labels_)),
               "pca_explained_variance": pca.explained_variance_ratio_.tolist(),
               "missing_features": [c for c in preferred if c not in features],
               "note": "Đặc trưng chỉ lấy từ FBref; cột thiếu toàn bộ/không biến động được loại, không thay bằng chỉ số FPL."}
    shared.save_json(shared.TABLES / "clustering_metrics.json", summary)
    return summary


def main(argv=None):
    shared.configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=5, help="Số cụm K-means")
    args = parser.parse_args(argv)
    shared.run_step(clustering, k=args.k)


if __name__ == "__main__":
    main()
