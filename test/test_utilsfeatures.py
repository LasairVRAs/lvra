from lvra.utils.features import json2cleandf
from pathlib import Path

test_json_path = Path(__file__).resolve().parent.parent / "data" / "test" /"20260202_102448.json"
test_csv_path = Path(__file__).resolve().parent.parent / "data" / "test" /"20260202_102448.csv"


def test_json2cleandf():
    clean_df = json2cleandf(test_json_path)
    # NOTE: This is test file specific
    assert clean_df.shape[0] == 44, "The clean data frame should have 44 rows. WARNING: TEST FILE SPECIFIC"
    assert clean_df.shape[1] == 119, "The clean data frame should have 119 columns. WARNING: TEST FILE SPECIFIC"
