# Chat gpt 5.2 wrote most of these tests
from pathlib import Path
import pandas as pd

from lvra.utils.features import json2cleandf

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
 