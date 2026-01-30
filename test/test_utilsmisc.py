from lvra.utils.misc import sha256_of_file
from pathlib import Path

test_csv_path = Path(__file__).resolve().parent.parent /"data"/"test"/"test.csv"

def test_sha256_of_file():
    expected_hash = "97ba3a1e1deaed49545954920f2ccfcece1b56216c54b692c10ad0f511ead6ac"
    computed_hash = sha256_of_file(test_csv_path)
    assert computed_hash == expected_hash

class TestCheckPckgVersions:

    def test_check_pckg_versions_correct(self):
        from lvra.utils.misc import check_pckg_versions, LVRA_ENV_FILE
        # This will raise an error if versions do not match
        result = check_pckg_versions(env_file=LVRA_ENV_FILE)
        assert result == 0
    
    def test_check_pckg_versions_bad_path(self):
        from lvra.utils.misc import check_pckg_versions
        import pytest
        bad_path = Path("/non/existent/path/lvra_env.yaml")
        with pytest.raises(FileNotFoundError):
            check_pckg_versions(env_file=bad_path)