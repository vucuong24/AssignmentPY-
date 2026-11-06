"""Integration checks for the user's saved, full-league FBref snapshot."""
import json

import numpy as np
import pandas as pd
import pytest

from epl.common import sha256
from epl.fbref_pipeline import TABLES, FIGURES
from epl.fbref_scraper import OUTPUT

QUALITY = OUTPUT / "data_quality.json"
pytestmark = pytest.mark.skipif(
    not QUALITY.exists() or not json.loads(QUALITY.read_text(encoding="utf-8")).get("complete_league"),
    reason="Requires the complete user-supplied FBref snapshot",
)


def test_fbref_originals_and_identity():
    quality = json.loads(QUALITY.read_text(encoding="utf-8"))
    players = pd.read_csv(OUTPUT / "result.csv")
    assert quality["dataset_sha256"] == sha256(OUTPUT / "result.csv")
    assert quality["teams"] == quality["expected_teams"] == 20
    assert len(quality["raw_sources"]) == 20
    for source in quality["raw_sources"]:
        from pathlib import Path
        assert sha256(Path(source["file"])) == source["sha256"]
    assert players.PlayerID.is_unique
    assert players.Min.gt(90).all()
    assert players.Source.eq("FBref").all()
    assert players.Season.eq("2025-2026").all()
    assert not any("FPL" in column for column in players)


def test_fbref_stints_and_statistics_conserve_observations():
    players = pd.read_csv(OUTPUT / "result.csv").set_index("PlayerID")
    stints = pd.read_csv(OUTPUT / "player_team_stints.csv")
    assert stints.Squad.nunique() == stints.SquadID.nunique() == 20
    assert not stints.duplicated(["PlayerID", "SquadID"]).any()
    for column in ["Min", "Gls", "Ast", "MP", "Starts"]:
        total = stints.groupby("PlayerID")[column].sum().reindex(players.index)
        np.testing.assert_allclose(players[column], total)
    np.testing.assert_allclose(players["90s"], players.Min / 90)
    np.testing.assert_allclose(players.Gls_per90, players.Gls * 90 / players.Min)
    result = pd.read_csv(TABLES / "results2.csv")
    assert len(result) == 21 and result.Squad.iloc[0] == "all"
    goals = pd.read_csv(TABLES / "team_totals.csv").set_index("Squad").Gls
    np.testing.assert_allclose(goals.sort_index(), stints.groupby("Squad").Gls.sum().sort_index())
    tops = pd.read_csv(TABLES / "top3_bottom3.csv")
    assert tops.groupby(["Attribute", "Direction"]).size().eq(3).all()
    stats = pd.read_csv(TABLES / "league_statistics.csv").set_index("Attribute")
    for column in ["Min", "Gls", "Ast", "Age"]:
        np.testing.assert_allclose(stats.loc[column, ["median", "mean", "std"]].astype(float),
                                   players[column].agg(["median", "mean", "std"]))


def test_fbref_analysis_outputs_use_current_snapshot():
    quality = json.loads(QUALITY.read_text(encoding="utf-8"))
    for filename in ["statistics_status.json", "clustering_metrics.json", "radar_status.json",
                     "transfer_status.json", "valuation_status.json"]:
        status = json.loads((TABLES / filename).read_text(encoding="utf-8"))
        assert status["dataset_sha256"] == quality["dataset_sha256"]
    clustered = pd.read_csv(OUTPUT / "result_with_clusters.csv")
    assert clustered.PlayerID.is_unique and len(clustered) == quality["players_over_90"]
    assert clustered.Cluster.nunique() == 5
    assert np.isfinite(clustered[["PC1", "PC2"]]).all().all()
    assert len(list((FIGURES / "histograms").glob("*.png"))) == 63
    radar = pd.read_csv(TABLES / "radar_values.csv")
    assert radar.PlayerID.nunique() == 2
    assert radar.Percentile.between(0, 100).all()


def test_fbref_fee_holdout_and_metrics():
    state = json.loads((TABLES / "valuation_status.json").read_text(encoding="utf-8"))
    if state["status"] != "retrospective_only":
        pytest.skip("Insufficient real transfer observations for this snapshot")
    train = pd.read_csv(OUTPUT / "valuation_train.csv")
    test = pd.read_csv(OUTPUT / "valuation_test.csv")
    assert not set(train.FBrefPlayerID) & set(test.FBrefPlayerID)
    assert train.FeeEUR.ge(0).all() and test.FeeEUR.ge(0).all()
    metrics = pd.read_csv(TABLES / "valuation_metrics.csv").set_index("Model")
    assert metrics.TrainCV_MAE_EUR.idxmin() == state["selected_model"]
    predictions = pd.read_csv(TABLES / "valuation_predictions.csv")
    assert len(predictions) == len(test)
    np.testing.assert_allclose(predictions.FeeEUR, test.FeeEUR)
    for name in metrics.index:
        errors = predictions[name] - predictions.FeeEUR
        np.testing.assert_allclose(metrics.loc[name, "Test_MAE_EUR"], errors.abs().mean())
        np.testing.assert_allclose(metrics.loc[name, "Test_RMSE_EUR"], np.sqrt((errors**2).mean()))
