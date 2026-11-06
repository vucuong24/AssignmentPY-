"""Synthetic HTML fixtures test parsing; never used as a real football dataset."""
import json
from pathlib import Path

import pandas as pd
import pytest

from epl import fbref_scraper as scraper


def squad_html(squad_id="18bb7c10", name="Arsenal", season="2025-2026", competition="9", extra="", rows=None):
    if rows is None:
        rows = [("aabbcc01", "Test Player A", "60", "1", "1"),
                ("aabbcc02", "Test Player B", "900", "3", "2")]
    table_rows = "".join(
        f'<tr><th data-stat="player"><a href="/en/players/{pid}/Test">{player}</a></th>'
        f'<td data-stat="nationality">eng ENG</td><td data-stat="position">FW</td>'
        f'<td data-stat="age">25-123</td><td data-stat="games">10</td>'
        f'<td data-stat="games_starts">8</td><td data-stat="minutes">{minutes}</td>'
        f'<td data-stat="goals">{goals}</td><td data-stat="assists">{assists}</td>'
        f'<td data-stat="goals_per90">0.30</td></tr>'
        for pid, player, minutes, goals, assists in rows
    )
    return (f'<html><head><title>{season} {name} Stats</title>'
            f'<link rel="canonical" href="https://fbref.com/en/squads/{squad_id}/{season}/Test-Stats"></head>'
            f'<body><h1>{season} {name} Stats</h1><table id="stats_standard_{competition}"><tbody>'
            f'{table_rows}</tbody></table>{extra}</body></html>')


def test_comment_table_namespaces_and_player_ids():
    keeper = '''<!--<table id="stats_keeper_9"><tbody><tr>
    <th data-stat="player"><a href="/en/players/aabbcc02/Test">Different spelling</a></th>
    <td data-stat="gk_saves">23</td><td data-stat="gk_save_pct">70.5</td>
    </tr></tbody></table>-->'''
    frame, raw, info = scraper.parse_squad(squad_html(extra=keeper))
    assert info["tables"]["keeper"]
    assert not info["tables"]["passing"]
    assert frame.loc[frame.PlayerID.eq("aabbcc02"), "Saves"].item() == 23
    assert frame.loc[frame.PlayerID.eq("aabbcc01"), "Saves"].isna().all()
    assert frame.Age.eq(25).all()
    assert frame.Nation.eq("ENG").all()
    assert "standard__goals_per90" in frame
    assert "keeper__gk_save_pct" in frame
    assert "gk_save_pct" in raw


@pytest.mark.parametrize("html", [squad_html(season="2024-2025"), squad_html(competition="12"),
                                       '<html><title>Just a moment...</title></html>'])
def test_wrong_season_competition_and_challenge_are_rejected(html):
    with pytest.raises(ValueError):
        scraper.parse_squad(html)


def test_missing_advanced_data_is_missing_not_zero():
    frame, _, info = scraper.parse_squad(squad_html())
    assert "xG" not in frame
    assert "PrgP" not in frame
    assert not info["tables"]["shooting"]


def test_unused_players_blank_minutes_are_zero_but_played_missing_minutes_fail():
    page = squad_html(rows=[("aabbcc01", "Unused Player", "", "", ""),
                            ("aabbcc02", "Played Player", "900", "3", "2")])
    page = page.replace('<td data-stat="games">10</td>', '<td data-stat="games">0</td>', 1)
    page = page.replace('<td data-stat="games_starts">8</td>', '<td data-stat="games_starts">0</td>', 1)
    frame, _, _ = scraper.parse_squad(page)
    assert frame.loc[frame.PlayerID.eq("aabbcc01"), "Min"].item() == 0
    totals, stints = scraper.make_totals(frame)
    assert totals.PlayerID.tolist() == ["aabbcc02"]
    assert len(stints) == 1
    with pytest.raises(ValueError, match="số phút thiếu"):
        scraper.parse_squad(squad_html(rows=[("aabbcc01", "Played but unknown", "", "1", "0")]))


def test_player_team_stints_aggregate_before_strict_90_filter():
    a, _, _ = scraper.parse_squad(squad_html())
    b, _, _ = scraper.parse_squad(squad_html(squad_id="abcdef12", name="Chelsea"))
    totals, stints = scraper.make_totals(pd.concat([a, b], ignore_index=True))
    test_player = totals[totals.PlayerID.eq("aabbcc01")].iloc[0]
    assert test_player.Min == 120
    assert test_player.Gls == 2
    assert set(test_player.Squad.split(" / ")) == {"Arsenal", "Chelsea"}
    assert stints.Min.sum() == totals.Min.sum()
    assert "standard__goals_per90" not in totals  # Rates from different stints are never summed.
    with pytest.raises(ValueError, match="Trùng"):
        scraper.make_totals(pd.concat([a, a], ignore_index=True))


def test_exact_90_and_missing_stint_statistics():
    frame, _, _ = scraper.parse_squad(squad_html(rows=[
        ("aabbcc01", "A", "90", "0", "0"), ("aabbcc02", "B", "120", "1", "1")]))
    totals, _ = scraper.make_totals(frame)
    assert totals.PlayerID.tolist() == ["aabbcc02"]
    other = frame.copy()
    other["SquadID"] = "other"
    other["Squad"] = "Chelsea"
    frame["xG"] = 1.0
    other["xG"] = float("nan")
    totals, _ = scraper.make_totals(pd.concat([frame, other], ignore_index=True))
    assert totals.xG.isna().all()




def test_local_partial_requires_explicit_flag_and_no_fpl(tmp_path, monkeypatch):
    manual = tmp_path / "manual"; manual.mkdir()
    (manual / "Arsenal.html").write_text(squad_html(), encoding="utf-8")
    monkeypatch.setattr(scraper, "INPUT", tmp_path / "raw")
    output = tmp_path / "processed"
    with pytest.raises(ValueError, match="1/20"):
        scraper.collect_fbref(html_dir=manual, output=output)
    assert not (output / "result.csv").exists()
    # Need at least two qualified players for analysis in partial mode.
    (manual / "Arsenal.html").write_text(squad_html(rows=[
        ("aabbcc01", "A", "120", "1", "0"), ("aabbcc02", "B", "900", "3", "2")]), encoding="utf-8")
    result = scraper.collect_fbref(html_dir=manual, output=output, allow_partial=True)
    assert result["source"] == "FBref"
    assert result["teams"] == 1
    assert not result["complete_league"]
    assert "xG" in result["missing_requested_metrics"]
    assert pd.read_csv(output / "result.csv").Source.eq("FBref").all()


def test_partial_cannot_replace_complete_dataset(tmp_path, monkeypatch):
    manual = tmp_path / "manual"; manual.mkdir()
    (manual / "Arsenal.html").write_text(squad_html(rows=[
        ("aabbcc01", "A", "120", "1", "0"), ("aabbcc02", "B", "900", "3", "2")]), encoding="utf-8")
    output = tmp_path / "processed"; output.mkdir()
    (output / "data_quality.json").write_text('{"complete_league": true}', encoding="utf-8")
    monkeypatch.setattr(scraper, "INPUT", tmp_path / "raw")
    with pytest.raises(ValueError, match="Không ghi đè"):
        scraper.collect_fbref(html_dir=manual, output=output, allow_partial=True)
    assert json.loads((output / "data_quality.json").read_text())["complete_league"]


def test_default_collection_reads_sources_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr("socket.socket.connect", lambda *a, **k: pytest.fail("Không được truy cập mạng"))
    root = tmp_path / "raw"
    manual = root.parent / "sources"; manual.mkdir(parents=True)
    (manual / "Arsenal.html").write_text(squad_html(rows=[
        ("aabbcc01", "A", "120", "1", "0"), ("aabbcc02", "B", "900", "3", "2")]), encoding="utf-8")
    monkeypatch.setattr(scraper, "INPUT", root)
    result = scraper.collect_fbref(output=tmp_path / "processed", allow_partial=True)
    assert result["teams"] == 1
    assert result["source"] == "FBref"


def test_missing_local_html_never_downloads_a_replacement(tmp_path, monkeypatch):
    monkeypatch.setattr("socket.socket.connect", lambda *a, **k: pytest.fail("Không được truy cập mạng"))
    monkeypatch.setattr(scraper, "INPUT", tmp_path)
    with pytest.raises(ValueError, match="Chưa có HTML"):
        scraper.collect_fbref(output=tmp_path / "processed", allow_partial=True)
    assert not (tmp_path / "processed" / "result.csv").exists()


def test_default_cli_reads_local_fbref(monkeypatch):
    import main
    called = []
    monkeypatch.setattr(scraper, "collect_fbref", lambda *a, **k: called.append("FBref") or {"source": "FBref"})
    monkeypatch.setattr("socket.socket.connect", lambda *a, **k: pytest.fail("Không được truy cập mạng"))
    main.main(["fetch", "--offline"])
    assert called == ["FBref"]


def test_default_all_pipeline_only_reads_local_files(tmp_path, monkeypatch):
    import main
    from epl import fbref_pipeline as fb
    monkeypatch.setattr("socket.socket.connect", lambda *a, **k: pytest.fail("Không được truy cập mạng"))
    calls = []
    monkeypatch.setattr(fb, "REPORTS", tmp_path / "reports")
    fb.REPORTS.mkdir()
    def collect(**kwargs):
        calls.append(kwargs)
        return {"source": "FBref", "dataset_sha256": "test-fixture", "raw_sources": []}
    monkeypatch.setattr(fb, "collect_fbref", collect)
    for name in ["statistics", "clustering", "radar", "valuation", "report"]:
        monkeypatch.setattr(fb, name, lambda: {})
    def transfer():
        return {}
    monkeypatch.setattr(fb, "transfers", transfer)
    main.main(["all", "--html-dir", str(tmp_path)])
    assert calls == [{"html_dir": tmp_path, "allow_partial": False}]


def test_offline_data_analyses_run_only_in_temporary_directory(tmp_path, monkeypatch):
    from epl import fbref_pipeline as fb
    manual = tmp_path / "manual"; manual.mkdir()
    rows = [(f"{i:08x}", f"Fixture Player {i}", str(120+i*100), str(i % 5), str(i % 3)) for i in range(1,13)]
    page = squad_html(rows=rows)
    # Vary ages as well; these are test fixtures, not observed football statistics.
    for i in range(1,13):
        page = page.replace('<td data-stat="age">25-123</td>', f'<td data-stat="age">{20+i}-123</td>', 1)
    (manual / "Arsenal.html").write_text(page, encoding="utf-8")
    monkeypatch.setattr(scraper, "INPUT", tmp_path / "raw")
    output = tmp_path / "processed"
    scraper.collect_fbref(html_dir=manual, output=output, allow_partial=True)
    monkeypatch.setattr(fb, "OUTPUT", output)
    for name, folder in [("TABLES", "tables"), ("FIGURES", "figures"), ("MODELS", "models"), ("REPORTS", "reports")]:
        monkeypatch.setattr(fb, name, tmp_path / folder)
    assert fb.statistics()["histogram_count"] == 6
    assert fb.clustering(k=2)["source"] == "FBref"
    assert fb.radar()["source"] == "FBref"
    assert (tmp_path / "tables" / "radar_values.csv").exists()
    assert not any("Ast_FPL" in c for c in pd.read_csv(output / "result.csv").columns)
    from epl import pdf_report
    pdf_calls = []
    monkeypatch.setattr(pdf_report, "build_pdf", lambda *a, **k: pdf_calls.append((a, k)))
    result = fb.report()
    assert not result["complete_league"]
    assert len(pdf_calls) == 1
    assert pdf_calls[0][0][0] == tmp_path / "reports"
    text = (tmp_path / "reports" / "BAO_CAO.md").read_text(encoding="utf-8")
    assert "DỮ LIỆU MỘT PHẦN" in text
    assert "Ast_FPL" not in text
    for uncollected in ["xG", "xA", "PrgP", "Tkl", "Int", "Saves", "CleanSheets"]:
        assert uncollected not in text
    assert "FBref" in text
    # A modified CSV cannot silently reuse the old charts/report.
    modified = pd.read_csv(output / "result.csv")
    modified.loc[0, "Gls"] += 1
    modified.to_csv(output / "result.csv", index=False)
    with pytest.raises(ValueError, match="hash"):
        fb.report()


def test_report_glossary_uses_observed_columns_only():
    from epl.fbref_pipeline import report_glossary
    players = pd.DataFrame({"Age": [25], "Min": [900], "Gls": [3], "Ast": [1],
                            "Sh": [10], "Saves": [float("nan")]})
    glossary = report_glossary(players)
    labels = glossary["Chỉ số"].str.cat(sep=" / ").split(" / ")
    assert {"Age", "Min", "Gls", "Ast", "Sh"}.issubset(labels)
    assert not {"Saves", "CleanSheets", "90s", "Starts", "SoT", "xG", "xA", "PrgP"}.intersection(labels)
