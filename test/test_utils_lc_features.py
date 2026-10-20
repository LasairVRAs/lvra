# Claude wrote this for LVRA v2 (2026-10-20)
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lvra.utils.lc_features import lc_features

FIX = Path(__file__).resolve().parent / "fixtures" / "lc_features"


def make_lc(mjd, flux, band="r", reliability=0.9, snr=20.0):
    n = len(mjd)
    return pd.DataFrame({
        "midpointmjdtai": mjd,
        "psfflux": flux,
        "reliability": [reliability] * n,
        "snr": [snr] * n,
        "band": [band] * n if isinstance(band, str) else band,
        "extendedness": [0.0] * n,
        "ra": [150.0] * n,
        "decl": [0.4] * n,
    })


LC_4_ROWS = make_lc([60000.0, 60001.0, 60002.0, 60003.0], [1000.0, 1200.0, 1100.0, 900.0])
LC_R_BAND_ONLY = make_lc([60000.0, 60001.0, 60002.0], [1000.0, 1200.0, 1100.0])
LC_BRIGHT_THEN_FAINT = make_lc([60000.0, 60001.0, 60002.0], [1000.0, 8000.0, 1000.0])


def test_lc_features_matches_notebook_golden_row():
    lc = pd.read_csv(FIX / "lc.csv").sort_values("midpointmjdtai")
    discovery_mjd = pd.read_csv(FIX / "summary.csv").discovery_mjd.iloc[0]
    expected = json.loads((FIX / "expected.json").read_text())
    got = lc_features(lc, discovery_mjd)
    assert set(got) == set(expected)
    for k, v in expected.items():
        assert (v is None and np.isnan(got[k])) or np.isclose(got[k], v), k


def test_medianR_last5_nan_below_five_detections():
    assert np.isnan(lc_features(LC_4_ROWS, 60000.0)["medianR_last5"])


def test_absent_band_gives_nan_band_features():
    f = lc_features(LC_R_BAND_ONLY, 60000.0)
    assert np.isnan(f["n_det_u"]) and np.isnan(f["median_flux_u"]) and np.isnan(f["rise_rate_u"])


def test_threshold_flags_are_ever_above():
    f = lc_features(LC_BRIGHT_THEN_FAINT, 60000.0)
    assert f["ever_brighter_22"] == 1 and f["first_brighter_22"] == 0 and f["N_brighter_22"] == 1


def test_single_detection_lightcurve():
    f = lc_features(make_lc([60000.0], [8000.0]), 60000.0)
    assert f["ever_brighter_22"] == 1 and f["first_brighter_22"] == 1 and f["N_brighter_22"] == 1
    assert f["max_flux"] == 8000.0 and f["delta_days_since_max"] == 0 and f["n_det_r"] == 1
    assert np.isnan(f["rise_rate_r"]) and np.isnan(f["medianR_last5"])
