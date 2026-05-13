import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_SCHEMA_PATH = REPO_ROOT / "data" / "log_schema.sql"


def initialise_log_db(db_path: Path, schema_path: Path = LOG_SCHEMA_PATH) -> Path:
    """Create a log DB from the canonical LVRA SQLite schema."""
    with sqlite3.connect(db_path) as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
    return db_path
