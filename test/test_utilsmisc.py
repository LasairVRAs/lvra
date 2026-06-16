"""
WRITTEN BY CLAUDE SONNET 4.5
Unit tests for lvra.utils.misc module.

Tests the critical setup and config-reading functions that are used
at the start of most pipelines. Ensures config validation and prevents
accidental breakage from typos or missing fields.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import yaml
from datetime import datetime
import logging

from lvra.utils import misc


# #-#-#-#-#-#-#-# #
#     FIXTURES     #
# #-#-#-#-#-#-#-# #

@pytest.fixture
def valid_settings_config(tmp_path):
    """Return a valid settings configuration dictionary."""
    return {
        'kafka_server': 'kafka.example.com:9092',
        'my_topic': 'lasair_topic',
        'group_id': 'test_group_123',
        'base_dir': str(tmp_path / "base"),
        'endpoint': 'https://lasair.example.com/api'
    }


@pytest.fixture
def valid_model_config():
    """Return a valid model configuration dictionary."""
    return {
        'MODEL_PATH': '/models/classifier_v1',
        'MODEL_NAME': 'Classifier',
        'MODEL_VERSION': 'v1.2.3',
        'TOPIC_OUT': 'predictions',
        'EXPLANATION': 'Classifies transient events',
        'URL': 'https://model-docs.example.com'
    }


@pytest.fixture
def mock_logger():
    """Return a mock logger for testing."""
    return Mock(spec=logging.Logger)


@pytest.fixture
def temp_settings_file(tmp_path, valid_settings_config):
    """Create a temporary valid settings YAML file."""
    settings_file = tmp_path / "test_settings.yaml"
    with open(settings_file, 'w') as f:
        yaml.dump(valid_settings_config, f)
    return settings_file


@pytest.fixture
def temp_model_config_file(tmp_path, valid_model_config):
    """Create a temporary valid model config YAML file."""
    config_file = tmp_path / "test_model_config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(valid_model_config, f)
    return config_file


# #-#-#-#-#-#-#-#-#-#-# #
#   TESTS: set_up()     #
# #-#-#-#-#-#-#-#-#-#-# #

class TestSetUpFunction:
    """Tests for the set_up() function."""
    
    @patch('lvra.utils.misc.datetime')
    @patch('lvra.utils.misc.logging')
    def test_creates_correct_directory_structure(
        self,
        mock_logging,
        mock_datetime,
        temp_settings_file,
        mock_logger,
        tmp_path
    ):
        """Test that set_up creates the correct directory structure."""
        # Mock datetime to get predictable paths
        mock_datetime.utcnow.return_value = datetime(2026, 1, 27, 10, 30, 45)
        
        # Run set_up
        result = misc.set_up(
            settings_path=temp_settings_file,
            log_name="test.log",
            logger=mock_logger
        )
        
        # Verify the returned dictionary has all required keys
        expected_keys = [
            'kafka_server', 'my_topic', 'group_id', 'base_dir',
            'json_dir', 'csv_dir', 'log_dir', 'log_db', 'endpoint'
        ]
        assert all(key in result for key in expected_keys)
        
        # Verify directory paths are correct
        base = tmp_path / "base"
        assert result['json_dir'] == base / "JSON" / "2026" / "20260127"
        assert result['csv_dir'] == base / "csv" / "2026" / "20260127"
        assert result['log_dir'] == base / "logs" / "2026" / "20260127"
        assert result['log_db'] == base / "db" / "log.db"
        
        # Verify log directory was created
        assert result['log_dir'].exists()
        
        # Verify logger was called
        mock_logger.info.assert_called_with("[INIT] - SET UP COMPLETE")


    @patch('lvra.utils.misc.datetime')
    @patch('lvra.utils.misc.logging')
    def test_reads_all_config_fields_correctly(
        self,
        mock_logging,
        mock_datetime,
        temp_settings_file,
        mock_logger,
        valid_settings_config
    ):
        """Test that all config fields are read and stored correctly."""
        mock_datetime.utcnow.return_value = datetime(2026, 1, 27, 10, 30, 45)
        
        result = misc.set_up(
            settings_path=temp_settings_file,
            log_name="test.log",
            logger=mock_logger
        )
        
        # Verify all config values match
        assert result['kafka_server'] == valid_settings_config['kafka_server']
        assert result['my_topic'] == valid_settings_config['my_topic']
        assert result['group_id'] == valid_settings_config['group_id']
        assert result['endpoint'] == valid_settings_config['endpoint']
        assert result['base_dir'] == Path(valid_settings_config['base_dir'])


    @patch('lvra.utils.misc.datetime')
    @patch('lvra.utils.misc.logging')
    def test_creates_subdirs_with_different_dates(
        self,
        mock_logging,
        mock_datetime,
        temp_settings_file,
        mock_logger,
        tmp_path
    ):
        """Test that subdirectory structure changes with date."""
        # Test with different date
        mock_datetime.utcnow.return_value = datetime(2025, 12, 31, 23, 59, 59)
        
        result = misc.set_up(
            settings_path=temp_settings_file,
            log_name="test.log",
            logger=mock_logger
        )
        
        base = tmp_path / "base"
        assert result['json_dir'] == base / "JSON" / "2025" / "20251231"
        assert result['csv_dir'] == base / "csv" / "2025" / "20251231"
        assert result['log_dir'] == base / "logs" / "2025" / "20251231"


    @patch('lvra.utils.misc.logging')
    def test_missing_config_field_raises_error(
        self,
        mock_logging,
        tmp_path,
        mock_logger
    ):
        """Test that missing required config fields cause an error."""
        # Create config missing 'endpoint' field
        incomplete_config = {
            'kafka_server': 'kafka.example.com:9092',
            'my_topic': 'lasair_topic',
            'group_id': 'test_group_123',
            'base_dir': '/tmp/test_base',
            # 'endpoint' is missing!
        }
        
        settings_file = tmp_path / "incomplete_settings.yaml"
        with open(settings_file, 'w') as f:
            yaml.dump(incomplete_config, f)
        
        # Should raise KeyError for missing field
        with pytest.raises(KeyError):
            misc.set_up(
                settings_path=settings_file,
                log_name="test.log",
                logger=mock_logger
            )


    @patch('lvra.utils.misc.logging')
    def test_invalid_yaml_syntax_raises_error(
        self,
        mock_logging,
        tmp_path,
        mock_logger
    ):
        """Test that invalid YAML syntax is handled."""
        # Create file with invalid YAML
        bad_yaml_file = tmp_path / "bad_syntax.yaml"
        with open(bad_yaml_file, 'w') as f:
            f.write("kafka_server: kafka.example.com\n")
            f.write("  bad_indent: value\n")
            f.write("my_topic: [unclosed bracket\n")
        
        # Should raise YAML parsing error
        with pytest.raises(yaml.YAMLError):
            misc.set_up(
                settings_path=bad_yaml_file,
                log_name="test.log",
                logger=mock_logger
            )


    @patch('lvra.utils.misc.logging')
    def test_nonexistent_config_file_raises_error(
        self,
        mock_logging,
        mock_logger
    ):
        """Test that missing config file raises FileNotFoundError."""
        nonexistent_file = Path("/this/does/not/exist.yaml")
        
        with pytest.raises(FileNotFoundError):
            misc.set_up(
                settings_path=nonexistent_file,
                log_name="test.log",
                logger=mock_logger
            )


    @patch('lvra.utils.misc.datetime')
    @patch('lvra.utils.misc.logging')
    def test_log_directory_creation_with_nested_paths(
        self,
        mock_logging,
        mock_datetime,
        tmp_path,
        mock_logger
    ):
        """Test that deeply nested log directories are created correctly."""
        mock_datetime.utcnow.return_value = datetime(2026, 1, 27, 10, 30, 45)
        
        # Use a base_dir that doesn't exist yet
        config = {
            'kafka_server': 'kafka.example.com:9092',
            'my_topic': 'lasair_topic',
            'group_id': 'test_group_123',
            'base_dir': str(tmp_path / "deeply" / "nested" / "base"),
            'endpoint': 'https://lasair.example.com/api'
        }
        
        settings_file = tmp_path / "nested_settings.yaml"
        with open(settings_file, 'w') as f:
            yaml.dump(config, f)
        
        result = misc.set_up(
            settings_path=settings_file,
            log_name="test.log",
            logger=mock_logger
        )
        
        # Verify the deeply nested directory was created
        assert result['log_dir'].exists()
        assert result['log_dir'].is_dir()


# #-#-#-#-#-#-#-#-#-#-#-#-#-# #
#   TESTS: read_model_config() #
# #-#-#-#-#-#-#-#-#-#-#-#-#-# #

class TestReadModelConfig:
    """Tests for the read_model_config() function."""
    
    def test_successfully_reads_valid_config(
        self,
        temp_model_config_file,
        mock_logger,
        valid_model_config
    ):
        """Test that a valid model config is read correctly."""
        result, status_code = misc.read_model_config(
            path=temp_model_config_file,
            logger=mock_logger
        )
        
        # Verify successful return
        assert status_code == 0
        assert result is not None
        
        # Verify all fields match
        assert result['MODEL_PATH'] == valid_model_config['MODEL_PATH']
        assert result['MODEL_NAME'] == valid_model_config['MODEL_NAME']
        assert result['MODEL_VERSION'] == valid_model_config['MODEL_VERSION']
        assert result['TOPIC_OUT'] == valid_model_config['TOPIC_OUT']
        assert result['EXPLANATION'] == valid_model_config['EXPLANATION']
        assert result['URL'] == valid_model_config['URL']
        
        # Verify logger was called
        mock_logger.info.assert_called_with("[MODEL CONFIG] Successfully Loaded ")


    def test_missing_config_file_returns_error(
        self,
        mock_logger
    ):
        """Test that missing config file returns status code 21."""
        nonexistent_file = Path("/this/does/not/exist.yaml")
        
        result, status_code = misc.read_model_config(
            path=nonexistent_file,
            logger=mock_logger
        )
        
        # Verify error return
        assert status_code == 21
        assert result is None
        
        # Verify error was logged
        assert mock_logger.error.called
        error_msg = mock_logger.error.call_args[0][0]
        assert "[MODEL CONFIG]" in error_msg


    def test_missing_required_field_returns_error(
        self,
        tmp_path,
        mock_logger
    ):
        """Test that missing required field returns status code 99."""
        # Create config missing MODEL_VERSION
        incomplete_config = {
            'MODEL_PATH': '/models/classifier_v1',
            'MODEL_NAME': 'Classifier',
            # 'MODEL_VERSION' is missing!
            'TOPIC_OUT': 'predictions',
            'EXPLANATION': 'Classifies transient events',
            'URL': 'https://model-docs.example.com'
        }
        
        config_file = tmp_path / "incomplete_model_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(incomplete_config, f)
        
        result, status_code = misc.read_model_config(
            path=config_file,
            logger=mock_logger
        )
        
        # Verify error return
        assert status_code == 99
        assert result is None
        
        # Verify error was logged
        assert mock_logger.error.called
        error_msg = mock_logger.error.call_args[0][0]
        assert "[MODEL CONFIG] Failed to load" in error_msg


    def test_invalid_yaml_returns_error(
        self,
        tmp_path,
        mock_logger
    ):
        """Test that invalid YAML returns status code 99."""
        bad_yaml_file = tmp_path / "bad_model_config.yaml"
        with open(bad_yaml_file, 'w') as f:
            f.write("MODEL_PATH: /models/test\n")
            f.write("MODEL_NAME: [unclosed\n")
        
        result, status_code = misc.read_model_config(
            path=bad_yaml_file,
            logger=mock_logger
        )
        
        # Verify error return
        assert status_code == 99
        assert result is None
        
        # Verify error was logged
        assert mock_logger.error.called


    def test_all_required_fields_present(
        self,
        tmp_path,
        mock_logger
    ):
        """Test that all six required fields must be present."""
        required_fields = [
            'MODEL_PATH', 'MODEL_NAME', 'MODEL_VERSION',
            'TOPIC_OUT', 'EXPLANATION', 'URL'
        ]
        
        # Test each field individually being missing
        for missing_field in required_fields:
            config = {
                'MODEL_PATH': '/models/classifier_v1',
                'MODEL_NAME': 'Classifier',
                'MODEL_VERSION': 'v1.2.3',
                'TOPIC_OUT': 'predictions',
                'EXPLANATION': 'Classifies transient events',
                'URL': 'https://model-docs.example.com'
            }
            
            # Remove the field we're testing
            del config[missing_field]
            
            config_file = tmp_path / f"missing_{missing_field}.yaml"
            with open(config_file, 'w') as f:
                yaml.dump(config, f)
            
            result, status_code = misc.read_model_config(
                path=config_file,
                logger=mock_logger
            )
            
            # Should fail with status code 99
            assert status_code == 99, f"Missing {missing_field} should cause error"
            assert result is None


# #-#-#-#-#-#-#-#-#-#-#-#-# #
#   INTEGRATION TESTS       #
# #-#-#-#-#-#-#-#-#-#-#-#-# #

class TestConfigValidation:
    """Integration tests for real-world config scenarios."""
    
    @patch('lvra.utils.misc.datetime')
    @patch('lvra.utils.misc.logging')
    def test_typo_in_field_name_causes_failure(
        self,
        mock_logging,
        mock_datetime,
        tmp_path,
        mock_logger
    ):
        """Test that typos in field names are caught (common mistake!)."""
        mock_datetime.utcnow.return_value = datetime(2026, 1, 27, 10, 30, 45)
        
        # Config with typo: 'kafka_sever' instead of 'kafka_server'
        typo_config = {
            'kafka_sever': 'kafka.example.com:9092',  # TYPO!
            'my_topic': 'ztf_topic',
            'group_id': 'test_group_123',
            'base_dir': str(tmp_path / "base"),
            'endpoint': 'https://lasair.example.com/api'
        }
        
        settings_file = tmp_path / "typo_settings.yaml"
        with open(settings_file, 'w') as f:
            yaml.dump(typo_config, f)
        
        # Should raise KeyError due to missing 'kafka_server'
        with pytest.raises(KeyError) as exc_info:
            misc.set_up(
                settings_path=settings_file,
                log_name="test.log",
                logger=mock_logger
            )
        
        assert 'kafka_server' in str(exc_info.value)


    def test_model_config_typo_causes_failure(
        self,
        tmp_path,
        mock_logger
    ):
        """Test that typos in model config field names are caught."""
        # Config with typo: 'MODEL_NANE' instead of 'MODEL_NAME'
        typo_config = {
            'MODEL_PATH': '/models/classifier_v1',
            'MODEL_NANE': 'Classifierefe',  # TYPO!
            'MODEL_VERSION': 'v1.2.3',
            'TOPIC_OUT': 'predictions',
            'EXPLANATION': 'Classifies transient events',
            'URL': 'https://model-docs.example.com'
        }
        
        config_file = tmp_path / "typo_model_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(typo_config, f)
        
        result, status_code = misc.read_model_config(
            path=config_file,
            logger=mock_logger
        )
        
        # Should fail due to missing MODEL_NAME
        assert status_code == 99
        assert result is None

    # Test that the log_dir, csv_dir and json_dir exist!
    @patch('lvra.utils.misc.datetime')
    @patch('lvra.utils.misc.logging')
    def test_directory_creation_and_existence(
        self,
        mock_logging,
        mock_datetime,
        temp_settings_file,
        mock_logger
    ):
        """Test that set_up creates the log, csv and json directories and they exist."""
        mock_datetime.utcnow.return_value = datetime(2026, 1, 27, 10, 30, 45)
        
        result = misc.set_up(
            settings_path=temp_settings_file,
            log_name="test.log",
            logger=mock_logger
        )
        
        # Verify directories were created and exist
        assert result['log_dir'].exists() and result['log_dir'].is_dir()
        assert result['csv_dir'].exists() and result['csv_dir'].is_dir()
        assert result['json_dir'].exists() and result['json_dir'].is_dir()



### MY OLD TESTS ###
test_csv_path = Path(__file__).resolve().parent.parent /"data"/"test"/"test.csv"

def test_sha256_of_file():
    expected_hash = "97ba3a1e1deaed49545954920f2ccfcece1b56216c54b692c10ad0f511ead6ac"
    computed_hash = misc.sha256_of_file(test_csv_path)
    assert computed_hash == expected_hash

class TestCheckPckgVersions:

    def test_check_pckg_versions_correct(self):
        from lvra.utils.misc import check_pckg_versions, LVRA_ENV_FILE
        # This will raise an error if versions do not match
        result = check_pckg_versions(env_file=LVRA_ENV_FILE)
        assert result == 0
    
    def test_check_pckg_versions_bad_path(self):
        from lvra.utils.misc import check_pckg_versions
        bad_path = Path("/non/existent/path/lvra_env.yaml")
        with pytest.raises(FileNotFoundError):
            check_pckg_versions(env_file=bad_path)