"""Bước 09. Đánh giá mô hình hồi cứu và vẽ phí thực tế so với phí ước lượng."""


from copy import deepcopy
from importlib import import_module

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# Nạp các hàm dùng chung từ bước 01. Tên file có tiền tố số.
shared = import_module("01_thu_thap_du_lieu")


shared.configure_plotting()
import matplotlib.pyplot as plt


def valuation():
    """Retrospective association only: season stats cannot forecast earlier transfer fees."""
    shared.setup(shared.TABLES, shared.FIGURES, shared.MODELS)
    transfer_status = shared.read_step_status("transfer_status.json", "08_ghep_chuyen_nhuong.py")
    path = shared.OUTPUT / "transfers_with_fbref.csv"
    if not path.exists():
        raise ValueError("Hãy chạy lại bước 08 để xuất bảng giao dịch đã ghép.")
    data = pd.read_csv(path, dtype={"FBrefPlayerID": str})
    valid = data[data.FBrefPlayerID.notna() & data.FeeEUR.notna() & data.FeeEUR.ge(0)].copy()
    features = [c for c in ["Age", "Min", "Gls", "Ast", "MP"]
                if c in valid and valid[c].notna().any() and valid[c].nunique() > 1]
    if len(valid) < 40 or valid.FBrefPlayerID.nunique() < 30 or len(features) < 3:
        status = {"status": "insufficient_original_data", "dataset_sha256": transfer_status["dataset_sha256"], "matched_rows": len(valid), "features": features,
                  "note": "Cần ít nhất 40 giao dịch, 30 cầu thủ và 3 đặc trưng thật. Không huấn luyện trên dữ liệu giả/FPL."}
        shared.save_json(shared.TABLES / "valuation_status.json", status)
        return status
    # Chia theo mã cầu thủ để các giao dịch của cùng một người không lọt vào cả hai tập.
    train_idx, test_idx = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=42).split(valid, groups=valid.FBrefPlayerID))
    train, test = valid.iloc[train_idx], valid.iloc[test_idx]
    # Đặt tiền xử lý trong Pipeline để mỗi lượt kiểm định chỉ học từ phần huấn luyện.
    preprocessing = [("imputer", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler())]
    # Mốc so sánh dùng phí trung vị. Ridge và Random Forest học trên log(1 + phí).
    models = {"Median": DummyRegressor(strategy="median"),
              "RidgeLog": Pipeline(deepcopy(preprocessing) + [("regressor", TransformedTargetRegressor(regressor=Ridge(alpha=10), func=np.log1p, inverse_func=np.expm1))]),
              "RandomForestLog": Pipeline(deepcopy(preprocessing) + [("regressor", TransformedTargetRegressor(
                  regressor=RandomForestRegressor(n_estimators=200, min_samples_leaf=4, n_jobs=1, random_state=42),
                  func=np.log1p, inverse_func=np.expm1))])}
    rows = []
    predictions = test[["TransferID", "FBrefPlayerID", "FeeEUR"]].copy()
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
    # Chọn mô hình theo MAE kiểm định chéo. Dùng tập kiểm tra để đo sai số ngoài mẫu.
    selected = str(metrics.loc[metrics.TrainCV_MAE_EUR.idxmin(), "Model"])
    shared.save_csv(metrics, shared.TABLES / "valuation_metrics.csv")
    shared.save_csv(predictions, shared.TABLES / "valuation_predictions.csv")
    shared.save_csv(train, shared.OUTPUT / "valuation_train.csv")
    shared.save_csv(test, shared.OUTPUT / "valuation_test.csv")
    fig, ax = plt.subplots(figsize=(8, 6))
    actual = predictions.FeeEUR / 1e6
    predicted = predictions[selected] / 1e6
    ax.scatter(actual, predicted, color="#245caa", alpha=.75)
    limit = max(float(actual.max()), float(predicted.max()), 1)
    ax.plot([0, limit], [0, limit], "--", color="#e8932e", label="Perfect agreement")
    ax.set(xlabel="Observed fee (million EUR)", ylabel="Estimated fee (million EUR)",
           title=f"FBref + FootballTransfers: retrospective test ({selected}, n={len(test)})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(shared.FIGURES / "valuation_predictions.png", dpi=160)
    plt.close(fig)
    joblib.dump({"source": "FBref + FootballTransfers", "model": models[selected], "features": features,
                 "purpose": "retrospective_association_only"}, shared.MODELS / "valuation.joblib")
    status = {"status": "retrospective_only", "dataset_sha256": transfer_status["dataset_sha256"], "train_rows": len(train), "test_rows": len(test),
              "player_overlap": len(set(train.FBrefPlayerID) & set(test.FBrefPlayerID)), "selected_model": selected,
              "features": features, "split": "GroupShuffleSplit theo cầu thủ; không phải chia theo thời gian",
              "warning": "Đặc trưng cả mùa có thể xảy ra sau giao dịch. Mô hình chỉ khảo sát liên hệ hồi cứu, không được đánh giá như dự báo phí trước chuyển nhượng. Muốn dự báo cần cào thêm các mùa trước và khóa mốc thời gian."}
    shared.save_json(shared.TABLES / "valuation_status.json", status)
    return status


if __name__ == "__main__":
    shared.run_step(valuation)
