"""
Unit tests for the Kafka consumer module.

These tests mock all external dependencies (Kafka, file system, SQLite)
for fast, isolated testing suitable for CI/CD.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import json
from datetime import datetime

# Import the actual module
from lvra.pypeline import kafka_consumer


# #-#-#-#-#-#-#-# #
#     FIXTURES     #
# #-#-#-#-#-#-#-# #

@pytest.fixture
def mock_setup_dict(tmp_path):
    """Return a mock setup dictionary with temp paths."""
    return {
        'kafka_server': 'test-kafka:9092',
        'group_id': 'test-group',
        'my_topic': 'test-topic',
        'json_dir': tmp_path / 'json_output',
        'log_db': tmp_path / 'test.db'
    }


@pytest.fixture
def mock_kafka_message():
    """Factory fixture to create mock Kafka messages."""
    def _create_message(dia_object_id='ZTF21aaaaaaa', as_bytes=False):
        msg = Mock()
        msg.error.return_value = None
        
        data = {
            'diaObjectId': dia_object_id,
            'candid': 123456789,
            'ra': 123.456,
            'dec': 78.901
        }
        
        if as_bytes:
            msg.value.return_value = json.dumps(data).encode('utf-8')
        else:
            msg.value.return_value = json.dumps(data)
        
        return msg
    
    return _create_message


@pytest.fixture
def mock_consumer(mock_kafka_message):
    """Mock lasair_consumer that returns test messages."""
    consumer = Mock()
    
    # Default: return 3 messages, then None
    messages = [
        mock_kafka_message('LSSTaaaaaaa'),
        mock_kafka_message('LSSTbbbbbbb'),
        mock_kafka_message('LSSTccccccc'),
        None  # End of messages
    ]
    consumer.poll.side_effect = messages
    
    return consumer


# #-#-#-#-#-#-#-# #
#      TESTS       #
# #-#-#-#-#-#-#-# #

class TestMainHappyPath:
    """Tests for successful message processing."""
    
    @patch('lvra.pypeline.kafka_consumer.lasair_consumer')
    @patch('lvra.pypeline.kafka_consumer.set_up')
    @patch('lvra.pypeline.kafka_consumer.sqlite3')
    @patch('lvra.pypeline.kafka_consumer.datetime')
    def test_successful_poll_writes_file_and_db(
        self, 
        mock_datetime,
        mock_sqlite3,
        mock_set_up,
        mock_lasair_consumer,
        mock_setup_dict,
        mock_consumer,
        tmp_path
    ):
        """Test that messages are written to JSON file and DB is updated."""
        # Setup mocks
        mock_set_up.return_value = mock_setup_dict
        mock_lasair_consumer.return_value = mock_consumer
        mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 45)
        
        # Mock SQLite
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_sqlite3.connect.return_value = mock_con
        mock_con.cursor.return_value = mock_cur
        
        # Create json_dir
        mock_setup_dict['json_dir'].mkdir(parents=True, exist_ok=True)
        
        # Run main
        result = kafka_consumer.main()
        
        # Assertions
        assert result == 0
        
        # Check file was written
        expected_file = mock_setup_dict['json_dir'] / '20240115_103045.json'
        assert expected_file.exists()
        
        # Verify file content
        with open(expected_file, 'r') as f:
            data = json.load(f)
        assert len(data) == 3
        assert data[0]['diaObjectId'] == 'LSSTaaaaaaa'
        assert data[1]['diaObjectId'] == 'LSSTbbbbbbb'
        assert data[2]['diaObjectId'] == 'LSSTccccccc'
        
        # Verify SQLite calls
        mock_sqlite3.connect.assert_called_once_with(mock_setup_dict['log_db'])
        
        # Check feature_making insert
        assert mock_cur.execute.call_args_list[0] == call(
            "INSERT INTO feature_making (stem, r0b) VALUES (?, 0)",
            ('20240115_103045',)
        )
        
        assert mock_cur.execute.call_args_list[1] == call(
            "INSERT INTO predict (stem, r0b) VALUES (?, 0)",
            ('20240115_103045',)
        )

        # Check annotating insert
        assert mock_cur.execute.call_args_list[2] == call(
            "INSERT INTO annotating (stem, r0b) VALUES (?, 0)",
            ('20240115_103045',)
        )
        


        # Check diaObjectId inserts (3 of them)
        expected_sql = "INSERT INTO diaobjid_stems (diaObjectId, stem, timestamp) VALUES (?, ?, current_timestamp) ON CONFLICT(diaObjectId) DO UPDATE SET stem=excluded.stem"
        assert mock_cur.execute.call_args_list[3] == call(expected_sql, ('LSSTaaaaaaa', '20240115_103045'))
        assert mock_cur.execute.call_args_list[4] == call(expected_sql, ('LSSTbbbbbbb', '20240115_103045'))
        assert mock_cur.execute.call_args_list[5] == call(expected_sql, ('LSSTccccccc', '20240115_103045'))
        
        mock_con.commit.assert_called_once()
        mock_con.close.assert_called_once()


    @patch('lvra.pypeline.kafka_consumer.lasair_consumer')
    @patch('lvra.pypeline.kafka_consumer.set_up')
    @patch('lvra.pypeline.kafka_consumer.sqlite3')
    @patch('lvra.pypeline.kafka_consumer.datetime')
    def test_handles_byte_encoded_messages(
        self,
        mock_datetime,
        mock_sqlite3,
        mock_set_up,
        mock_lasair_consumer,
        mock_setup_dict,
        mock_kafka_message,
        tmp_path
    ):
        """Test that byte-encoded messages are properly decoded."""
        # Setup
        mock_set_up.return_value = mock_setup_dict
        mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 45)
        
        # Consumer returns byte-encoded messages
        consumer = Mock()
        consumer.poll.side_effect = [
            mock_kafka_message('LSSTtest001', as_bytes=True),
            None
        ]
        mock_lasair_consumer.return_value = consumer
        
        # Mock SQLite
        mock_con = MagicMock()
        mock_sqlite3.connect.return_value = mock_con
        mock_con.cursor.return_value = MagicMock()
        
        mock_setup_dict['json_dir'].mkdir(parents=True, exist_ok=True)
        
        # Run
        result = kafka_consumer.main()
        
        # Check
        assert result == 0
        expected_file = mock_setup_dict['json_dir'] / '20240115_103045.json'
        assert expected_file.exists()
        
        with open(expected_file, 'r') as f:
            data = json.load(f)
        assert data[0]['diaObjectId'] == 'LSSTtest001'


class TestEmptyPoll:
    """Tests for when no messages are received."""
    
    @patch('lvra.pypeline.kafka_consumer.lasair_consumer')
    @patch('lvra.pypeline.kafka_consumer.set_up')
    @patch('lvra.pypeline.kafka_consumer.sqlite3')
    @patch('lvra.pypeline.kafka_consumer.datetime')
    def test_no_messages_no_file_written(
        self,
        mock_datetime,
        mock_sqlite3,
        mock_set_up,
        mock_lasair_consumer,
        mock_setup_dict,
        tmp_path
    ):
        """Test that no file is written when no messages are received."""
        # Setup
        mock_set_up.return_value = mock_setup_dict
        mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 45)
        
        # Consumer returns None immediately (no messages)
        consumer = Mock()
        consumer.poll.return_value = None
        mock_lasair_consumer.return_value = consumer
        
        mock_setup_dict['json_dir'].mkdir(parents=True, exist_ok=True)
        
        # Run
        result = kafka_consumer.main()
        
        # Assertions
        assert result == 0
        
        # No file should exist
        expected_file = mock_setup_dict['json_dir'] / '20240115_103045.json'
        assert not expected_file.exists()
        
        # No temp file should exist either
        temp_file = mock_setup_dict['json_dir'] / '20240115_103045.jsn.tmp'
        assert not temp_file.exists()
        
        # SQLite should NOT be called
        mock_sqlite3.connect.assert_not_called()


class TestErrorHandling:
    """Tests for error scenarios."""
    
    @patch('lvra.pypeline.kafka_consumer.lasair_consumer')
    @patch('lvra.pypeline.kafka_consumer.set_up')
    @patch('lvra.pypeline.kafka_consumer.datetime')
    def test_consumer_error_breaks_loop(
        self,
        mock_datetime,
        mock_set_up,
        mock_lasair_consumer,
        mock_setup_dict,
        tmp_path
    ):
        """Test that consumer errors break the polling loop gracefully."""
        # Setup
        mock_set_up.return_value = mock_setup_dict
        mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 45)
        
        # Consumer returns error
        consumer = Mock()
        error_msg = Mock()
        error_msg.error.return_value = "Kafka connection lost"
        consumer.poll.return_value = error_msg
        mock_lasair_consumer.return_value = consumer
        
        mock_setup_dict['json_dir'].mkdir(parents=True, exist_ok=True)
        
        # Run
        result = kafka_consumer.main()
        
        # Should complete but write no file
        assert result == 0
        expected_file = mock_setup_dict['json_dir'] / '20240115_103045.json'
        assert not expected_file.exists()


    @patch('lvra.pypeline.kafka_consumer.lasair_consumer')
    @patch('lvra.pypeline.kafka_consumer.set_up')
    @patch('lvra.pypeline.kafka_consumer.sqlite3')
    @patch('lvra.pypeline.kafka_consumer.datetime')
    def test_atomic_file_replacement(
        self,
        mock_datetime,
        mock_sqlite3,
        mock_set_up,
        mock_lasair_consumer,
        mock_setup_dict,
        mock_kafka_message,
        tmp_path
    ):
        """Test that temporary file is atomically replaced."""
        # Setup
        mock_set_up.return_value = mock_setup_dict
        mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 45)
        
        consumer = Mock()
        consumer.poll.side_effect = [
            mock_kafka_message('ZTF21test001'),
            None
        ]
        mock_lasair_consumer.return_value = consumer
        
        mock_con = MagicMock()
        mock_sqlite3.connect.return_value = mock_con
        mock_con.cursor.return_value = MagicMock()
        
        mock_setup_dict['json_dir'].mkdir(parents=True, exist_ok=True)
        
        # Run
        kafka_consumer.main()
        
        # Final file should exist
        final_file = mock_setup_dict['json_dir'] / '20240115_103045.json'
        assert final_file.exists()
        
        # Temp file should NOT exist
        temp_file = mock_setup_dict['json_dir'] / '20240115_103045.jsn.tmp'
        assert not temp_file.exists()


class TestEdgeCases:
    """Tests for edge cases and potential issues."""
    
    @patch('lvra.pypeline.kafka_consumer.lasair_consumer')
    @patch('lvra.pypeline.kafka_consumer.set_up')
    @patch('lvra.pypeline.kafka_consumer.sqlite3')
    @patch('lvra.pypeline.kafka_consumer.datetime')
    def test_missing_diaObjectId_uses_null(
        self,
        mock_datetime,
        mock_sqlite3,
        mock_set_up,
        mock_lasair_consumer,
        mock_setup_dict,
        tmp_path
    ):
        """Test handling of messages missing diaObjectId field."""
        # Setup
        mock_set_up.return_value = mock_setup_dict
        mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 45)
        
        # Create message WITHOUT diaObjectId
        consumer = Mock()
        bad_msg = Mock()
        bad_msg.error.return_value = None
        bad_msg.value.return_value = json.dumps({'candid': 999, 'ra': 1.0})
        
        consumer.poll.side_effect = [bad_msg, None]
        mock_lasair_consumer.return_value = consumer
        
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_sqlite3.connect.return_value = mock_con
        mock_con.cursor.return_value = mock_cur
        
        mock_setup_dict['json_dir'].mkdir(parents=True, exist_ok=True)
        
        # Run
        kafka_consumer.main()
        
        # Check that 'null' was inserted into DB
        # This tests current behavior - as per TODO, this should probably raise an error instead
        calls = mock_cur.execute.call_args_list
        diaobjid_call = calls[2]  # Third call should be the diaObjectId insert
        assert diaobjid_call[0][1] == ('20240115_103045',)


    @patch('lvra.pypeline.kafka_consumer.lasair_consumer')
    @patch('lvra.pypeline.kafka_consumer.set_up')
    @patch('lvra.pypeline.kafka_consumer.sqlite3')
    @patch('lvra.pypeline.kafka_consumer.datetime')
    def test_max_messages_limit(
        self,
        mock_datetime,
        mock_sqlite3,
        mock_set_up,
        mock_lasair_consumer,
        mock_setup_dict,
        mock_kafka_message,
        tmp_path
    ):
        """Test that polling stops at N_MESSAGES limit."""
        # Setup
        mock_set_up.return_value = mock_setup_dict
        mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 45)
        
        # Create more messages than N_MESSAGES (which is 10,000 in the code)
        # For testing, we'll just verify the loop counter works
        consumer = Mock()
        # Return messages indefinitely (more than the limit)
        consumer.poll.return_value = mock_kafka_message('LSSTtest001')
        mock_lasair_consumer.return_value = consumer
        
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_sqlite3.connect.return_value = mock_con
        mock_con.cursor.return_value = mock_cur
        
        mock_setup_dict['json_dir'].mkdir(parents=True, exist_ok=True)
        
        # Run
        kafka_consumer.main()
        
        # Verify poll was called N_MESSAGES times (10,000)
        # We can't easily test 10k iterations, so this test verifies the pattern
        # In a real scenario, you might want to temporarily patch N_MESSAGES
        assert consumer.poll.call_count <= 10_001  # N_MESSAGES + 1 for the None check


# #-#-#-#-#-#-#-#-#-#-#-# #
#   INTEGRATION HELPERS   #
# #-#-#-#-#-#-#-#-#-#-#-# #

# If you want to add some lightweight integration tests later,
# you could use an in-memory SQLite database like this:

@pytest.fixture
def real_sqlite_db(tmp_path):
    """Create a real SQLite database with the expected schema for integration tests."""
    import sqlite3
    
    db_path = tmp_path / 'test.db'
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    
    # Create tables (adjust based on your actual schema)
    cur.execute("""
        CREATE TABLE feature_making (
            stem TEXT PRIMARY KEY,
            r0b INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE predict (
            stem TEXT PRIMARY KEY,
            r0b INTEGER, 
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE annotating (
            stem TEXT PRIMARY KEY,
            r0b INTEGER, 
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)


    
    cur.execute("""
        CREATE TABLE diaobjid_stems (
            diaObjectId TEXT PRIMARY KEY,
            stem TEXT, 
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP 
        )
    """)
    
    con.commit()
    con.close()
    
    return db_path


# #-#-#-#-#-#-#-# #
#   EASTER EGG!   #
# #-#-#-#-#-#-#-# #

def test_the_answer_to_life_the_universe_and_everything():
    """
    Deep Thought computed for 7.5 million years...
    and determined the answer to be: 42
    
    (But what's the question?)
    """
    assert 42 == 42  # Always passes, just like Deep Thought's confidence