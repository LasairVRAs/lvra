# Claude wrote this for LVRA v2 (2026-10-21)
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

import lvra.pypeline.lvra_annotator as an_module
from lvra.utils.alert_rows import json_to_feature_rows
from lvra.utils.feature_store import connect, insert_features, insert_scores
from test.helpers import initialise_features_db, initialise_log_db

PARITY_JSON = Path(__file__).resolve().parent / "fixtures" / "parity" / "20260711_084501_trimmed.json"
STEM = "20260711_084501"
DUP_OBJECT = 170587111930986663
CLASSES = ["agn", "bogus", "extragal", "mover", "real"]


@pytest.fixture(scope="module")
def parity_rows():
    return json_to_feature_rows(PARITY_JSON)[0]


@pytest.fixture
def base(tmp_path, parity_rows):
    (tmp_path / "db").mkdir()
    con = sqlite3.connect(initialise_log_db(tmp_path / "db" / "log.db"))
    con.execute("INSERT INTO predict (stem, r0b, lvra) VALUES (?, 0, 1)", (STEM,))
    con.execute("INSERT INTO annotating (stem, r0b) VALUES (?, 0)", (STEM,))
    con.commit()
    features_con = connect(initialise_features_db(tmp_path / "db" / "features.db"))
    insert_features(features_con, parity_rows, STEM)
    scores = parity_rows[["diaObjectId", "diaSourceId"]].assign(**{c: 0.2 for c in CLASSES})
    insert_scores(features_con, scores, STEM, "champion", "0.1")
    config = {'TOPIC_OUT': 'lvradev', 'EXPLANATION': 'test', 'URL': 'https://example.com',
              'MODELS': {'champion': {'PATH': 'unused', 'VERSION': "0.1"}, 'challenger': None, 'retired': None}}
    (tmp_path / "lvra_config.yaml").write_text(yaml.dump(config))
    return tmp_path


@pytest.fixture
def lasair_L(monkeypatch):
    L = Mock()
    monkeypatch.setattr(an_module.lasair, "lasair_client", Mock(return_value=L))
    return L


def run_main(monkeypatch, base, token="fake-token"):
    monkeypatch.setattr(an_module, "LASAIR_TOKEN", token)
    monkeypatch.setattr(an_module, "LVRA_CONFIG_FILE", base / "lvra_config.yaml")
    monkeypatch.setattr(an_module, "set_up", lambda **kw: {"log_db": base / "db" / "log.db", "endpoint": "x"})
    return an_module.main()


def annotating_status(base):
    con = sqlite3.connect(base / "db" / "log.db")
    return con.execute("SELECT lvra FROM annotating WHERE stem = ?", (STEM,)).fetchone()[0]


def test_one_annotate_call_per_object(monkeypatch, base, lasair_L, parity_rows):
    run_main(monkeypatch, base)
    calls = lasair_L.annotate.call_args_list
    assert len(calls) == parity_rows.diaObjectId.nunique()
    dup_call = [c for c in calls if c.kwargs["objectId"] == DUP_OBJECT][0]
    dup_rows = parity_rows[parity_rows.diaObjectId == DUP_OBJECT]
    latest = dup_rows.loc[dup_rows.delta_days_TOTAL.idxmax()]
    assert dup_call.kwargs["classdict"]["blame_diaSourceId"] == latest.diaSourceId


def test_status_1_after_success(monkeypatch, base, lasair_L):
    run_main(monkeypatch, base)
    assert annotating_status(base) == 1


def test_mixed_failures_status_minus1(monkeypatch, base, lasair_L):
    lasair_L.annotate.side_effect = [None, Exception("boom")] + [None] * 10
    run_main(monkeypatch, base)
    assert annotating_status(base) == -1


def test_all_failures_status_42(monkeypatch, base, lasair_L):
    lasair_L.annotate.side_effect = Exception("boom")
    run_main(monkeypatch, base)
    assert annotating_status(base) == 42


def test_no_token_exits_99(monkeypatch, base, lasair_L):
    assert run_main(monkeypatch, base, token=None) == 99
    assert not lasair_L.annotate.called


def test_classification_arg_is_formatted_string(monkeypatch, base, lasair_L):
    run_main(monkeypatch, base)
    kwargs = lasair_L.annotate.call_args.kwargs
    assert kwargs["classification"] == "0.200000"
    assert kwargs["version"] == "0.1"
    assert kwargs["topic"] == "lvradev"


def test_stem_waits_for_predict(monkeypatch, base, lasair_L):
    con = sqlite3.connect(base / "db" / "log.db")
    con.execute("UPDATE predict SET lvra = 0 WHERE stem = ?", (STEM,))
    con.commit()
    run_main(monkeypatch, base)
    assert not lasair_L.annotate.called
    assert annotating_status(base) == 0
