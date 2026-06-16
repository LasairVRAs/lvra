# Chat gpt 5.2 wrote most of these tests
import json
from pathlib import Path
import pandas as pd
import pytest

from lvra.utils.features import json2cleandf, flux_threshold_features

HERE = Path(__file__).resolve().parent
TEST_JSON = HERE.parent / "data" / "test" / "20260205_073301.json"


def test_json2cleandf_basic_properties():
    """Sanity checks: returns a DataFrame and a list, and expected key columns exist."""
    clean_df, missing = json2cleandf(TEST_JSON)
    assert isinstance(clean_df, pd.DataFrame)
    assert isinstance(missing, list)

    # key columns that the function is expected to produce
    assert "diaObjectId" in clean_df.columns, "diaObjectId must be present"
    assert "diaSourceId" in clean_df.columns, "diaSourceId must be present"



def test_objectIds_withoutAlert_col_matches_json():
    """
    The function returns a list of diaObjectIds for rows where 'alert' is null.
    This test computes that list from the raw JSON and compares it to the function output.
    """
    # load raw JSON and compute which diaObjectIds have alert == NaN/None
    raw = pd.read_json(TEST_JSON)
    null_alert_ids = raw.loc[raw["alert"].isnull(), "diaObjectId"].tolist()

    _, missing = json2cleandf(TEST_JSON)

    # ensure same set (order may differ)
    assert set(missing) == set(null_alert_ids), (
        "The list of diaObjectIds reported as missing alert does not match the raw JSON."
    )

### mine
def test_json2cleandf():
    clean_df, objectIds_withoutAlert_col = json2cleandf(TEST_JSON)
    # NOTE: This is test file specific
    assert 'diaObjectId' in clean_df.columns, "diaObjectId column should exist in clean data frame"
    assert 'diaSourceId' in clean_df.columns, "diaSourceId column should exist in clean data frame"
    assert 'N_above_22' in clean_df.columns, "N_above_22 column should exist in clean data frame"
    assert clean_df.diaSourceId.shape[0] == clean_df.shape[0], "diaSourceId column should have same number of rows as clean data frame"
    assert clean_df.shape[0] == 32, "The clean data frame should have 32 rows. WARNING: TEST FILE SPECIFIC"
    assert clean_df.shape[1] == 137, "The clean data frame should have 137 columns. WARNING: TEST FILE SPECIFIC"


_THRESHOLD = 5_754  # mag 22 in nJy


class TestFluxThresholdFeatures:
    def _lc(self, fluxes, mjds):
        return pd.DataFrame({'psfFlux': fluxes, 'midpointMjdTai': mjds})

    def test_all_below_threshold(self):
        is_above, first_time, n = flux_threshold_features(
            self._lc([1000, 2000, 3000], [59000.0, 59001.0, 59002.0]), _THRESHOLD
        )
        assert n == 0
        assert is_above is False
        assert first_time is False

    def test_one_above_and_it_is_latest(self):
        is_above, first_time, n = flux_threshold_features(
            self._lc([1000, 2000, 6000], [59000.0, 59001.0, 59002.0]), _THRESHOLD
        )
        assert n == 1
        assert is_above is True
        assert first_time is True

    def test_one_above_but_not_latest(self):
        is_above, first_time, n = flux_threshold_features(
            self._lc([6000, 2000, 3000], [59000.0, 59001.0, 59002.0]), _THRESHOLD
        )
        assert n == 1
        assert is_above is True
        assert first_time is False

    def test_multiple_above_threshold(self):
        is_above, first_time, n = flux_threshold_features(
            self._lc([6000, 7000, 8000], [59000.0, 59001.0, 59002.0]), _THRESHOLD
        )
        assert n == 3
        assert is_above is True
        assert first_time is False


def _write_alert_json(tmp_path, rows):
    path = tmp_path / "alerts.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def _alert_row(dia_object_id, dia_source_ids=(1001,), fluxes=(1000,), mjds=(59000.0,)):
    sources = [
        {
            "diaObjectId": dia_object_id,
            "diaSourceId": dia_source_id,
            "psfFlux": flux,
            "midpointMjdTai": mjd,
        }
        for dia_source_id, flux, mjd in zip(dia_source_ids, fluxes, mjds)
    ]
    return {
        "diaObjectId": dia_object_id,
        "ra": 123.4,
        "decl": -45.6,
        "alert": {"diaSourcesList": sources},
    }


def test_json2cleandf_threshold_flags_are_computed_from_lightcurve(tmp_path):
    path = _write_alert_json(
        tmp_path,
        [
            _alert_row(
                42,
                dia_source_ids=(1001, 1002),
                fluxes=(1000, 6000),
                mjds=(59000.0, 59001.0),
            )
        ],
    )

    clean_df, missing = json2cleandf(path)

    assert missing == []
    row = clean_df.iloc[0]
    assert row["diaObjectId"] == 42
    assert row["diaSourceId"] == 1002
    assert row["N_above_22"] == 1
    assert bool(row["is_above_22"]) is True
    assert bool(row["first_time_22"]) is True
    assert row["N_above_21"] == 0
    assert bool(row["is_above_21"]) is False
    assert bool(row["first_time_21"]) is False


def test_json2cleandf_tracks_null_alert_rows_without_losing_valid_rows(tmp_path):
    path = _write_alert_json(
        tmp_path,
        [
            _alert_row(100),
            {
                "diaObjectId": 200,
                "ra": 123.4,
                "decl": -45.6,
                "alert": None,
            },
        ],
    )

    clean_df, missing = json2cleandf(path)

    assert clean_df["diaObjectId"].tolist() == [100]
    assert missing == [200]


def test_json2cleandf_preserves_duplicate_diaobjectid_alert_rows(tmp_path):
    path = _write_alert_json(
        tmp_path,
        [
            _alert_row(300, dia_source_ids=(3001,), fluxes=(1000,), mjds=(59000.0,)),
            _alert_row(300, dia_source_ids=(3002,), fluxes=(7000,), mjds=(59001.0,)),
        ],
    )

    clean_df, missing = json2cleandf(path)

    assert missing == []
    assert clean_df["diaObjectId"].tolist() == [300, 300]
    assert clean_df["diaSourceId"].tolist() == [3001, 3002]


def test_json2cleandf_raises_for_empty_diasources_list(tmp_path):
    path = _write_alert_json(
        tmp_path,
        [
            {
                "diaObjectId": 400,
                "ra": 123.4,
                "decl": -45.6,
                "alert": {"diaSourcesList": []},
            }
        ],
    )

    with pytest.raises(IndexError):
        json2cleandf(path)


def test_json2cleandf_raises_when_joined_object_ids_do_not_match(tmp_path):
    row = _alert_row(500)
    row["alert"]["diaSourcesList"][-1]["diaObjectId"] = 501
    path = _write_alert_json(tmp_path, [row])

    with pytest.raises(ValueError, match="diaObjectId"):
        json2cleandf(path)


def test_json2cleandf_raises_when_alert_column_is_missing(tmp_path):
    path = _write_alert_json(
        tmp_path,
        [
            {
                "diaObjectId": 600,
                "ra": 123.4,
                "decl": -45.6,
            }
        ],
    )

    with pytest.raises(KeyError):
        json2cleandf(path)
 
