# Claude wrote this for LVRA v2 (2026-10-21)
import sqlite3
from pathlib import Path

import pytest

from test.helpers import initialise_log_db

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATION = REPO_ROOT / "data" / "migrations" / "2026-10-20_add_lvra_columns.sql"
TABLES = ("feature_making", "predict", "annotating")
OLD_SCHEMA = "\n".join(
    f"CREATE TABLE {t} (stem TEXT PRIMARY KEY, timestamp TEXT NOT NULL DEFAULT current_timestamp, r0b INTEGER);"
    for t in TABLES
)


@pytest.fixture
def old_db(tmp_path):
    con = sqlite3.connect(tmp_path / "old_log.db")
    con.executescript(OLD_SCHEMA)
    for t in TABLES:
        con.execute(f"INSERT INTO {t} (stem, r0b) VALUES ('20260101_000000', 1)")
    con.commit()
    return con


def migrate(con):
    con.executescript(MIGRATION.read_text())


def columns(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def test_migration_old_stems_null_new_stems_zero(old_db):
    migrate(old_db)
    for t in TABLES:
        old_db.execute(f"INSERT INTO {t} (stem, r0b) VALUES ('20261101_000000', 0)")
    for t in TABLES:
        rows = dict(old_db.execute(f"SELECT stem, lvra FROM {t}").fetchall())
        assert rows == {"20260101_000000": None, "20261101_000000": 0}


def test_migration_keeps_r0b_values(old_db):
    migrate(old_db)
    for t in TABLES:
        assert old_db.execute(f"SELECT r0b FROM {t}").fetchall() == [(1,)]


def test_migrated_schema_matches_fresh_schema_columns(old_db, tmp_path):
    migrate(old_db)
    fresh = sqlite3.connect(initialise_log_db(tmp_path / "fresh_log.db"))
    for t in TABLES:
        assert columns(old_db, t) == columns(fresh, t)


def test_second_run_fails_and_keeps_progress(old_db):
    migrate(old_db)
    old_db.execute("UPDATE feature_making SET lvra = 1")
    old_db.commit()
    with pytest.raises(sqlite3.OperationalError):
        migrate(old_db)
    old_db.rollback()
    assert old_db.execute("SELECT lvra FROM feature_making").fetchall() == [(1,)]
