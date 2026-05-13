import sqlite3
from pathlib import Path

import pytest

from test.helpers import LOG_SCHEMA_PATH, initialise_log_db


@pytest.fixture
def log_schema_path() -> Path:
    return LOG_SCHEMA_PATH


@pytest.fixture
def log_db_path(tmp_path) -> Path:
    return initialise_log_db(tmp_path / "log.db")


@pytest.fixture
def log_db_connection(log_db_path):
    connection = sqlite3.connect(log_db_path)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def log_db_cursor(log_db_connection):
    return log_db_connection.cursor()
