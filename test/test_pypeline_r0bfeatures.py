from unittest.mock import patch, MagicMock
import pytest
from lvra.pypeline.r0b_feature_maker import stemlist_from_logdb, make_features
from lvra.utils.features import json2cleandf
from lvra.utils.misc import set_up
from pathlib import Path


TEST_STEM = '20260202_102448'
test_json_path = Path(__file__).resolve().parent.parent / "data" / "test" /"20260202_102448.json"

@patch('lvra.pypeline.r0b_feature_maker.sqlite3')
def test_stemlist_from_logdb_no_matches(mock_sqlite3):
    # Mock the cursor and its execute method to return no results
    mock_cursor = MagicMock()
    mock_cursor.execute.return_value.fetchall.return_value = []
    
    stem_list = stemlist_from_logdb(mock_cursor, logger=MagicMock())
    
    assert stem_list == []

@patch('lvra.pypeline.r0b_feature_maker.sqlite3')
def test_stemlist_from_logdb_with_matches(mock_sqlite3):
    # Mock the cursor and its execute method to return some results
    mock_cursor = MagicMock()
    mock_cursor.execute.return_value.fetchall.return_value = [(TEST_STEM,), ('20260203_103000',)]
    
    stem_list = stemlist_from_logdb(mock_cursor, logger=MagicMock())
    
    assert stem_list == [TEST_STEM, '20260203_103000']

# test make_features
def test_make_features():
    # Use a mock setup_dict
    setup_dict = {
        'csv_path': Path('/tmp/csv.csv')  # Use a temp directory for testing
    }
    logger = MagicMock()
    
    # Call make_features
    make_features(test_json_path, 
                  setup_dict['csv_path'], 
                  logger = logger)
    
    # Check that the CSV file was created
    expected_csv_path = setup_dict['csv_path']
    assert expected_csv_path.exists()
    
    # Clean up the created file
    expected_csv_path.unlink()

    

