# tests/test_tns.py
import os
import shutil
import sqlite3
import importlib
from pathlib import Path
import json
import logging
import lvra.utils.tns as tns_mod
importlib.reload(tns_mod)

TEST_DIAOBJECTID = 169760231713145019  # expected to exist in repo test CSV
TEST_STEM = "20260202_102448"

# Ensure the env var exists before importing the module (module raises on missing key)
os.environ.setdefault("LVRA_TNS_API_KEY", "fake-key-for-tests")

# import (or reload) the module so that TNS_API_KEY is picked up from env



def _create_provenance_db(dbpath: Path, diaObjectId: int, stem: str):
    """Create an sqlite DB at dbpath with a provenance row for diaObjectId->stem."""
    con = sqlite3.connect(str(dbpath))
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE provenance (
            ID INTEGER PRIMARY KEY,
            diaObjectId INTEGER,
            diaSourceId INTEGER,
            stem TEXT,
            score REAL,
            model_name TEXT,
            model_version TEXT,
            timestamp TEXT NOT NULL DEFAULT current_timestamp
        );
        """
    )
    # Insert a single provenance row mapping diaObjectId -> stem
    cur.execute(
        "INSERT INTO provenance (diaObjectId, stem) VALUES (?, ?);",
        (diaObjectId, stem),
    )
    con.commit()
    return con, cur


def _install_csv_for_stem(tmp_csv_root: Path, source_csv_path: Path, stem: str):
    """
    (Kept for compatibility) Create the directory structure expected by make_tns_report_dictionary:
      csv_dir / {stem[:4]} / {stem[:8]} / {stem}.csv
    and copy source_csv_path into that location.
    Returns the csv_dir that should be passed into the function.
    """
    year_dir = tmp_csv_root / stem[:4]
    day_dir = year_dir / stem[:8]
    day_dir.mkdir(parents=True, exist_ok=True)
    dest = day_dir / f"{stem}.csv"
    shutil.copy(source_csv_path, dest)
    return tmp_csv_root


def test_make_tns_report_dictionary_success(tmp_path):
    """
    Copy the repository test CSV into a temporary csv_dir with the expected layout,
    create a provenance DB pointing to that stem, and call the function.
    Expect a dict with the at_report keys and the correct internal_name value.
    """
    # locate repo test CSV (adjust path relative to this test file)
    repo_root = Path(__file__).resolve().parent.parent
    repo_csv = repo_root / "data" / "test" / f"{TEST_STEM}.csv"
    assert repo_csv.exists(), f"Expected test CSV at {repo_csv} (add it if missing)"

    # tmp locations
    tmp_db = tmp_path / "log.db"

    # Create the CSV at: base / YEAR / YEARMONTHDAY / stem.csv
    base = tmp_path / "base"
    dest = base / TEST_STEM[:4] / TEST_STEM[:8] / f"{TEST_STEM}.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(repo_csv, dest)

    # Choose csv_dir so csv_dir.parent.parent == base
    csv_dir = base / "unused" / "placeholder"   # parent.parent -> base

    # create provenance DB with a row mapping our diaObjectId -> stem
    con, cur = _create_provenance_db(tmp_db, TEST_DIAOBJECTID, TEST_STEM)

    # call the function
    logger = logging.getLogger("test_tns")
    tns_dict = tns_mod.make_tns_report_dictionary(
        diaObjectId=TEST_DIAOBJECTID, csv_dir=csv_dir, sqlitecursor=cur, logger=logger
    )

    # Basic assertions on structure and content
    assert isinstance(tns_dict, dict)
    assert "at_report" in tns_dict
    at = tns_dict["at_report"]
    assert "internal_name" in at and at["internal_name"]["value"] == f"LSST-AP-DO-{TEST_DIAOBJECTID}"
    # photometry must be present with expected keys
    assert "photometry" in at
    phot = at["photometry"]
    assert "flux" in phot and "obsdate" in phot and "filterid" in phot

    # ra/dec values should be present
    assert "ra" in at and "dec" in at
    # ra/dec values should be numeric types (int/float)
    assert isinstance(at["ra"]["value"], (int, float))
    assert isinstance(at["dec"]["value"], (int, float))

    con.close()


def test_make_tns_report_dictionary_unknown_band(tmp_path):
    """
    Create a tiny CSV with an unknown band and ensure the function returns 99 and logs an error.
    """
    # base directory where year/day/stem will live
    base = tmp_path / "base"
    csv_dir = base / "any" / "thing"  # csv_dir.parent.parent == base

    # create the directory and csv file at base / YEAR / YEARMONTHDAY / stem.csv
    dest = base / TEST_STEM[:4] / TEST_STEM[:8] / f"{TEST_STEM}.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)

    # minimal CSV columns required by function (note 'decl' for declination)
    import pandas as pd
    df = pd.DataFrame({
        "diaObjectId": [TEST_DIAOBJECTID],
        "lastDiaSourceMjdTai": [59500.0],
        "psfFlux": [123.4],
        "band": ["X"],  # unknown band -> should trigger error
        "ra": [10.0],
        "decl": [-5.0]
    })
    df.to_csv(dest, index=False)

    # create provenance DB pointing to our stem
    tmp_db = tmp_path / "log.db"
    con, cur = _create_provenance_db(tmp_db, TEST_DIAOBJECTID, TEST_STEM)

    logger = logging.getLogger("test_tns")
    rc = tns_mod.make_tns_report_dictionary(
        diaObjectId=TEST_DIAOBJECTID, csv_dir=csv_dir, sqlitecursor=cur, logger=logger
    )

    assert rc == 99

    con.close()



# ---------------------------
# New tests for report2TNS
# ---------------------------

def test_report2TNS_missing_api_key_returns_99(monkeypatch, tmp_path):
    """
    If no API key is provided via tns_api_key and module global TNS_API_KEY is None,
    the function should log and return 99 immediately.
    """
    monkeypatch.setattr(tns_mod, "TNS_API_KEY", None)
    # provide minimal setup so function won't fail earlier (but api key check occurs before DB creation)
    setup = {"log_db": str(tmp_path / "log.db"), "csv_dir": tmp_path / "csvroot"}
    # call with explicit None tns_api_key and expect 99
    rc = tns_mod.report2TNS([1], setup_dict=setup, tns_api_key=None, dry_run=True)
    assert rc == 99


def test_report2TNS_dry_run_builds_payload_and_closes_db(monkeypatch, tmp_path):
    """
    dry_run=True should build payload and not call requests.post.
    We mock set_up and make_tns_report_dictionary to control behaviour.
    The function should create (and close) its own DB connection (close_conn True).
    """
    # prepare fake setup to be returned by set_up
    dbfile = tmp_path / "log.db"
    csvroot = tmp_path / "csvroot"
    fake_setup = {"log_db": str(dbfile), "csv_dir": csvroot}
    monkeypatch.setattr(tns_mod, "set_up", lambda *a, **k: fake_setup)

    # fake make_tns_report_dictionary: one success, one numeric error
    def fake_make(did, csv_dir, sqlitecursor, logger):
        if did == 10:
            return {"at_report": {"internal_name": {"value": "LSST-AP-DO-10"}}}
        return 99

    monkeypatch.setattr(tns_mod, "make_tns_report_dictionary", fake_make)

    # ensure requests.post would raise if called (should not be)
    monkeypatch.setattr(tns_mod.requests, "post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("should not be called")))

    # Pass a tns_api_key so API key check passes
    summary = tns_mod.report2TNS([10, 11], setup_dict=None, tns_api_key="fake-k", dry_run=True, sandbox=True)

    assert summary["n_requested"] == 2
    assert summary["n_payload"] == 1  # only one success
    assert summary["failures"] == {11: 99}
    # since exactly one report, payload should be the single-report dict (matching code behavior)
    assert isinstance(summary["payload"], dict)
    assert summary["payload"]["at_report"]["internal_name"]["value"] == "LSST-AP-DO-10"

    # The function created a DB file at fake_setup['log_db']; ensure it exists (was opened/closed)
    assert dbfile.exists()


def test_report2TNS_posts_and_returns_response(monkeypatch, tmp_path):
    """
    Non-dry-run should call requests.post and include response_status in summary.
    """
    dbfile = tmp_path / "log2.db"
    csvroot = tmp_path / "csvroot"
    fake_setup = {"log_db": str(dbfile), "csv_dir": csvroot}
    monkeypatch.setattr(tns_mod, "set_up", lambda *a, **k: fake_setup)

    # make_tns_report_dictionary returns two reports
    monkeypatch.setattr(tns_mod, "make_tns_report_dictionary",
                        lambda did, csv_dir, sqlitecursor, logger: {"at_report": {"internal_name": {"value": f"LSST-AP-DO-{did}"}}})

    # create a fake response and capture call
    called = {}
    class FakeResp:
        def __init__(self, code=201, text="created"):
            self.status_code = code
            self.text = text

    def fake_post(url, data=None, timeout=None, headers=None):
        called['url'] = url
        called['data'] = data
        called['headers'] = headers
        return FakeResp(201, "created")

    monkeypatch.setattr(tns_mod.requests, "post", fake_post)

    # Ensure module global TNS_API_KEY is set so header is populated
    monkeypatch.setattr(tns_mod, "TNS_API_KEY", "global-fake-key")

    summary = tns_mod.report2TNS([20, 21], setup_dict=None, tns_api_key="explicit-key", dry_run=False, sandbox=True)

    # verify a POST was made to sandbox URL
    assert called['url'].startswith(tns_mod.TNS_BASE_URL_SANDBOX)
    # data['data'] should be a JSON string; parse it
    parsed = json.loads(called['data']['data'])
    assert isinstance(parsed, dict) and "reports" in parsed and len(parsed['reports']) == 2

    assert summary["n_posted"] == 1
    assert summary["response_status"] == 201
    assert summary["n_payload"] == 2


def test_report2TNS_handles_make_exception(monkeypatch, tmp_path):
    """
    If make_tns_report_dictionary raises, it should be captured as a failure entry and not crash.
    """
    fake_setup = {"log_db": str(tmp_path / "log.db"), "csv_dir": tmp_path / "csvroot"}
    monkeypatch.setattr(tns_mod, "set_up", lambda *a, **k: fake_setup)

    # raise for one id, return report for another
    def bad_make(did, csv_dir, sqlitecursor, logger):
        if did == 101:
            raise RuntimeError("boom")
        return {"at_report": {"internal_name": {"value": f"LSST-AP-DO-{did}"}}}

    monkeypatch.setattr(tns_mod, "make_tns_report_dictionary", bad_make)
    # stub out requests.post so we do not perform network I/O (and to satisfy post step)
    monkeypatch.setattr(tns_mod.requests, "post", lambda *a, **k: type("R", (), {"status_code": 200, "text": "ok"})())

    summary = tns_mod.report2TNS([101, 102], setup_dict=None, tns_api_key="k", dry_run=False, sandbox=True)

    # failure recorded with repr string
    assert 101 in summary["failures"]
    assert isinstance(summary["failures"][101], str)
    # the other id should be included in payload/reports
    assert summary["n_payload"] == 1

