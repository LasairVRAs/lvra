# Claude wrote this for LVRA v2 (2026-10-21)
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lvra.utils.alert_rows import json_to_feature_rows
from lvra.utils.exceptions import LVRAValueError
from lvra.utils.feature_store import connect, insert_features, insert_scores, read_features
from test.helpers import initialise_features_db

HERE = Path(__file__).resolve().parent
TRIMMED = HERE / "fixtures" / "parity" / "20260711_084501_trimmed.json"
LVRA_FEATURES = HERE.parent / "data" / "lvra_features.csv"
STEM = "20260711_084501"


@pytest.fixture
def rows():
    return json_to_feature_rows(TRIMMED)[0]


@pytest.fixture
def con(tmp_path):
    return connect(initialise_features_db(tmp_path / "features.db"))


def scores_for(rows, classes=("agn", "bogus", "extragal", "mover", "real")):
    scores = rows[["diaObjectId", "diaSourceId"]].copy()
    for c in classes:
        scores[c] = 0.2
    return scores


def table_columns(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def test_connect_sets_wal_and_foreign_keys(con):
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_first_write_wins(con, rows):
    first = rows.iloc[:1]
    assert insert_features(con, first, STEM) == 1
    second = first.copy()
    second["psfflux"] = -999.0
    assert insert_features(con, second, "other_stem") == 0
    got = read_features(con, [STEM, "other_stem"])
    assert len(got) == 1
    assert got.psfflux.iloc[0] == first.psfflux.iloc[0]


def test_roundtrip_nan_and_text(con, rows):
    rows = rows.copy()
    rows.loc[rows.index[0], "psfflux"] = np.nan
    insert_features(con, rows, STEM)
    got = read_features(con, [STEM]).set_index("diaSourceId").loc[rows.diaSourceId]
    assert pd.isna(got.psfflux.iloc[0])
    assert got.band.tolist() == rows.band.tolist()
    assert got.best_distance_flag.tolist() == rows.best_distance_flag.tolist()


def test_read_features_filters_on_stem(con, rows):
    insert_features(con, rows.iloc[:1], STEM)
    insert_features(con, rows.iloc[1:], "other_stem")
    assert len(read_features(con, [STEM])) == 1


def test_schema_columns_match_feature_list(con):
    assert table_columns(con, "features")[4:] == pd.read_csv(LVRA_FEATURES).feature.tolist()


def test_scores_rerun_does_not_duplicate(con, rows):
    insert_features(con, rows, STEM)
    assert insert_scores(con, scores_for(rows), STEM, "champion", "v1") == len(rows)
    assert insert_scores(con, scores_for(rows), STEM, "champion", "v1") == 0
    n, n_gal = con.execute("SELECT COUNT(*), COUNT(gal) FROM model_scores").fetchone()
    assert n == len(rows) and n_gal == 0


def test_score_for_unknown_alert_rejected(con):
    unknown = pd.DataFrame({"diaObjectId": [1], "diaSourceId": [1], "extragal": [0.5]})
    with pytest.raises(sqlite3.IntegrityError):
        insert_scores(con, unknown, "s", "champion", "v1")


def test_connect_missing_db_raises(tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        connect(tmp_path / "missing.db")
    assert not (tmp_path / "missing.db").exists()


def test_invalid_role_rejected(con, rows):
    insert_features(con, rows, STEM)
    with pytest.raises(LVRAValueError):
        insert_scores(con, scores_for(rows), STEM, "retiree", "v1")
