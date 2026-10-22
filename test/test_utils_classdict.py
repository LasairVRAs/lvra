# Claude wrote this for LVRA v2 (2026-10-21)
import json
from pathlib import Path

import numpy as np
import pytest

from lvra.utils.alert_rows import json_to_feature_rows
from lvra.utils.classdict import PUBLIC_FEATURES, build_classdict, format_classification

PARITY_JSON = Path(__file__).resolve().parent / "fixtures" / "parity" / "20260711_084501_trimmed.json"
SCORES = {"extragal": 0.123456789, "mover": 0.000012345678, "real": 0.5, "bogus": 0.2, "agn": 0.176543, "gal": None}
ONE_SLOT = {"champion": {"version": "0.1", **SCORES}, "challenger": None, "retired": None}
THREE_SLOTS = {role: {"version": "0.1.0-long-version-name", **SCORES} for role in ("champion", "challenger", "retired")}


@pytest.fixture(scope="module")
def full_features():
    return json_to_feature_rows(PARITY_JSON)[0].iloc[0].to_dict()


def test_classification_small_value_fixed_format():
    assert format_classification(1.234e-7) == "0.000000"
    assert format_classification(0.0000123) == "0.000012"


def test_classification_text_sorts_like_numbers():
    ps = [0.5, 0.05, 0.9999, 1e-5]
    assert sorted(map(format_classification, ps)) == list(map(format_classification, sorted(ps)))


def test_classdict_under_4096_with_three_slots(full_features):
    assert len(json.dumps(build_classdict(full_features, THREE_SLOTS))) < 4096


def test_classdict_valid_json_with_nan_features(full_features):
    features = {**full_features, "max_flux": np.nan, "current_snr": None}
    d = json.loads(json.dumps(build_classdict(features, ONE_SLOT), allow_nan=False))
    assert d["max_flux"] is None and d["current_snr"] is None


def test_empty_slots_null_and_gal_absent(full_features):
    d = build_classdict(full_features, ONE_SLOT)
    assert d["challenger"] is None and d["retired"] is None and "gal" not in d["champion"]


def test_public_feature_names(full_features):
    d = build_classdict(full_features, ONE_SLOT)
    assert {"n_gt23", "ever_gt22", "first_gt18", "n_det_y", "delta_days_total", "n_loR_sources"} <= set(d)
    assert set(d) == {"blame_diaSourceId", "champion", "challenger", "retired"} | set(PUBLIC_FEATURES)
    assert d["blame_diaSourceId"] == full_features["diaSourceId"]
    # Claude wrote this for the classdict renames (2026-10-22)
    assert list(d)[:7] == ["blame_diaSourceId", "champion", "challenger", "retired", "n_loR_sources", "n_hiR_sources", "n_gt18"]


def test_numbers_rounded_and_python_types(full_features):
    features = {**full_features, "max_flux": np.float64(1234.56789), "n_det_g": np.int64(3), "ever_brighter_22": np.bool_(True)}
    d = build_classdict(features, ONE_SLOT)
    assert d["max_flux"] == 1234.57
    assert d["n_det_g"] == 3 and type(d["n_det_g"]) is int
    assert d["ever_gt22"] is True
    assert d["champion"]["extragal"] == 0.123457 and d["champion"]["mover"] == 1.23457e-05
