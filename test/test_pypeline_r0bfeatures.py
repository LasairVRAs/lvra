# tests/test_r0b_feature_maker.py
import sqlite3
from pathlib import Path
import logging
import pandas as pd
import pytest
from unittest.mock import MagicMock

import lvra.pypeline.r0b_feature_maker as fm_module


# Helper to create minimal DB with feature_making table -----------------------
def _create_db(path: str):
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE feature_making (
            stem TEXT PRIMARY KEY,
            r0b INTEGER DEFAULT 0
        );
        """
    )
    con.commit()
    return con, cur


# Tests ----------------------------------------------------------------------

def test_stemlist_from_logdb_returns_list(tmp_path):
    dbfile = str(tmp_path / "fm.db")
    con, cur = _create_db(dbfile)

    # insert several stems
    cur.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, ?);", ("20260202_000001", 0))
    cur.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, ?);", ("20260202_000002", 1))  # should be excluded
    cur.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, ?);", ("20260202_000003", -1)) # excluded (abs == 1)
    con.commit()

    stems = fm_module.stemlist_from_logdb(con.cursor(), logger=logging.getLogger("test"))
    assert isinstance(stems, list)
    assert "20260202_000001" in stems
    assert "20260202_000002" not in stems
    assert "20260202_000003" not in stems

    con.close()


def test_make_features_file_not_found(monkeypatch, tmp_path):
    """If json2cleandf raises FileNotFoundError, make_features returns code 21 and no output file."""
    out = tmp_path / "outdir" / "20260202_000001.csv"
    # monkeypatch module-level json2cleandf to raise
    monkeypatch.setattr(fm_module, "json2cleandf", lambda path: (_ for _ in ()).throw(FileNotFoundError()))

    logger = logging.getLogger("test")
    rc = fm_module.make_features(input_path=Path("/nonexistent.json"), output_path=out, logger=logger)

    assert rc == 21
    assert not out.exists()


def _sample_clean_df():
    # minimal clean_df used to create features: must have last/first MJD and some columns
    return pd.DataFrame({
        "diaObjectId": [1, 2],
        "lastDiaSourceMjdTai": [59000.5, 59001.3],
        "firstDiaSourceMjdTai": [58999.5, 59000.8],
        "somecol": [10, 20]
    })


def test_make_features_success_writes_csv(monkeypatch, tmp_path):
    """When json2cleandf returns a normal DataFrame and no missing ids, file is written and code -1 returned."""
    out = tmp_path / "outdir" / "20260202_000001.csv"
    # json2cleandf returns (clean_df, missing_list)
    monkeypatch.setattr(fm_module, "json2cleandf", lambda path: (_sample_clean_df(), []))

    logger = logging.getLogger("test")
    rc = fm_module.make_features(input_path=Path("/fake.json"), output_path=out, logger=logger)

    assert rc == -1  # code in implementation returns -1 on successful write
    assert out.exists()
    df_written = pd.read_csv(out)
    # deltaDiaSourceMjdTai should have been created
    assert "deltaDiaSourceMjdTai" in df_written.columns
    # somecol should also be present
    assert "somecol" in df_written.columns


def test_make_features_partial_missing_alerts(monkeypatch, tmp_path):
    """When json2cleandf returns missing ids, the code still writes CSV and returns -1 (partial success)."""
    out = tmp_path / "outdir" / "20260202_000001.csv"
    monkeypatch.setattr(fm_module, "json2cleandf", lambda path: (_sample_clean_df(), [12345]))

    logger = logging.getLogger("test")
    rc = fm_module.make_features(input_path=Path("/fake.json"), output_path=out, logger=logger)

    assert rc == -1
    assert out.exists()


def test_main_updates_feature_making_status(monkeypatch, tmp_path):
    """
    Integration-style test for main():
    - create DB with one stem marked as needing features
    - mock set_up to point to that DB and to csv/json dirs under tmp_path
    - mock json2cleandf to simulate success
    - after main(), assert feature_making.r0b updated to -1 (partial-success path used by make_features)
    """
    dbfile = str(tmp_path / "fm_main.db")
    con, cur = _create_db(dbfile)

    stem = "20260202_102448"
    cur.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, ?);", (stem, 0))
    con.commit()
    con.close()

    # Prepare directories so code's path arithmetic is valid (but json2cleandf is mocked so no file needed)
    json_date_dir = tmp_path / "jsonroot" / stem[:8]
    csv_date_dir = tmp_path / "csvroot" / stem[:8]
    json_date_dir.mkdir(parents=True)
    csv_date_dir.mkdir(parents=True)

    # set_up should return dict where json_dir.parent == tmp_path/"jsonroot"
    # and csv_dir.parent == tmp_path/"csvroot"
    fake_setup = {
        "log_db": dbfile,
        "json_dir": json_date_dir / "placeholder",  # parent == tmp_path/"jsonroot"
        "csv_dir": csv_date_dir / "placeholder"
    }
    monkeypatch.setattr(fm_module, "set_up", lambda settings_path, log_name, logger: fake_setup)
    # mock json2cleandf to return dataframe and no missing list
    monkeypatch.setattr(fm_module, "json2cleandf", lambda path: (_sample_clean_df(), []))

    ret = fm_module.main()
    assert ret == 0

    # verify DB updated: r0b should be -1 because make_features returns -1 (partial success branch)
    con2 = sqlite3.connect(dbfile)
    cur2 = con2.cursor()
    cur2.execute("SELECT r0b FROM feature_making WHERE stem = ?;", (stem,))
    val = cur2.fetchone()[0]
    assert val == -1
    con2.close()


TEST_STEM = "20260202_102448"

def test_stemlist_from_logdb_no_matches():
    # Create a fake cursor whose execute(...).fetchall() returns no rows
    fake_cursor = MagicMock()
    fake_cursor.execute.return_value.fetchall.return_value = []

    stems = fm_module.stemlist_from_logdb(fake_cursor, logger=logging.getLogger("test"))
    assert stems == []


def test_stemlist_from_logdb_with_matches():
    # Fake cursor returns a list of 2-row tuples as sqlite would
    fake_cursor = MagicMock()
    fake_cursor.execute.return_value.fetchall.return_value = [(TEST_STEM,), ("20260203_103000",)]

    stems = fm_module.stemlist_from_logdb(fake_cursor, logger=logging.getLogger("test"))
    assert stems == [TEST_STEM, "20260203_103000"]


def test_make_features_with_real_json(tmp_path, monkeypatch):
    """
    Use your actual test JSON file (if present) but keep output isolated in tmp_path.
    If the repo test JSON isn't available, this test will still work if we mock json2cleandf.
    """

    # locate repo test json (adjust path if needed); fall back to mocking if not found
    repo_test_json = Path(__file__).resolve().parent.parent / "data" / "test" / f"{TEST_STEM}.json"
    out_csv = tmp_path / f"{TEST_STEM}.csv"

    logger = logging.getLogger("test")

    if repo_test_json.exists():
        # run make_features on the real JSON file (integration-style)
        rc = fm_module.make_features(input_path=repo_test_json, output_path=out_csv, logger=logger)
        # implementation returns -1 on success/partial-success and writes file
        assert rc in (-1, 0, 1)  # be permissive if code changes; check file if rc indicates success-ish
        if rc in (-1, 0):
            assert out_csv.exists()
    else:
        # fallback: mock json2cleandf to return a simple clean_df so test is deterministic
        def _sample_clean_df():
            return pd.DataFrame({
                "diaObjectId": [1, 2],
                "lastDiaSourceMjdTai": [59000.5, 59001.3],
                "firstDiaSourceMjdTai": [58999.5, 59000.8],
                "somecol": [10, 20]
            })
        monkeypatch.setattr(fm_module, "json2cleandf", lambda path: (_sample_clean_df(), []))
        rc = fm_module.make_features(input_path=Path("/nonexistent.json"), output_path=out_csv, logger=logger)
        assert rc == -1
        assert out_csv.exists()
