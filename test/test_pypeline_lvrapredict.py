# Claude wrote this for LVRA v2 (2026-10-21)
import logging
import sqlite3
from pathlib import Path

import joblib
import pytest
import yaml

import lvra.pypeline.lvra_predict as pr_module
from lvra.utils.alert_rows import FEATURE_NAMES, json_to_feature_rows
from lvra.utils.feature_store import connect, insert_features
from test.helpers import fit_tiny_hgb, initialise_features_db, initialise_log_db

PARITY_JSON = Path(__file__).resolve().parent / "fixtures" / "parity" / "20260711_084501_trimmed.json"
STEM = "20260711_084501"


@pytest.fixture(scope="module")
def parity_rows():
    return json_to_feature_rows(PARITY_JSON)[0]


@pytest.fixture
def base(tmp_path, parity_rows):
    (tmp_path / "db").mkdir()
    con = sqlite3.connect(initialise_log_db(tmp_path / "db" / "log.db"))
    con.execute("INSERT INTO feature_making (stem, r0b, lvra) VALUES (?, 0, 1)", (STEM,))
    con.execute("INSERT INTO predict (stem, r0b) VALUES (?, 0)", (STEM,))
    con.commit()
    features_con = connect(initialise_features_db(tmp_path / "db" / "features.db"))
    insert_features(features_con, parity_rows, STEM)
    joblib.dump(fit_tiny_hgb(parity_rows, FEATURE_NAMES), tmp_path / "champion.joblib")
    return tmp_path


def run_main(monkeypatch, base, challenger=None):
    config = {'TOPIC_OUT': 'lvradev', 'EXPLANATION': 'test', 'URL': 'https://example.com',
              'MODELS': {'champion': {'PATH': str(base / "champion.joblib"), 'VERSION': "0.1"},
                         'challenger': challenger,
                         'retired': None}}
    (base / "lvra_config.yaml").write_text(yaml.dump(config))
    monkeypatch.setattr(pr_module, "LVRA_CONFIG_FILE", base / "lvra_config.yaml")
    monkeypatch.setattr(pr_module, "set_up", lambda **kw: {"base_dir": base, "log_db": base / "db" / "log.db"})
    return pr_module.main()


def score_rows(base):
    con = sqlite3.connect(base / "db" / "features.db")
    return con.execute("SELECT diaSourceId, model_role, model_version FROM model_scores").fetchall()


def predict_status(base):
    con = sqlite3.connect(base / "db" / "log.db")
    return con.execute("SELECT lvra FROM predict WHERE stem = ?", (STEM,)).fetchone()[0]


def test_stems_need_features_done_and_predict_not_done(base):
    con = sqlite3.connect(base / "db" / "log.db")
    for stem, fm, pr in [("a", 1, 0), ("b", -1, 0), ("c", 0, 0), ("d", 1, 1), ("e", 21, 0)]:
        con.execute("INSERT INTO feature_making (stem, lvra) VALUES (?, ?)", (stem, fm))
        con.execute("INSERT INTO predict (stem, lvra) VALUES (?, ?)", (stem, pr))
    stems = pr_module.stemlist_from_log(con.cursor(), logging.getLogger("test"))
    assert sorted(stems) == sorted([STEM, "a", "b"])


def test_champion_only_one_score_row_per_alert(monkeypatch, base, parity_rows):
    assert run_main(monkeypatch, base) == 0
    rows = score_rows(base)
    assert len(rows) == len(parity_rows)
    assert {(r[1], r[2]) for r in rows} == {("champion", "0.1")}


def test_champion_and_challenger_two_rows_per_alert(monkeypatch, base, parity_rows):
    challenger = {'PATH': str(base / "champion.joblib"), 'VERSION': "0.2"}
    run_main(monkeypatch, base, challenger=challenger)
    rows = score_rows(base)
    assert len(rows) == 2 * len(parity_rows)
    assert {(r[1], r[2]) for r in rows} == {("champion", "0.1"), ("challenger", "0.2")}


def test_predict_status_1_after_success(monkeypatch, base):
    run_main(monkeypatch, base)
    assert predict_status(base) == 1


def test_missing_feature_status_31(monkeypatch, base, parity_rows):
    names = FEATURE_NAMES + ["not_in_features_db"]
    joblib.dump(fit_tiny_hgb(parity_rows.assign(not_in_features_db=0.0), names), base / "champion.joblib")
    run_main(monkeypatch, base)
    assert predict_status(base) == 31
    assert score_rows(base) == []


def test_rerun_no_duplicate_scores(monkeypatch, base, parity_rows):
    run_main(monkeypatch, base)
    con = sqlite3.connect(base / "db" / "log.db")
    con.execute("UPDATE predict SET lvra = 0 WHERE stem = ?", (STEM,))
    con.commit()
    run_main(monkeypatch, base)
    assert len(score_rows(base)) == len(parity_rows)


def test_missing_model_file_exits_21(monkeypatch, base):
    (base / "champion.joblib").unlink()
    assert run_main(monkeypatch, base) == 21
    assert predict_status(base) == 0
