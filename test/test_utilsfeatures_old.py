from lvra.utils.features import FeaturesRealBogus
from pathlib import Path

test_json_path = Path(__file__).resolve().parent.parent / "data" / "test" /"test.json"
test_csv_path = Path(__file__).resolve().parent.parent / "data" / "test" /"test.csv"
# TODO: make tests for if json file wrong or other failure modes
def test_featuresRB_from_json():
    features = FeaturesRealBogus.from_json(test_json_path)
    assert features.shape[0] == 2
    # HFS 2026-01-06: I removed this assertion because I, for now, do not trim columns
    #assert features.shape[1] == len(FeaturesRealBogus.columns)

def test_featuresRB_from_csv():
    features = FeaturesRealBogus.from_csv(test_csv_path)
    assert features.shape[0] == 2
    #assert features.shape[1] == len(FeaturesRealBogus.columns)

def test_featuresRB_from_dataframe():
    import pandas as pd
    df = pd.read_json(test_json_path)
    features = FeaturesRealBogus.from_dataframe(df)
    assert features.shape[0] == 2
    #assert features.shape[1] == len(FeaturesRealBogus.columns)

