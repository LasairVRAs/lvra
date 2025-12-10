from lvra.utils.misc import sha256_of_file
from pathlib import Path

test_csv_path = Path(__file__).resolve().parent.parent /"data"/"test"/"test.csv"

def test_sha256_of_file():
    expected_hash = "97ba3a1e1deaed49545954920f2ccfcece1b56216c54b692c10ad0f511ead6ac"
    computed_hash = sha256_of_file(test_csv_path)
    assert computed_hash == expected_hash