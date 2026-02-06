# tests/test_pypeline_r0bannotator.py
import sqlite3
import logging
import pandas as pd

import lvra.pypeline.r0b_annotator as annotator_module

# Helpers --------------------------------------------------------------------

def _create_db(path: str):
    """Create a sqlite DB with the tables used by the annotator and return connection/cursor."""
    con = sqlite3.connect(path)
    cur = con.cursor()
    # minimal provenance and annotating schemas used by get_pending_annotations and update
    cur.execute(
        """
        CREATE TABLE provenance (
            ID INTEGER PRIMARY KEY,
            diaObjectId TEXT,
            diaSourceId TEXT,
            stem TEXT,
            score TEXT,
            model_name TEXT,
            model_version TEXT
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE annotating (
            stem TEXT PRIMARY KEY,
            r0b INTEGER DEFAULT 0
        );
        """
    )
    con.commit()
    return con, cur

# Tests ----------------------------------------------------------------------

def test_get_pending_annotations(tmp_path):
    dbfile = str(tmp_path / "test_pending.db")
    con, cur = _create_db(dbfile)

    # insert a provenance row that should be returned
    cur.execute(
        "INSERT INTO provenance (ID, diaObjectId, diaSourceId, stem, score, model_name, model_version) VALUES (?, ?, ?, ?, ?, ?, ?);",
        (1, "D1", "S1", "stem1", "0.87", "r0b", "v1"),
    )
    # annotating row with r0b != 1 (0) so it's pending
    cur.execute("INSERT INTO annotating (stem, r0b) VALUES (?, ?);", ("stem1", 0))
    con.commit()

    # reopen connection with proper row_factory so cursor returns dict rows (what function expects)
    con_with_factory = sqlite3.connect(dbfile)
    con_with_factory.row_factory = lambda cursor, row: {col[0]: row[i] for i, col in enumerate(cursor.description)}
    cur_with_factory = con_with_factory.cursor()

    pending_df = annotator_module.get_pending_annotations(sqlite_cursor=cur_with_factory,
                                                         model_name="r0b",
                                                         model_version="v1",
                                                         logger=logging.getLogger("test"),
                                                         )
    # Should return a dataframe with our provenance row
    assert isinstance(pending_df, pd.DataFrame)
    assert pending_df.shape[0] == 1
    # check it contains fields from the provenance row (as strings per function)
    row = pending_df.iloc[0]
    assert row["diaObjectId"] == "D1"
    assert row["stem"] == "stem1"
    assert row["score"] == "0.87"

    con.close()
    con_with_factory.close()


def test_annotate_loop_success_and_failure(monkeypatch, tmp_path):
    """Test annotate_loop handles both successful annotations and exceptions."""
    # Build pending_annotations DataFrame with two rows: one will succeed, one will fail
    pending = pd.DataFrame([
        {"ID": "1", "diaObjectId": "DO1", "diaSourceId": "S1", "stem": "st1", "score": "0.5", "model_name": "r0b", "model_version": "v1"},
        {"ID": "2", "diaObjectId": "DO2", "diaSourceId": "S2", "stem": "st2", "score": "0.9", "model_name": "r0b", "model_version": "v1"},
    ])

    # Create a mock Lasair client with annotate method.
    class MockLasair:
        def __init__(self):
            self.calls = []

        def annotate(self, topic, objectId, classification, version, explanation, classdict, url):
            # simulate failure for objectId DO2
            if objectId == "DO2":
                raise RuntimeError("annotation failed")
            self.calls.append((topic, objectId, classification, version, explanation, classdict, url))
            return True

    L = MockLasair()

    model_conf_dict = {
        "TOPIC_OUT": "top",
        "EXPLANATION": "why",
        "URL": "http://example",
    }
    logger = logging.getLogger("test_annotate")
    success_dois, failure_dois, stem_list = annotator_module.annotate_loop(pending, L, model_conf_dict, logger)

    assert success_dois == ["DO1"]
    assert failure_dois == ["DO2"]
    assert set(stem_list) == {"st1"}  # only the successful one appended its stem


def test_update_annotating_table_commits(tmp_path):
    dbfile = str(tmp_path / "test_update.db")
    con, cur = _create_db(dbfile)

    # insert two annotating rows
    cur.execute("INSERT INTO annotating (stem, r0b) VALUES (?, ?);", ("stA", 0))
    cur.execute("INSERT INTO annotating (stem, r0b) VALUES (?, ?);", ("stB", 0))
    con.commit()

    # call update_annotating_table with status_code 1 for both stems
    logger = logging.getLogger("test_update")
    annotator_module.update_annotating_table(status_code=1,
                                            unique_stems=["stA", "stB"],
                                            model_name="r0b",
                                            sqlite_cursor=con.cursor(),
                                            connection=con,
                                            logger=logger)

    # verify changes were committed
    cur2 = con.cursor()
    cur2.execute("SELECT stem, r0b FROM annotating ORDER BY stem;")
    rows = cur2.fetchall()
    assert rows == [("stA", 1), ("stB", 1)]

    con.close()


def test_main_returns_99_when_no_token(monkeypatch, tmp_path):
    """If LASAIR_TOKEN is not set at module level, main should log an error and return 99."""
    # ensure module-level token is None (module sets LASAIR_TOKEN at import time)
    monkeypatch.setattr(annotator_module, "LASAIR_TOKEN", None)

    # monkeypatch set_up/read_model_config to simple functions so main doesn't crash early
    monkeypatch.setattr(annotator_module, "set_up", lambda settings_path, log_name, logger: {"log_db": ":memory:", "endpoint": "http://x"})
    monkeypatch.setattr(annotator_module, "read_model_config", lambda path, logger: ({"MODEL_NAME": "r0b", "MODEL_VERSION": "v1"}, 0))

    ret = annotator_module.main()
    assert ret == 99


def test_main_no_pending_annotations_returns_0(monkeypatch, tmp_path):
    """
    Test main when the database contains no pending annotations.
    We'll create a temporary sqlite file and point set_up to it.
    """
    dbfile = str(tmp_path / "main_no_pending.db")
    con, cur = _create_db(dbfile)
    # no provenance rows inserted -> get_pending_annotations will be empty

    # Provide LASAIR_TOKEN at module level
    monkeypatch.setattr(annotator_module, "LASAIR_TOKEN", "dummy-token")
    # Monkeypatch set_up to point to our db file and endpoint
    monkeypatch.setattr(annotator_module, "set_up", lambda settings_path, log_name, logger: {"log_db": dbfile, "endpoint": "http://x"})
    # Monkeypatch read_model_config to minimal model conf
    monkeypatch.setattr(annotator_module, "read_model_config", lambda path, logger: ({"MODEL_NAME": "r0b", "MODEL_VERSION": "v1", "TOPIC_OUT": "t", "EXPLANATION": "e", "URL": "u"}, 0))
    # Monkeypatch lasair client to a simple object (shouldn't be reached because no pending)
    monkeypatch.setattr(annotator_module.lasair, "lasair_client", lambda token, endpoint: object())

    ret = annotator_module.main()
    assert ret == 0
    con.close()
