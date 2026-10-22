# Claude wrote this for LVRA v2 (2026-10-20)
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lvra.utils.alert_rows import json_to_feature_rows

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "parity"
TRIMMED = FIX / "20260711_084501_trimmed.json"
FEATURE_NAMES = pd.read_csv(HERE.parent / "data" / "lvra_features.csv").feature.tolist()
LWA_OBJECT = 170587106692825120
DUP_OBJECT = 170587111930986663


def write_entries(path, entries):
    path.write_text(json.dumps(entries))
    return path


def test_parity_with_training_row():
    rows, _ = json_to_feature_rows(TRIMMED)
    expected = pd.read_csv(FIX / "24lwa_expected_row.csv")
    row = rows.set_index("diaSourceId").loc[expected.diasourceid.iloc[0]]
    for col in FEATURE_NAMES:
        e, g = expected[col].iloc[0], row[col]
        assert (pd.isna(e) and pd.isna(g)) or e == g or np.isclose(float(e), float(g)), col


def test_two_alerts_same_object_give_two_rows():
    rows, _ = json_to_feature_rows(TRIMMED)
    dup = rows[rows.diaObjectId == DUP_OBJECT]
    assert len(dup) == 2 and dup.diaSourceId.nunique() == 2


def test_entry_without_alert_is_reported_not_raised(tmp_path):
    entries = json.loads(TRIMMED.read_text())
    entries[0]["alert"] = None
    rows, missing = json_to_feature_rows(write_entries(tmp_path / "x.json", entries))
    assert missing == [entries[0]["diaObjectId"]]
    assert len(rows) == len(entries) - 1


def test_trigger_is_latest_mjd_not_last_list_item(tmp_path):
    entries = json.loads(TRIMMED.read_text())
    lwa = next(e for e in entries if e["diaObjectId"] == LWA_OBJECT)
    lwa["alert"]["diaSourcesList"].reverse()
    shuffled, _ = json_to_feature_rows(write_entries(tmp_path / "x.json", [lwa]))
    rows, _ = json_to_feature_rows(TRIMMED)
    expected = rows[rows.diaObjectId == LWA_OBJECT].reset_index(drop=True)
    pd.testing.assert_frame_equal(shuffled, expected, check_dtype=False)


def test_all_feature_columns_present():
    rows, _ = json_to_feature_rows(TRIMMED)
    assert set(FEATURE_NAMES) <= set(rows.columns)
