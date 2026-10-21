# Claude wrote this for LVRA v2 (2026-10-21)
import json
import logging
import shutil
import sqlite3
from pathlib import Path

import pytest

import lvra.pypeline.lvra_feature_maker as fm_module
from lvra.utils.feature_store import connect, read_features
from test.helpers import initialise_features_db, initialise_log_db

PARITY_JSON = Path(__file__).resolve().parent / "fixtures" / "parity" / "20260711_084501_trimmed.json"
STEM = "20260711_084501"
LOGGER = logging.getLogger("test")


@pytest.fixture
def base(tmp_path):
    (tmp_path / "db").mkdir()
    initialise_log_db(tmp_path / "db" / "log.db")
    initialise_features_db(tmp_path / "db" / "features.db")
    json_dir = tmp_path / "JSON" / STEM[:4] / STEM[:8]
    json_dir.mkdir(parents=True)
    shutil.copy(PARITY_JSON, json_dir / f"{STEM}.json")
    return tmp_path


@pytest.fixture
def features_con(base):
    return connect(base / "db" / "features.db")


def run_main(monkeypatch, base):
    monkeypatch.setattr(fm_module, "set_up", lambda **kw: {"base_dir": base, "log_db": base / "db" / "log.db"})
    return fm_module.main()


def test_stems_selected_only_where_lvra_not_done(base):
    con = sqlite3.connect(base / "db" / "log.db")
    for stem, lvra in [("s0", 0), ("s1", 1), ("sm1", -1), ("snull", None)]:
        con.execute("INSERT INTO feature_making (stem, r0b, lvra) VALUES (?, 0, ?)", (stem, lvra))
    assert fm_module.stemlist_from_logdb(con.cursor(), LOGGER) == ["s0"]


def test_consumer_style_insert_defaults_lvra_to_0(base):
    con = sqlite3.connect(base / "db" / "log.db")
    con.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, 0)", (STEM,))
    assert fm_module.stemlist_from_logdb(con.cursor(), LOGGER) == [STEM]


def test_make_features_writes_rows_and_status_1(base, features_con):
    path = base / "JSON" / STEM[:4] / STEM[:8] / f"{STEM}.json"
    assert fm_module.make_features(path, features_con, STEM, LOGGER) == 1
    assert len(read_features(features_con, [STEM])) == len(json.loads(path.read_text()))


def test_missing_json_status_21(base, features_con):
    assert fm_module.make_features(base / "nope.json", features_con, STEM, LOGGER) == 21


def test_partial_alerts_status_minus1(base, features_con):
    entries = json.loads(PARITY_JSON.read_text())
    entries[0]["alert"] = None
    path = base / "partial.json"
    path.write_text(json.dumps(entries))
    assert fm_module.make_features(path, features_con, STEM, LOGGER) == -1
    assert len(read_features(features_con, [STEM])) == len(entries) - 1


def test_rerun_stem_keeps_first_rows(base, features_con):
    path = base / "JSON" / STEM[:4] / STEM[:8] / f"{STEM}.json"
    fm_module.make_features(path, features_con, STEM, LOGGER)
    first = read_features(features_con, [STEM]).set_index("diaSourceId").psfflux

    entries = json.loads(path.read_text())
    for e in entries:
        for s in e["alert"]["diaSourcesList"]:
            s["psfFlux"] = -1.0
    path.write_text(json.dumps(entries))

    assert fm_module.make_features(path, features_con, STEM, LOGGER) == 1
    second = read_features(features_con, [STEM]).set_index("diaSourceId").psfflux
    assert second.equals(first)


def test_main_sets_lvra_status(monkeypatch, base):
    con = sqlite3.connect(base / "db" / "log.db")
    con.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, 0)", (STEM,))
    con.commit()
    assert run_main(monkeypatch, base) == 0
    assert con.execute("SELECT lvra FROM feature_making WHERE stem = ?", (STEM,)).fetchone()[0] == 1


def test_r0b_columns_untouched(monkeypatch, base):
    con = sqlite3.connect(base / "db" / "log.db")
    for stem, r0b in [(STEM, 0), ("20260711_090000", 1), ("20260711_100000", -1)]:
        for table in ("feature_making", "predict", "annotating"):
            con.execute(f"INSERT INTO {table} (stem, r0b) VALUES (?, ?)", (stem, r0b))
    con.commit()
    before = {t: con.execute(f"SELECT stem, r0b FROM {t} ORDER BY stem").fetchall()
              for t in ("feature_making", "predict", "annotating")}
    run_main(monkeypatch, base)
    after = {t: con.execute(f"SELECT stem, r0b FROM {t} ORDER BY stem").fetchall()
             for t in ("feature_making", "predict", "annotating")}
    assert before == after
