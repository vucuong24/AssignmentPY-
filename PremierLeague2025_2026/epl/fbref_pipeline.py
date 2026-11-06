"""Statistics, clustering, transfer analysis and reports from saved FBref HTML."""
from __future__ import annotations

import base64
import html
import json
import platform
from importlib.metadata import version
from copy import deepcopy
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.compose import TransformedTargetRegressor
from sklearn.decomposition import PCA
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, silhouette_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .analysis import histogram, percentile_scores, resolve_player, team_leaders, top_bottom
from .common import RAW, TABLES, FIGURES, MODELS, REPORTS, canonical_club, normalized_name, now, save_csv, save_json, sha256
from .fbref_scraper import ADDITIVE, OUTPUT, collect_fbref
from .report import markdown_table
from .transfers import prepare_confirmed

def setup():
    for directory in [TABLES, FIGURES, MODELS, REPORTS]:
        directory.mkdir(parents=True, exist_ok=True)


def read_fbref():
    meta = OUTPUT / "data_quality.json"
    if not meta.exists():
        raise ValueError("Chưa có dữ liệu FBref gốc. Chạy fetch/prepare với --html-dir hoặc tải trực tiếp; không dùng result.csv FPL cũ.")
    quality = json.loads(meta.read_text(encoding="utf-8"))
    if quality.get("source") != "FBref":
        raise ValueError("Sai nguồn: quy trình này chỉ nhận dữ liệu FBref.")
    if quality.get("dataset_sha256") != sha256(OUTPUT / "result.csv"):
        raise ValueError("CSV FBref không khớp hash đã ghi; hãy chạy prepare lại từ HTML gốc.")
    return pd.read_csv(OUTPUT / "result.csv", dtype={"PlayerID": str}), quality


def statistics():
    setup()
    players, quality = read_fbref()
    stints = pd.read_csv(OUTPUT / "player_team_stints.csv", dtype={"PlayerID": str, "SquadID": str})
    columns = [c for c in players.select_dtypes("number") if c not in ["PlayerID", "SquadID"] and players[c].notna().any()]
    save_csv(top_bottom(players, columns), TABLES / "top3_bottom3.csv")
    save_csv(players[columns].agg(["median", "mean", "std"]).T.rename_axis("Attribute").reset_index(), TABLES / "league_statistics.csv")
    team = stints.groupby("Squad")[columns].agg(["median", "mean", "std"])
    team.columns = [f"{c}_{s}" for c, s in team.columns]
    league = pd.DataFrame([{f"{c}_{s}": getattr(players[c], s)() for c in columns for s in ["median", "mean", "std"]}], index=["all"])
    save_csv(pd.concat([league, team]).rename_axis("Squad"), TABLES / "results2.csv", index=True)
    sums = [c for c in ADDITIVE if c in columns]
    totals = stints.groupby("Squad")[sums].sum(min_count=1)
    save_csv(totals, TABLES / "team_totals.csv", index=True)
    age = stints.groupby("Squad")[["Age"]].mean() if "Age" in stints else pd.DataFrame()
    save_csv(team_leaders(totals, age), TABLES / "team_leaders.csv")
    histogram_count = 0
    plot_columns = [c for c in ["Age", "MP", "90s"] if c in players and players[c].notna().any()]
    # Reuse histogram only when its required columns exist; never invent missing age.
    if len(plot_columns) == 3:
        histogram(players, "All league", FIGURES / "histograms")
        for club, group in stints.groupby("Squad"):
            histogram(group, club, FIGURES / "histograms")
        histogram_count = len(plot_columns) * (quality["teams"] + 1)
    fig, ax = plt.subplots(figsize=(10, 7))
    totals.Gls.sort_values().plot.barh(ax=ax, color="#245caa")
    ax.set(title="FBref: goals of qualified player-team stints (2025/26)", xlabel="Goals", ylabel="")
    fig.tight_layout(); fig.savefig(FIGURES / "team_goals.png", dpi=160); plt.close(fig)
    status = {"source": "FBref", "dataset_sha256": quality["dataset_sha256"], "numeric_columns": columns, "histogram_count": histogram_count,
              "missing_histogram_columns": sorted(set(["Age", "MP", "90s"]) - set(plot_columns)),
              "note": "Tổng đội chỉ cộng chỉ số tích lũy; không cộng phần trăm hoặc tỷ lệ mỗi 90 phút."}
    save_json(TABLES / "statistics_status.json", status)
    return status


def clustering(k=5):
    setup()
    players, quality = read_fbref()
    preferred = ["Age", "Min", "Gls_per90", "Ast_per90"]
    features = [c for c in preferred if c in players and players[c].notna().mean() >= .6 and players[c].nunique() > 1]
    if len(features) < 3 or not 2 <= k < len(players):
        raise ValueError("Không đủ đặc trưng/cầu thủ FBref cho K-means và PCA.")
    preprocess = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    x = preprocess.fit_transform(players[features])
    if len(np.unique(x, axis=0)) < k:
        raise ValueError("Số bộ đặc trưng khác nhau ít hơn số cụm yêu cầu.")
    model = KMeans(n_clusters=k, random_state=42, n_init=20).fit(x)
    pca = PCA(n_components=2).fit(x)
    result = players.copy()
    result["Cluster"] = model.labels_
    result[["PC1", "PC2"]] = pca.transform(x)
    diagnostics = []
    for candidate in range(2, min(10, len(players)-1, len(np.unique(x, axis=0))-1)+1):
        trial = KMeans(n_clusters=candidate, random_state=42, n_init=20).fit(x)
        if len(set(trial.labels_)) > 1:
            diagnostics.append({"k": candidate, "inertia": float(trial.inertia_),
                                "silhouette": float(silhouette_score(x, trial.labels_))})
    diagnostic = pd.DataFrame(diagnostics)
    save_csv(diagnostic, TABLES / "kmeans_diagnostics.csv")
    save_csv(result, OUTPUT / "result_with_clusters.csv")
    profiles = result.groupby("Cluster")[features].mean()
    profiles.insert(0, "Count", result.groupby("Cluster").size())
    save_csv(profiles, TABLES / "cluster_profiles.csv", index=True)
    save_csv(pd.DataFrame(pca.components_.T, index=features, columns=["PC1", "PC2"]), TABLES / "pca_components.csv", index=True)
    if "Position" in result:
        save_csv(pd.crosstab(result.Cluster, result.Position), TABLES / "cluster_positions.csv", index=True)
    joblib.dump({"source": "FBref", "features": features, "preprocess": preprocess, "kmeans": model, "pca": pca}, MODELS / "clustering.joblib")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(diagnostic.k, diagnostic.inertia, "o-"); axes[0].set(title="Elbow", xlabel="k", ylabel="Inertia")
    axes[1].plot(diagnostic.k, diagnostic.silhouette, "o-"); axes[1].set(title="Silhouette", xlabel="k", ylabel="Score")
    fig.tight_layout(); fig.savefig(FIGURES / "kmeans_diagnostics.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.scatterplot(data=result, x="PC1", y="PC2", hue="Cluster", palette="tab10", ax=ax)
    ax.set(title="FBref: K-means projected into PCA", xlabel=f"PC1 ({pca.explained_variance_ratio_[0]:.1%})", ylabel=f"PC2 ({pca.explained_variance_ratio_[1]:.1%})")
    fig.tight_layout(); fig.savefig(FIGURES / "pca_clusters.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.heatmap(pd.DataFrame(model.cluster_centers_, columns=features), center=0, cmap="vlag", annot=True, fmt=".1f", ax=ax)
    ax.set(title="FBref: standardized cluster centers", ylabel="Cluster")
    fig.tight_layout(); fig.savefig(FIGURES / "cluster_profiles.png", dpi=160); plt.close(fig)
    summary = {"source": "FBref", "dataset_sha256": quality["dataset_sha256"], "k": k, "features": features,
               "silhouette": float(silhouette_score(x, model.labels_)),
               "pca_explained_variance": pca.explained_variance_ratio_.tolist(),
               "missing_features": [c for c in preferred if c not in features],
               "note": "Đặc trưng chỉ lấy từ FBref; cột thiếu toàn bộ/không biến động được loại, không thay bằng chỉ số FPL."}
    save_json(TABLES / "clustering_metrics.json", summary)
    return summary


def radar(p1=None, p2=None, attributes=None, same_position=True):
    setup()
    players, quality = read_fbref()
    players["WebName"] = players.Name
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
        closed = np.r_[values, values[0]]
        ax.plot(angles, closed, "o-", label=player.Name, color=color)
        ax.fill(angles, closed, color=color, alpha=.12)
        rows.extend({"PlayerID": player.PlayerID, "Name": player.Name, "Attribute": c,
                     "RawValue": float(player[c]), "Percentile": float(scores.loc[player.name, c]),
                     "ReferenceCount": len(reference)} for c in attributes)
    ax.set_xticks(angles[:-1], attributes); ax.tick_params(axis="x", pad=14, labelsize=9)
    ax.set_ylim(0, 100); ax.set_title("FBref: percentile comparison", pad=30)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.12))
    fig.tight_layout(); fig.savefig(FIGURES / "radar.png", dpi=160, bbox_inches="tight"); plt.close(fig)
    save_csv(pd.DataFrame(rows), TABLES / "radar_values.csv")
    status = {"source": "FBref", "dataset_sha256": quality["dataset_sha256"], "players": [a.Name, b.Name], "attributes": attributes, "reference_count": len(reference)}
    save_json(TABLES / "radar_status.json", status)
    return status


def transfers():
    setup()
    players, quality = read_fbref()
    stints = pd.read_csv(OUTPUT / "player_team_stints.csv", dtype={"PlayerID": str, "SquadID": str})
    raw = RAW / "footballtransfers_2025_2026.json"
    if not raw.exists():
        raise ValueError("Chưa có bản lưu giao dịch gốc FootballTransfers. Quy trình hiện tại chỉ đọc tệp, không tự truy cập URL.")
    provenance = raw.with_suffix(".json.source.json")
    if not provenance.exists() or json.loads(provenance.read_text(encoding="utf-8")).get("sha256") != sha256(raw):
        raise ValueError("JSON FootballTransfers thiếu nguồn/hash hợp lệ; tải lại từ trang gốc.")
    records = json.loads(raw.read_text(encoding="utf-8"))
    confirmed, excluded = prepare_confirmed(records, set(stints.Squad))
    save_csv(confirmed, OUTPUT / "transfer_values.csv")
    save_csv(excluded, TABLES / "excluded_transfers.csv")
    lookup = {}
    for _, row in players.iterrows():
        lookup.setdefault(normalized_name(row.Name), []).append(row.PlayerID)
    confirmed["FBrefPlayerID"] = confirmed.Name.map(lambda name: lookup.get(normalized_name(name), [None])[0]
                                                     if len(lookup.get(normalized_name(name), [])) == 1 else None)
    membership = stints.groupby("PlayerID").Squad.agg(set).to_dict()
    for index, row in confirmed[confirmed.FBrefPlayerID.notna()].iterrows():
        known = membership.get(str(row.FBrefPlayerID), set())
        if not known.intersection({canonical_club(row.ClubFrom), canonical_club(row.ClubTo)}):
            confirmed.at[index, "FBrefPlayerID"] = None
    joined = confirmed.merge(players, left_on="FBrefPlayerID", right_on="PlayerID", how="left",
                             suffixes=("_Transfer", "_FBref"), validate="many_to_one")
    save_csv(joined, OUTPUT / "transfers_with_fbref.csv")
    status = {"source": "FootballTransfers direct + FBref", "dataset_sha256": quality["dataset_sha256"], "raw_transfers": len(records),
              "included": len(confirmed), "matched_by_unique_name_and_club": int(confirmed.FBrefPlayerID.notna().sum()),
              "unknown_fees": int(confirmed.FeeEUR.isna().sum()),
              "raw_file_sha256": sha256(raw),
              "note": "Ghép chính xác tên chuẩn hóa duy nhất và kiểm tra đội; không ghép mờ, không dùng giá FPL."}
    save_json(TABLES / "transfer_status.json", status)
    return status


def valuation():
    """Retrospective association only: season stats cannot forecast earlier transfer fees."""
    setup()
    _, quality = read_fbref()
    transfer_state = TABLES / "transfer_status.json"
    if not transfer_state.exists() or json.loads(transfer_state.read_text(encoding="utf-8")).get("dataset_sha256") != quality["dataset_sha256"]:
        raise ValueError("Cần chạy transfers cho đúng tập FBref hiện tại trước khi mô hình hóa phí.")
    path = OUTPUT / "transfers_with_fbref.csv"
    if not path.exists():
        raise ValueError("Chạy transfers để lấy giao dịch trực tiếp và ghép FBref trước.")
    data = pd.read_csv(path, dtype={"FBrefPlayerID": str})
    valid = data[data.FBrefPlayerID.notna() & data.FeeEUR.notna() & data.FeeEUR.ge(0)].copy()
    features = [c for c in ["Age", "Min", "Gls", "Ast", "MP"]
                if c in valid and valid[c].notna().any() and valid[c].nunique() > 1]
    if len(valid) < 40 or valid.FBrefPlayerID.nunique() < 30 or len(features) < 3:
        status = {"status": "insufficient_original_data", "dataset_sha256": quality["dataset_sha256"], "matched_rows": len(valid), "features": features,
                  "note": "Cần ít nhất 40 giao dịch, 30 cầu thủ và 3 đặc trưng thật. Không huấn luyện trên dữ liệu giả/FPL."}
        save_json(TABLES / "valuation_status.json", status)
        return status
    train_idx, test_idx = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=42).split(valid, groups=valid.FBrefPlayerID))
    train, test = valid.iloc[train_idx], valid.iloc[test_idx]
    preprocessing = [("imputer", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler())]
    models = {"Median": DummyRegressor(strategy="median"),
              "RidgeLog": Pipeline(deepcopy(preprocessing) + [("regressor", TransformedTargetRegressor(regressor=Ridge(alpha=10), func=np.log1p, inverse_func=np.expm1))]),
              "RandomForestLog": Pipeline(deepcopy(preprocessing) + [("regressor", TransformedTargetRegressor(
                  regressor=RandomForestRegressor(n_estimators=200, min_samples_leaf=4, n_jobs=1, random_state=42),
                  func=np.log1p, inverse_func=np.expm1))])}
    rows = []; predictions = test[["TransferID", "FBrefPlayerID", "FeeEUR"]].copy()
    for name, model in models.items():
        score = -cross_val_score(model, train[features], train.FeeEUR, groups=train.FBrefPlayerID,
                                 cv=GroupKFold(3), scoring="neg_mean_absolute_error")
        model.fit(train[features], train.FeeEUR)
        prediction = np.maximum(0, model.predict(test[features]))
        predictions[name] = prediction
        rows.append({"Model": name, "TrainCV_MAE_EUR": float(score.mean()),
                     "Test_MAE_EUR": float(mean_absolute_error(test.FeeEUR, prediction)),
                     "Test_RMSE_EUR": float(np.sqrt(mean_squared_error(test.FeeEUR, prediction))),
                     "Test_R2": float(r2_score(test.FeeEUR, prediction))})
    metrics = pd.DataFrame(rows)
    selected = str(metrics.loc[metrics.TrainCV_MAE_EUR.idxmin(), "Model"])
    save_csv(metrics, TABLES / "valuation_metrics.csv"); save_csv(predictions, TABLES / "valuation_predictions.csv")
    save_csv(train, OUTPUT / "valuation_train.csv"); save_csv(test, OUTPUT / "valuation_test.csv")
    fig, ax = plt.subplots(figsize=(8, 6))
    actual = predictions.FeeEUR / 1e6
    predicted = predictions[selected] / 1e6
    ax.scatter(actual, predicted, color="#245caa", alpha=.75)
    limit = max(float(actual.max()), float(predicted.max()), 1)
    ax.plot([0, limit], [0, limit], "--", color="#e8932e", label="Perfect agreement")
    ax.set(xlabel="Observed fee (million EUR)", ylabel="Estimated fee (million EUR)",
           title=f"FBref + FootballTransfers: retrospective test ({selected}, n={len(test)})")
    ax.legend(); fig.tight_layout()
    fig.savefig(FIGURES / "valuation_predictions.png", dpi=160); plt.close(fig)
    joblib.dump({"source": "FBref + FootballTransfers", "model": models[selected], "features": features,
                 "purpose": "retrospective_association_only"}, MODELS / "valuation.joblib")
    status = {"status": "retrospective_only", "dataset_sha256": quality["dataset_sha256"], "train_rows": len(train), "test_rows": len(test),
              "player_overlap": len(set(train.FBrefPlayerID) & set(test.FBrefPlayerID)), "selected_model": selected,
              "features": features, "split": "GroupShuffleSplit theo cầu thủ; không phải chia theo thời gian",
              "warning": "Đặc trưng cả mùa có thể xảy ra sau giao dịch. Mô hình chỉ khảo sát liên hệ hồi cứu, không được đánh giá như dự báo phí trước chuyển nhượng. Muốn dự báo cần cào thêm các mùa trước và khóa mốc thời gian."}
    save_json(TABLES / "valuation_status.json", status)
    return status


def report_glossary(players):
    """Describe only columns with observations in the current player dataset."""
    definitions = [
        (["PlayerID", "SquadID"], "Mã định danh từ nguồn; dùng ghép dữ liệu, không dùng làm đặc trưng thành tích."),
        (["Name", "Nation", "Position", "Squad"], "Tên cầu thủ, quốc tịch, vị trí và đội; cầu thủ nhiều đội được ghép theo PlayerID."),
        (["Age"], "Tuổi hiển thị trong HTML FBref, không phải tuổi tự tính tại một ngày tham chiếu."),
        (["MP", "Starts", "Min"], "Số trận ra sân, số trận đá chính và tổng phút thi đấu. MP cộng theo cầu thủ là lượt ra sân, không phải số trận CLB."),
        (["90s"], "Số trận 90 phút quy đổi = Min/90."),
        (["Gls", "Ast", "G+A"], "Bàn thắng, kiến tạo và tổng hai chỉ số theo FBref."),
        (["G-PK"], "Bàn thắng không tính bàn từ phạt đền."),
        (["PK", "PKatt"], "Số bàn phạt đền và số lần thực hiện phạt đền."),
        (["CrdY", "CrdR"], "Thẻ vàng và thẻ đỏ; giá trị cao không phải thành tích tốt."),
        (["Sh", "SoT"], "Tổng cú sút và số cú sút trúng đích."),
        (["Saves"], "Số lần cứu thua của thủ môn; không có dữ liệu không được hiểu là 0."),
        (["CleanSheets"], "Số trận sạch lưới theo cầu thủ thủ môn; tổng theo nhóm cầu thủ không mặc nhiên là số trận sạch lưới chính thức của CLB."),
    ]
    rows = []
    for columns, description in definitions:
        observed = [column for column in columns if column in players and players[column].notna().any()]
        if observed:
            rows.append([" / ".join(observed), description])
    if any(column.endswith("_per90") and players[column].notna().any() for column in players):
        rows.append(["*_per90", "Chỉ số tích lũy mỗi 90 phút = tổng chỉ số ×90/Min; ít phút làm tỷ lệ biến động lớn. Không cộng các tỷ lệ giữa các đội."])
    rows.append(["Median / Mean / Std", "Trung vị, trung bình và độ lệch chuẩn mẫu ddof=1; Std có cùng đơn vị với chỉ số gốc."])
    return pd.DataFrame(rows, columns=["Chỉ số", "Ý nghĩa và lưu ý"])


def report():
    setup()
    players, quality = read_fbref()
    for required_status in ["statistics_status.json", "clustering_metrics.json"]:
        path = TABLES / required_status
        if not path.exists() or json.loads(path.read_text(encoding="utf-8")).get("dataset_sha256") != quality["dataset_sha256"]:
            raise ValueError("Bảng/hình chưa khớp dữ liệu FBref hiện tại. Chạy stats và cluster trước report.")
    md = ["# PHÂN TÍCH CẦU THỦ PREMIER LEAGUE 2025-2026 TỪ FBREF GỐC", ""]
    body = []
    def section(title, paragraphs=(), table=None, images=()):
        md.extend([f"## {title}", ""]); body.append(f"<h2>{html.escape(title)}</h2>")
        for text in paragraphs:
            md.extend([text, ""]); body.append(f"<p>{html.escape(text)}</p>")
        if table is not None:
            md.extend([markdown_table(table), ""]); body.append(table.to_html(index=False, border=0, escape=True))
        for filename, caption, guides in images:
            path = FIGURES / filename
            if not path.exists():
                continue
            md.extend([f"![{caption}](../figures/{filename})", ""])
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            body.append(f"<figure><img src='data:image/png;base64,{encoded}'><figcaption>{html.escape(caption)}</figcaption></figure>")
            for text in guides:
                md.extend([text, ""]); body.append(f"<p>{html.escape(text)}</p>")
    section("1. Nội dung, bài toán và yêu cầu", [
        "Phân tích thành tích cầu thủ/đội, thống kê phân phối, tìm nhóm cầu thủ tương đồng và khảo sát phí chuyển nhượng. Bài 1: tự thu thập HTML FBref, chuẩn hóa và lọc tổng phút >90. Bài 2: top/bottom 3, median/mean/std, histogram, đội dẫn đầu. Bài 3: K-means, PCA và radar. Bài 4: giao dịch trực tiếp FootballTransfers và minh họa mô hình phí nếu đủ dữ liệu thật.",
        f"Nguồn thống kê: FBref, mùa {quality['season']}. Thu được {quality['teams']}/20 đội, {len(players)} cầu thủ đủ điều kiện, {quality['stints']} stint. Trạng thái: {'ĐỦ 20 ĐỘI' if quality['complete_league'] else 'DỮ LIỆU MỘT PHẦN - CHƯA ĐẠI DIỆN TOÀN GIẢI'}.",
        "Không tải FPL, không dùng CSV tổng hợp của bên thứ ba và không tạo dữ liệu thay cho phần thiếu. HTML do người dùng lưu vẫn là nội dung gốc FBref; phương thức thu thập được ghi ở cuối báo cáo.",
        "Báo cáo chỉ trình bày những chỉ số có quan sát trong tập dữ liệu hiện tại. Dữ liệu chưa có không được tự điền 0. Tuổi dùng giá trị hiển thị trong bảng FBref."])
    section("2. Từ điển các chỉ số thực tế thu được", table=report_glossary(players))
    section("3. Thống kê và biểu đồ", [
        "Top/bottom lấy 3 dòng mỗi chỉ số, đồng hạng sắp tên rồi ID. Tổng mùa dùng PlayerID duy nhất; từng đội dùng stint để tránh gán toàn mùa cho đội cuối. Tỷ lệ và phần trăm không cộng giữa đội. Tổng bàn của nhóm cầu thủ được chọn không phải bảng bàn thắng chính thức CLB."],
        table=pd.read_csv(TABLES / "top3_bottom3.csv").query("Attribute == 'Gls'")[["Direction", "Rank", "Name", "Squad", "Value"]],
        images=[("team_goals.png", "Tổng bàn của cầu thủ đủ điều kiện theo đội", ["Mục đích: so sánh đóng góp ghi bàn giữa các đội. Trục dọc là đội, ngang là bàn; thanh dài hơn là nhiều bàn hơn. Chỉ cộng cầu thủ đủ điều kiện theo stint, không kể bàn phản lưới đối thủ."])])
    top = pd.read_csv(TABLES / "top3_bottom3.csv")
    summary_columns = [c for c in ["Age", "Min", "MP", "Gls", "Ast", "Gls_per90", "Ast_per90"] if c in players]
    league_stats = pd.read_csv(TABLES / "league_statistics.csv")
    section("3.1. Trả lời Bài 2: kết quả nổi bật", [
        "Bảng dưới trình bày ba cầu thủ đứng đầu về bàn thắng và kiến tạo. Toàn bộ top/bottom 3 cho mọi chỉ số có trong top3_bottom3.csv; kết quả theo toàn giải và 20 đội có trong results2.csv.",
        "Số liệu này chỉ mô tả các HTML đã lưu, không tự xác nhận thời điểm cập nhật hoặc độ đầy đủ của từng trang trên website."],
        table=top[top.Attribute.isin(["Gls", "Ast"]) & top.Direction.eq("top")][["Attribute", "Rank", "Name", "Squad", "Value"]])
    section("3.2. Thống kê toàn giải", table=league_stats[league_stats.Attribute.isin(summary_columns)].round(4))
    leaders = pd.read_csv(TABLES / "team_leaders.csv")
    leaders = leaders[leaders.Attribute.isin(["Gls", "Ast", "Sh", "SoT", "CrdY", "CrdR", "Saves", "CleanSheets", "Age"])].copy()
    leaders.Aggregation = leaders.Aggregation.map({"sum_of_qualified_player_stints": "Tổng", "mean_of_qualified_player_stints": "Trung bình"})
    section("3.3. Đội dẫn đầu theo chỉ số", [
        "Giữ mọi đội đồng hạng. Age dùng tuổi trung bình; các chỉ số còn lại dùng tổng của cầu thủ đủ điều kiện. MP cộng theo cầu thủ là lượt ra sân, không phải số trận của CLB. Thẻ phạt cao không có nghĩa là thành tích tốt."], table=leaders.round(3))
    histogram_guides = ["Mục đích: quan sát cơ cấu và độ phân tán. Trục ngang là tuổi/số trận/90s; trục dọc là số cầu thủ trong mỗi khoảng (bin), không là tổng chỉ số. Đường KDE chỉ làm mượt phân phối, không là dự báo. 90s=Min/90, MP là số lần ra sân. Các hình đội dùng cùng cách đọc với cỡ mẫu stint của đội."]
    histogram_status = json.loads((TABLES / "statistics_status.json").read_text(encoding="utf-8"))
    radar_status_path = TABLES / "radar_status.json"
    has_radar = radar_status_path.exists() and json.loads(radar_status_path.read_text(encoding="utf-8")).get("dataset_sha256") == quality["dataset_sha256"]
    section("4. Histogram và radar", images=[
        (f"histograms/all_league_{field}.png", f"Phân phối {field} toàn bộ tập dữ liệu", histogram_guides)
        for field in ["Age", "MP", "90s"] if histogram_status["histogram_count"]] + ([("radar.png", "So sánh percentile hai cầu thủ", [
            "Mục đích: so sánh nhiều khía cạnh trên cùng thang 0-100. Tên cạnh các tia là chỉ số; mỗi màu là một cầu thủ trong chú giải. Bán kính là hạng trung bình chia cỡ nhóm tham chiếu ×100, không phải số bàn/phút gốc.",
            "Điểm xa tâm là giá trị tương đối lớn hơn; không lấy diện tích đa giác làm điểm chất lượng. Thẻ phạt lớn không phải ưu điểm. File radar_values.csv chứa giá trị gốc, percentile và cỡ nhóm."])] if has_radar else []))
    cm = json.loads((TABLES / "clustering_metrics.json").read_text(encoding="utf-8"))
    section("5. K-means, PCA và tâm cụm", [
        f"Đặc trưng thực có: {', '.join(cm['features'])}. k={cm['k']}; silhouette={cm['silhouette']:.4f}; PCA 2D giữ {sum(cm['pca_explained_variance']):.2%} phương sai. Cột thiếu/không biến động bị loại trước khi chuẩn hóa."],
        table=pd.read_csv(TABLES / "cluster_profiles.csv"), images=[
            ("kmeans_diagnostics.png", "Elbow và Silhouette", ["Mục đích: đối chiếu số cụm k. Elbow có trục ngang k, dọc Inertia = tổng bình phương khoảng cách tới tâm cụm trên thang chuẩn hóa; tìm đoạn gãy, không chỉ chọn giá trị nhỏ nhất. Silhouette có thang [-1,1], gần 1 tách rõ, gần 0 sát ranh giới, âm có thể gán cụm chưa phù hợp; s=(b-a)/max(a,b)."]),
            ("pca_clusters.png", "Cầu thủ trên mặt phẳng PCA", ["Mỗi chấm là một cầu thủ; màu là mã K-means, không là thứ hạng. PC1/PC2 là tổ hợp tuyến tính các chỉ số chuẩn hóa; phần trăm cạnh trục là phương sai giữ lại. Chồng điểm có thể do mất thông tin khi chiếu, không chứng minh cầu thủ hoàn toàn giống nhau."]),
            ("cluster_profiles.png", "Bản đồ nhiệt tâm cụm", ["Hàng là cụm, cột là đặc trưng. Số trong ô là tâm trên thang z=(x-mean)/std do StandardScaler tính với ddof=0. Đỏ/dương cao hơn trung bình, xanh/âm thấp hơn; z=1 tương ứng một độ lệch chuẩn, không phải thêm một bàn. Đỏ không luôn tốt, cần đọc theo ý nghĩa chỉ số."])])
    profiles = pd.read_csv(TABLES / "cluster_profiles.csv")
    interpretations = []
    if all(c in profiles for c in ["Age", "Min", "Gls_per90", "Ast_per90"]):
        for field, description in [("Age", "tuổi trung bình cao nhất"), ("Min", "thời gian thi đấu trung bình cao nhất"),
                                   ("Gls_per90", "bàn/90 trung bình cao nhất"), ("Ast_per90", "kiến tạo/90 trung bình cao nhất")]:
            row = profiles.loc[profiles[field].idxmax()]
            interpretations.append(f"Cụm {int(row.Cluster)} có {description}: {row[field]:.3f}, gồm {int(row.Count)} cầu thủ.")
    interpretations.append("Các mô tả dựa trên trung bình cụm, không gán nhãn vị trí hoặc chất lượng. Chỉ số mỗi 90 phút của cầu thủ ít phút dễ biến động; kết quả phụ thuộc tập đặc trưng còn lại trong nguồn.")
    section("5.1. Trả lời Bài 3: diễn giải phân cụm", interpretations)
    if has_radar:
        radar_state = json.loads(radar_status_path.read_text(encoding="utf-8"))
        section("5.2. So sánh hai cầu thủ bằng radar", [
            f"So sánh {' và '.join(radar_state['players'])} trong nhóm {radar_state['reference_count']} cầu thủ cùng vị trí. Mỗi chỉ số có giá trị gốc và percentile dưới đây; percentile biểu thị giá trị tương đối, không phải xác suất thắng."],
            table=pd.read_csv(TABLES / "radar_values.csv")[["Name", "Attribute", "RawValue", "Percentile"]].round(3))
    transfer_state = TABLES / "transfer_status.json"
    model_state = TABLES / "valuation_status.json"
    notes = []
    if transfer_state.exists() and json.loads(transfer_state.read_text(encoding="utf-8")).get("dataset_sha256") == quality["dataset_sha256"]:
        state = json.loads(transfer_state.read_text(encoding="utf-8"))
        notes.append(f"FootballTransfers gốc: {state['included']} giao dịch trong phạm vi; ghép được {state['matched_by_unique_name_and_club']} theo tên duy nhất và đội. FeeEUR là phí EUR; miễn phí là 0, chưa biết là thiếu. Không dùng giá FPL.")
    else:
        notes.append("Chưa có giao dịch trực tiếp được xử lý cho tập FBref này; không dùng mô hình FPL cũ.")
    if model_state.exists() and json.loads(model_state.read_text(encoding="utf-8")).get("dataset_sha256") == quality["dataset_sha256"]:
        state = json.loads(model_state.read_text(encoding="utf-8"))
        if state.get("status") == "insufficient_original_data":
            notes.append(f"Chưa huấn luyện mô hình phí: chỉ ghép được {state['matched_rows']} giao dịch có nhãn thật. Cần ít nhất 40 giao dịch, 30 cầu thủ và 3 đặc trưng có giá trị. Không tạo dữ liệu giả để bù phần thiếu.")
        elif state.get("status") == "retrospective_only":
            notes.append(f"Mô hình hồi cứu: {state['selected_model']}; train {state['train_rows']} giao dịch, test {state['test_rows']} giao dịch; tách theo cầu thủ, không tách theo thời gian. Đặc trưng đầu vào thực tế: {', '.join(state['features'])}. {state['warning']}")
        else:
            notes.append("Phần mô hình phí đang thiếu dữ liệu gốc: " + state.get("reason", "cần bổ sung đầu vào"))
    notes.extend([
        "MAE là trung bình trị tuyệt đối sai số phí; RMSE là căn trung bình sai số bình phương, phạt lỗi lớn mạnh hơn; cả hai tính EUR, thấp hơn là tốt hơn. R²=1-SSE/SST; âm nghĩa kém hơn mốc trung bình test theo sai số bình phương, không phải tỷ lệ dự đoán đúng.",
        "Nếu chỉ có thành tích cả mùa 2025-2026 và phí giao dịch trong mùa, mô hình chỉ khảo sát liên hệ hồi cứu vì thành tích có thể xảy ra sau giao dịch. Muốn đánh giá dự báo trước giao dịch phải thu thêm mùa trước và khóa mốc thời gian; không được trình bày kết quả hồi cứu thành dự báo tương lai."])
    section("6. Chuyển nhượng và mô hình phí", notes)
    metrics_path = TABLES / "valuation_metrics.csv"
    has_metrics = metrics_path.exists() and model_state.exists() and json.loads(model_state.read_text(encoding="utf-8")).get("status") == "retrospective_only" and json.loads(model_state.read_text(encoding="utf-8")).get("dataset_sha256") == quality["dataset_sha256"]
    if has_metrics:
        metrics = pd.read_csv(metrics_path)
        state = json.loads(model_state.read_text(encoding="utf-8"))
        selected = metrics.set_index("Model").loc[state["selected_model"]]
        baseline = metrics.set_index("Model").loc["Median"]
        metric_display = metrics.copy()
        for field in ["TrainCV_MAE_EUR", "Test_MAE_EUR", "Test_RMSE_EUR"]:
            metric_display[field] /= 1e6
        metric_display = metric_display.rename(columns={c: c.replace("_EUR", "_million_EUR") for c in metric_display})
        section("7. Trả lời Bài 4: kết quả kiểm định hồi cứu", [
            f"Chọn {state['selected_model']} bằng MAE kiểm định chéo trên train. Test MAE={selected.Test_MAE_EUR/1e6:.3f} triệu EUR; RMSE={selected.Test_RMSE_EUR/1e6:.3f} triệu EUR; R²={selected.Test_R2:.4f}. Baseline median có MAE={baseline.Test_MAE_EUR/1e6:.3f} triệu EUR.",
            "Các cột MAE/RMSE trong bảng dùng triệu EUR. Sai số còn lớn; kết quả chỉ minh họa liên hệ giữa thành tích và phí trong dữ liệu đã ghép. Chưa đủ dữ liệu mùa trước để hoàn thành một bộ dự báo phí trước giao dịch có kiểm định theo thời gian."],
            table=metric_display.round(4), images=[("valuation_predictions.png", "Phí thực tế và phí ước lượng trên test hồi cứu", [
                "Mỗi điểm là một giao dịch trong test; cả hai trục dùng triệu EUR. Đường chéo thể hiện ước lượng bằng phí thực tế; điểm dưới đường là ước lượng thấp, trên đường là cao. Đây là tập test tách theo cầu thủ, không phải dự báo giao dịch tương lai."])])
    provenance = pd.DataFrame(quality["raw_sources"])[["URL", "method", "sha256"]]
    provenance["sha256"] = provenance.sha256.str[:16]
    provenance = provenance.rename(columns={"sha256": "SHA256_prefix_16"})
    source_section = 8 if has_metrics else 7
    section(f"{source_section}. Nguồn gốc dữ liệu", [f"Tạo lúc {now()}. Các phân tích và mô hình chỉ sử dụng dữ liệu đã trích xuất thực tế. Giữ HTML gốc, data_quality.json và table_rows.csv để đối chiếu. Bảng trình bày 16 ký tự đầu SHA-256; hash đầy đủ nằm trong data_quality.json và run_manifest.json."], table=provenance)
    availability = pd.DataFrame([{"Squad": item["Squad"], "ExtractedTables": ", ".join(k for k,v in item["tables"].items() if v), "PlayerRowsBeforeFilter": item["rows"]} for item in quality["team_tables"]])
    section(f"{source_section+1}. Các bảng thực tế đã trích xuất theo đội", ["Số hồ sơ trong bảng là số dòng cầu thủ ở bảng standard trước khi lọc tổng phút >90; có thể gồm cầu thủ chưa thi đấu và cùng cầu thủ đăng ký ở nhiều đội."], table=availability)
    # Keep all club histograms accessible in the self-contained HTML without
    # adding sixty near-identical pages to the PDF.
    histogram_files = sorted((FIGURES / "histograms").glob("*.png"))
    save_csv(pd.DataFrame({"Figure": [p.name for p in histogram_files]}), TABLES / "histogram_index.csv")
    body.append("<h2>Phụ lục: toàn bộ histogram theo đội và toàn giải</h2>")
    for path in histogram_files:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        body.append(f"<details><summary>{html.escape(path.stem)}</summary><img loading='lazy' src='data:image/png;base64,{encoded}' alt='{html.escape(path.stem)}'></details>")
    (REPORTS / "BAO_CAO.md").write_text("\n".join(md), encoding="utf-8")
    (REPORTS / "BAO_CAO.html").write_text("<!doctype html><html lang='vi'><meta charset='utf-8'><title>FBref Premier League</title><style>body{font:16px/1.6 Arial;max-width:1100px;margin:auto;padding:30px}table{border-collapse:collapse;width:100%;font-size:12px}td,th{border-bottom:1px solid #ccc;padding:8px;overflow-wrap:anywhere}img{max-width:100%}h2{margin-top:35px;color:#193044}</style><h1>Phân tích Premier League từ FBref gốc</h1>"+"".join(body)+"</html>", encoding="utf-8")
    from .pdf_report import build_pdf
    build_pdf(REPORTS, source_description="Nguồn: HTML gốc FBref; bản lưu dữ liệu gốc FootballTransfers nếu có. Chỉ đọc tệp cục bộ, không dùng dữ liệu FPL.",
              appendix_description="Chi tiết nguồn, số đội và bảng thiếu được ghi trong báo cáo và data_quality.json.")
    return {"source": "FBref", "pdf": str(REPORTS / "BAO_CAO.pdf"), "complete_league": quality["complete_league"]}


def run_all(args):
    quality = collect_fbref(html_dir=args.html_dir, allow_partial=args.allow_partial)
    results = {"collection": quality}
    results["statistics"] = statistics()
    results["clustering"] = clustering()
    results["radar"] = radar()
    try:
        results["transfers"] = transfers()
        results["valuation"] = valuation()
    except ValueError as error:
        save_json(TABLES / "valuation_status.json", {"status": "needs_original_transfer_data", "dataset_sha256": quality["dataset_sha256"], "reason": str(error)})
        results["valuation"] = {"status": "needs_original_transfer_data", "reason": str(error)}
    results["report"] = report()
    save_json(REPORTS / "run_manifest.json", {
        "source": "FBref browser-saved HTML + FootballTransfers saved JSON", "created_at": now(),
        "python": platform.python_version(), "html_dir": str(args.html_dir.resolve()),
        "dataset_sha256": quality["dataset_sha256"], "raw_sources": quality["raw_sources"],
        "versions": {name: version(name) for name in ["pandas", "numpy", "scikit-learn", "matplotlib", "reportlab"]},
        "results": {key: value for key, value in results.items() if key != "collection"},
    })
    return results
