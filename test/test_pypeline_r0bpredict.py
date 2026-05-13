# tests/test_r0b_predict.py
import sqlite3
import joblib
import logging
from pathlib import Path
import pandas as pd

import lvra.pypeline.r0b_predict as predict_module
from test.helpers import initialise_log_db

# Helpers --------------------------------------------------------------------

def _create_db(path: str):
    """Create a sqlite DB from the canonical production schema."""
    initialise_log_db(Path(path))
    con = sqlite3.connect(path)
    cur = con.cursor()
    return con, cur

# Tests ----------------------------------------------------------------------

def test_stemlist_from_log_returns_stems(tmp_path):
    dbfile = str(tmp_path / "stems.db")
    con, cur = _create_db(dbfile)

    # Insert rows: predict.r0b != 1 and feature_making.r0b == 1 => should be selected
    cur.execute("INSERT INTO predict (stem, r0b) VALUES (?, ?);", ("stemA", 0))
    cur.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, ?);", ("stemA", 1))
    # Insert another which should NOT be selected
    cur.execute("INSERT INTO predict (stem, r0b) VALUES (?, ?);", ("stemB", 1))
    cur.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, ?);", ("stemB", 1))
    con.commit()

    # Use cursor with row_factory that returns dict-like rows (what function expects)
    con_rf = sqlite3.connect(dbfile)
    con_rf.row_factory = lambda cursor, row: {col[0]: row[i] for i, col in enumerate(cursor.description)}
    cur_rf = con_rf.cursor()

    stems = predict_module.stemlist_from_log(sqlite_cursor=cur_rf,
                                            model_name="r0b",
                                            logger=logging.getLogger("test"))
    assert isinstance(stems, list)
    assert stems == ["stemA"]

    con.close()
    con_rf.close()


def test_update_provenance_table_inserts_rows(tmp_path):
    dbfile = str(tmp_path / "prov.db")
    con, cur = _create_db(dbfile)

    # create a scores_df as predict() would return
    scores_df = pd.DataFrame({
        "diaObjectId": ["100", "101"],
        "diaSourceId": ["200", "201"],
        "score": [0.42, 0.99]
    })

    # call update_provenance_table
    predict_module.update_provenance_table(scores_df=scores_df,
                                           sqlite_cursor=con.cursor(),
                                           stem="20260127_000000",
                                           model_name="r0b",
                                           model_version="v1",
                                           connection=con,
                                           logger=logging.getLogger("test"))

    # Check provenance table contents (diaObjectId and diaSourceId should be integers)
    cur2 = con.cursor()
    cur2.execute("SELECT diaObjectId, diaSourceId, stem, score, model_name, model_version FROM provenance ORDER BY diaObjectId;")
    rows = cur2.fetchall()
    assert rows == [
        (100, 200, "20260127_000000", 0.42, "r0b", "v1"),
        (101, 201, "20260127_000000", 0.99, "r0b", "v1"),
    ]

    con.close()


def test_main_no_stems_returns_0(monkeypatch, tmp_path):
    """When no stems to process, main should return 0 early."""
    dbfile = str(tmp_path / "nomore.db")
    con, cur = _create_db(dbfile)
    con.close()

    # Provide set_up that points to our DB and csv_dir (not used)
    monkeypatch.setattr(predict_module, "set_up", lambda settings_path, log_name, logger: {
        "log_db": dbfile,
        "csv_dir": Path("/nonexistent")
    })
    # model config with a path (not used because no stems)
    monkeypatch.setattr(predict_module, "read_model_config", lambda path, logger: ({"MODEL_NAME": "r0b", "MODEL_VERSION": "v1", "MODEL_PATH": "unused"}, 0))

    ret = predict_module.main()
    assert ret == 0


def test_main_returns_model_config_status_when_config_fails(monkeypatch, tmp_path):
    """A missing or invalid model config should return its explicit status code."""
    dbfile = str(tmp_path / "bad_config.db")
    con, cur = _create_db(dbfile)
    con.close()

    monkeypatch.setattr(predict_module, "set_up", lambda settings_path, log_name, logger: {
        "log_db": dbfile,
        "csv_dir": Path("/nonexistent")
    })
    monkeypatch.setattr(predict_module, "read_model_config", lambda path, logger: (None, 21))

    ret = predict_module.main()
    assert ret == 21


def test_main_returns_21_when_model_file_is_missing(monkeypatch, tmp_path):
    """A missing model file should fail clearly before processing stems."""
    dbfile = str(tmp_path / "missing_model.db")
    con, cur = _create_db(dbfile)
    cur.execute("INSERT INTO predict (stem, r0b) VALUES (?, ?);", ("20260202_102448", 0))
    cur.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, ?);", ("20260202_102448", 1))
    con.commit()
    con.close()

    missing_model_path = tmp_path / "does_not_exist.joblib"
    monkeypatch.setattr(predict_module, "set_up", lambda settings_path, log_name, logger: {
        "log_db": dbfile,
        "csv_dir": Path(tmp_path) / "csvs"
    })
    monkeypatch.setattr(predict_module, "read_model_config", lambda path, logger: ({
        "MODEL_NAME": "r0b",
        "MODEL_VERSION": "v1",
        "MODEL_PATH": str(missing_model_path),
    }, 0))

    ret = predict_module.main()
    assert ret == 21


def test_main_missing_csv_continues_and_no_provenance_inserted(monkeypatch, tmp_path):
    """If a feature CSV for a stem is missing, prediction is skipped and no provenance rows inserted."""
    dbfile = str(tmp_path / "missingcsv.db")
    con, cur = _create_db(dbfile)

    # Prepare predict + feature_making rows so stemlist returns a stem
    cur.execute("INSERT INTO predict (stem, r0b) VALUES (?, ?);", ("20260202_102448", 0))
    cur.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, ?);", ("20260202_102448", 1))
    con.commit()
    con.close()

    # set_up to point to db and a csv_dir where file does NOT exist
    monkeypatch.setattr(predict_module, "set_up", lambda settings_path, log_name, logger: {
        "log_db": dbfile,
        "csv_dir": Path(tmp_path) / "csvs"
    })
    monkeypatch.setattr(predict_module, "read_model_config", lambda path, logger: ({"MODEL_NAME": "r0b", "MODEL_VERSION": "v1", "MODEL_PATH": str(tmp_path / "model.joblib")}, 0))

    # joblib.load shouldn't be called (no csv), but safe to mock
    monkeypatch.setattr(joblib, "load", lambda p: object())

    # run main
    ret = predict_module.main()
    assert ret == 0

    # ensure provenance table still empty
    con2 = sqlite3.connect(dbfile)
    cur2 = con2.cursor()
    cur2.execute("SELECT COUNT(*) FROM provenance;")
    count = cur2.fetchone()[0]
    assert count == 0
    cur2.execute("SELECT r0b FROM predict WHERE stem = ?;", ("20260202_102448",))
    assert cur2.fetchone()[0] == 21
    con2.close()


def test_main_records_predict_failure_without_writing_provenance(monkeypatch, tmp_path):
    """If predict() returns an error status, record it and skip provenance inserts."""
    dbfile = str(tmp_path / "predict_failure.db")
    con, cur = _create_db(dbfile)

    stem = "20260202_102448"
    cur.execute("INSERT INTO predict (stem, r0b) VALUES (?, ?);", (stem, 0))
    cur.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, ?);", (stem, 1))
    con.commit()
    con.close()

    csv_parent = tmp_path / "csvroot" / stem[:8]
    csv_parent.mkdir(parents=True)
    pd.DataFrame({
        "diaObjectId": [1000],
        "diaSourceId": [2000],
        "featureA": [1.0],
    }).to_csv(csv_parent / f"{stem}.csv", index=False)

    monkeypatch.setattr(predict_module, "set_up", lambda settings_path, log_name, logger: {
        "log_db": dbfile,
        "csv_dir": csv_parent.parent / "placeholder"
    })
    monkeypatch.setattr(predict_module, "read_model_config", lambda path, logger: ({
        "MODEL_NAME": "r0b",
        "MODEL_VERSION": "v1",
        "MODEL_PATH": str(tmp_path / "model.joblib")
    }, 0))
    monkeypatch.setattr(joblib, "load", lambda p: object())
    monkeypatch.setattr(predict_module, "predict", lambda df, model, logger: (None, 31))

    ret = predict_module.main()
    assert ret == 0

    con2 = sqlite3.connect(dbfile)
    cur2 = con2.cursor()
    cur2.execute("SELECT COUNT(*) FROM provenance;")
    assert cur2.fetchone()[0] == 0
    cur2.execute("SELECT r0b FROM predict WHERE stem = ?;", (stem,))
    assert cur2.fetchone()[0] == 31
    con2.close()


def test_main_full_flow_calls_predict_and_writes_provenance(monkeypatch, tmp_path):
    """Full flow: create CSV for the stem, mock predict to return scores, ensure provenance rows written."""
    dbfile = str(tmp_path / "full.db")
    con, cur = _create_db(dbfile)

    stem = "20260202_102448"
    # Set predict and feature_making to select this stem
    cur.execute("INSERT INTO predict (stem, r0b) VALUES (?, ?);", (stem, 0))
    cur.execute("INSERT INTO feature_making (stem, r0b) VALUES (?, ?);", (stem, 1))
    con.commit()
    con.close()

    # Create csv_dir structure matching code: csv_dir.parent / stem[:8] / stem.csv
    # We want the final path (csv_dir.parent / stem[:8] / stem).with_suffix('.csv')
    # to equal tmp_path/"csvroot"/stem[:8]/f"{stem}.csv"
    csv_parent = tmp_path / "csvroot" / (stem[:8])   # <-- this is where we will write the file
    csv_parent.mkdir(parents=True)
    csv_file = csv_parent / f"{stem}.csv"
    # write CSV that the code will read (any minimal dataframe with required columns)
    df = pd.DataFrame({
        "diaObjectId": [1000, 1001],
        "diaSourceId": [2000, 2001],
        "featureA": [1.0, 2.0]
    })
    df.to_csv(csv_file, index=False)

    # To satisfy (csv_dir.parent / stem[:8] / stem).with_suffix('.csv') == csv_file,
    # set csv_dir such that csv_dir.parent == tmp_path/"csvroot"
    csv_dir_for_set_up = csv_parent.parent / "placeholder"  # parent(csv_dir) == csv_parent.parent == tmp_path/"csvroot"

    # Mock set_up/read_model_config
    monkeypatch.setattr(predict_module, "set_up", lambda settings_path, log_name, logger: {
        "log_db": dbfile,
        "csv_dir": csv_dir_for_set_up
    })
    monkeypatch.setattr(predict_module, "read_model_config", lambda path, logger: ({
        "MODEL_NAME": "r0b",
        "MODEL_VERSION": "v1",
        "MODEL_PATH": str(tmp_path / "model.joblib")
    }, 0))

    # mock joblib.load to return a dummy model object (not used by our mock predict)
    monkeypatch.setattr(joblib, "load", lambda p: object())

    # mock the predict function to return a scores DataFrame and status_code 0
    def fake_predict(df, model, logger):
        return pd.DataFrame({
            "diaObjectId": [1000, 1001],
            "diaSourceId": [2000, 2001],
            "score": [0.12, 0.99]
        }), 0

    monkeypatch.setattr(predict_module, "predict", fake_predict)

    ret = predict_module.main()
    assert ret == 0

    # Confirm provenance rows inserted
    con2 = sqlite3.connect(dbfile)
    cur2 = con2.cursor()
    cur2.execute("SELECT diaObjectId, diaSourceId, stem, score FROM provenance ORDER BY diaObjectId;")
    rows = cur2.fetchall()
    assert rows == [
        (1000, 2000, stem, 0.12),
        (1001, 2001, stem, 0.99),
    ]
    con2.close()
