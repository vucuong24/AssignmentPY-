"""Regression checks for fees, club names, percentiles and team leaders."""
import numpy as np
import pandas as pd

from epl.analysis import percentile_scores, team_leaders
from epl.transfers import confirmed_fee, prepare_confirmed


def test_unknown_fee_is_not_free_and_display_rounding_is_not_used():
    assert np.isnan(confirmed_fee({"unknown": 1, "free": 0, "price_tag": {"value": 0}}))
    assert confirmed_fee({"free": 1, "disclosed": 1}) == 0
    assert confirmed_fee({"amount": "€0.8M", "price_tag": {"value": 750000}, "disclosed": 1}) == 750000
    assert np.isnan(confirmed_fee({"amount": "Loan", "price_tag": {"value": 0}}))


def test_confirmed_filters_wrong_season_date_and_wrong_clubs():
    rows = [
        {"id": 1, "player_name": "A", "club_from_short_name": "Man City", "club_to_short_name": "Liverpool", "date_transfer": "2025-07-01", "free": 1},
        {"id": 2, "player_name": "B", "club_from_short_name": "Man City", "club_to_short_name": "Liverpool", "date_transfer": "2026-07-01", "free": 1},
        {"id": 3, "player_name": "C", "club_from_short_name": "Hull", "club_to_short_name": "Ipswich", "date_transfer": "2025-07-01", "free": 1},
    ]
    kept, excluded = prepare_confirmed(rows, {"Manchester City", "Liverpool"})
    assert kept.TransferID.tolist() == [1]
    assert len(excluded) == 2


def test_footballtransfers_short_names_do_not_exclude_premier_league_clubs():
    rows = [{"id": i, "player_name": "A", "club_from_short_name": name,
             "club_to_short_name": "Real Madrid", "date_transfer": "2025-07-01", "free": 1}
            for i, name in enumerate(["A. Villa", "N. Forest", "B'mouth", "C. Palace"])]
    kept, excluded = prepare_confirmed(rows, {"Aston Villa", "Nottingham Forest", "AFC Bournemouth", "Crystal Palace"})
    assert len(kept) == 4
    assert excluded.empty


def test_radar_uses_shared_reference_and_average_rank_for_ties():
    scores = percentile_scores(pd.DataFrame({"Gls": [0, 1, 1, 4]}), ["Gls"])
    assert scores.Gls.tolist() == [25, 62.5, 62.5, 100]


def test_team_leader_is_highest_team_total_and_keeps_ties():
    totals = pd.DataFrame({"Gls": [12, 10, 12]}, index=["A", "B", "C"])
    means = pd.DataFrame({"Age": [24, 26, 25]}, index=["A", "B", "C"])
    leaders = team_leaders(totals, means)
    assert set(leaders.loc[leaders.Attribute.eq("Gls"), "Squad"]) == {"A", "C"}
