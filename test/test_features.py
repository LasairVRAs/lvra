from lvra.features import FeaturesRealBogus
from pathlib import Path

test_json_path = Path(__file__).resolve().parent.parent / "data" / "test" /"test.json"

def test_featuresRB_from_json():
    features = FeaturesRealBogus.from_json(test_json_path)
    assert features.shape[0] == 2
    assert features.shape[1] == len(FeaturesRealBogus.columns)