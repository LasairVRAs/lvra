from lvra.utils.misc import sha256_of_file, set_up
from pathlib import Path
import os 

test_csv_path = Path(__file__).resolve().parent.parent /"data"/"test"/"test.csv"


# TEST SETUP FUNCTION
env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    SETTINGS_PATH = Path(env_settings)
else:                                            # or go to default file
    SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"

def test_set_up():
    setup_dict, logger = set_up(settings_path=SETTINGS_PATH,
                                log_name="test_utilsmisc.log")
    expected_keys = ['base_dir', 'json_dir', 'csv_dir', 'log_dir', 'log_db', 'endpoint']
    for key in expected_keys:
        assert key in setup_dict, f"Key '{key}' missing from setup_dict"



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