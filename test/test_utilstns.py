import json
import logging
import sqlite3

import pandas as pd
import pytest

import lvra.utils.tns as tns_mod


TEST_DIAOBJECTID = 170000000000000001
TEST_STEM = "20260202_102448"


def _create_provenance_db(db_path, rows=None):
    con = sqlite3.connect(db_path)
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
    for row in rows or []:
        cur.execute(
            "INSERT INTO provenance (diaObjectId, stem, timestamp) VALUES (?, ?, ?);",
            row,
        )
    con.commit()
    return con, cur


def _csv_dir_for_stem(tmp_path, stem=TEST_STEM, rows=None):
    base = tmp_path / "csv_base"
    path = base / stem[:4] / stem[:8] / f"{stem}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        rows
        or [
            {
                "diaObjectId": TEST_DIAOBJECTID,
                "lastDiaSourceMjdTai": 60000.0,
                "psfFlux": 1000.0,
                "psfFluxErr": 100.0,
                "band": "r",
                "ra": 123.4,
                "decl": -45.6,
            }
        ]
    )
    df.to_csv(path, index=False)
    return base / "unused" / "placeholder"


def test_mjd_and_flux_converters_are_stable():
    assert tns_mod.mjdToDateFraction(0) == "1858-11-17.00000"
    assert tns_mod.mjdToDateFraction(60000.5, decimalPlaces=3) == "2023-02-25.500"
    assert tns_mod.nanoJanskyToABMag(1.0) == pytest.approx(31.4)
    assert tns_mod.nanoJanskyToABMag(-1.0) == pytest.approx(31.4)
    assert tns_mod.nanoJanskyErrToABMagErr(100.0, 10.0) == pytest.approx(0.108574)


def test_make_tns_report_dictionary_success_uses_latest_matching_row(tmp_path):
    csv_dir = _csv_dir_for_stem(
        tmp_path,
        rows=[
            {
                "diaObjectId": TEST_DIAOBJECTID,
                "lastDiaSourceMjdTai": 59999.0,
                "psfFlux": 10.0,
                "psfFluxErr": 1.0,
                "band": "g",
                "ra": 1.0,
                "decl": 2.0,
            },
            {
                "diaObjectId": TEST_DIAOBJECTID,
                "lastDiaSourceMjdTai": 60000.0,
                "psfFlux": 1000.0,
                "psfFluxErr": 100.0,
                "band": "r",
                "ra": 123.4,
                "decl": -45.6,
            },
        ],
    )
    con, cur = _create_provenance_db(
        tmp_path / "log.db",
        [(TEST_DIAOBJECTID, TEST_STEM, "2026-01-01 00:00:00")],
    )

    report = tns_mod.make_tns_report_dictionary(
        diaObjectId=TEST_DIAOBJECTID,
        csv_dir=csv_dir,
        sqlitecursor=cur,
        logger=logging.getLogger("test_tns"),
    )

    assert report["internal_name"] == f"LSST-AP-DO-{TEST_DIAOBJECTID}"
    assert report["ra"]["value"] == "123.4"
    assert report["dec"]["value"] == "-45.6"
    assert report["photometry"]["0"]["filter_value"] == str(tns_mod.FILTER_IDS["r"])
    assert report["photometry"]["0"]["flux"] == str(tns_mod.nanoJanskyToABMag(1000.0))
    con.close()


def test_make_tns_report_dictionary_returns_expected_error_codes(tmp_path):
    logger = logging.getLogger("test_tns")
    con, cur = _create_provenance_db(tmp_path / "empty.db")
    assert tns_mod.make_tns_report_dictionary(TEST_DIAOBJECTID, tmp_path, cur, logger) == 97
    con.close()

    con, cur = _create_provenance_db(
        tmp_path / "missing_csv.db",
        [(TEST_DIAOBJECTID, TEST_STEM, "2026-01-01 00:00:00")],
    )
    assert tns_mod.make_tns_report_dictionary(TEST_DIAOBJECTID, tmp_path / "a" / "b", cur, logger) == 21
    con.close()

    csv_dir = _csv_dir_for_stem(
        tmp_path,
        rows=[{"diaObjectId": TEST_DIAOBJECTID, "lastDiaSourceMjdTai": 60000.0}],
    )
    con, cur = _create_provenance_db(
        tmp_path / "missing_cols.db",
        [(TEST_DIAOBJECTID, TEST_STEM, "2026-01-01 00:00:00")],
    )
    assert tns_mod.make_tns_report_dictionary(TEST_DIAOBJECTID, csv_dir, cur, logger) == 96
    con.close()


def test_make_tns_report_dictionary_handles_missing_row_and_unknown_band(tmp_path):
    logger = logging.getLogger("test_tns")
    csv_dir = _csv_dir_for_stem(
        tmp_path,
        rows=[
            {
                "diaObjectId": 999,
                "lastDiaSourceMjdTai": 60000.0,
                "psfFlux": 1000.0,
                "psfFluxErr": 100.0,
                "band": "r",
                "ra": 123.4,
                "decl": -45.6,
            }
        ],
    )
    con, cur = _create_provenance_db(
        tmp_path / "missing_row.db",
        [(TEST_DIAOBJECTID, TEST_STEM, "2026-01-01 00:00:00")],
    )
    assert tns_mod.make_tns_report_dictionary(TEST_DIAOBJECTID, csv_dir, cur, logger) == 98
    con.close()

    csv_dir = _csv_dir_for_stem(
        tmp_path,
        rows=[
            {
                "diaObjectId": TEST_DIAOBJECTID,
                "lastDiaSourceMjdTai": 60000.0,
                "psfFlux": 1000.0,
                "psfFluxErr": 100.0,
                "band": "unknown",
                "ra": 123.4,
                "decl": -45.6,
            }
        ],
    )
    con, cur = _create_provenance_db(
        tmp_path / "unknown_band.db",
        [(TEST_DIAOBJECTID, TEST_STEM, "2026-01-01 00:00:00")],
    )
    assert tns_mod.make_tns_report_dictionary(TEST_DIAOBJECTID, csv_dir, cur, logger) == 99
    con.close()


def test_report2tns_missing_api_key_returns_99(monkeypatch, tmp_path):
    monkeypatch.setattr(tns_mod, "TNS_API_KEY", None)

    result = tns_mod.report2TNS(
        [TEST_DIAOBJECTID],
        setup_dict={"log_db": tmp_path / "log.db", "csv_dir": tmp_path / "csv"},
        tns_api_key=None,
        dry_run=True,
    )

    assert result == 99


def test_report2tns_dry_run_builds_payload_and_records_failures(monkeypatch, tmp_path):
    setup = {"log_db": tmp_path / "log.db", "csv_dir": tmp_path / "csv"}

    def fake_make(dia_object_id, csv_dir, sqlitecursor, logger):
        if dia_object_id == 1:
            return {"internal_name": "LSST-AP-DO-1"}
        return 97

    monkeypatch.setattr(tns_mod, "make_tns_report_dictionary", fake_make)
    monkeypatch.setattr(
        tns_mod.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("should not post")),
    )

    summary = tns_mod.report2TNS([1, 2], setup_dict=setup, tns_api_key="key", dry_run=True)

    assert summary["n_requested"] == 2
    assert summary["n_payload"] == 1
    assert summary["failures"] == {2: 97}
    assert summary["payload"] == {"at_report": {"0": {"internal_name": "LSST-AP-DO-1"}}}


def test_report2tns_posts_payload_and_returns_response(monkeypatch, tmp_path):
    setup = {"log_db": tmp_path / "log.db", "csv_dir": tmp_path / "csv"}
    monkeypatch.setattr(tns_mod, "TNS_API_KEY", "global-key")
    monkeypatch.setattr(
        tns_mod,
        "make_tns_report_dictionary",
        lambda dia_object_id, csv_dir, sqlitecursor, logger: {"internal_name": f"LSST-AP-DO-{dia_object_id}"},
    )
    called = {}

    class FakeResponse:
        status_code = 201
        text = "created"

    def fake_post(url, data=None, timeout=None, headers=None):
        called["url"] = url
        called["data"] = data
        called["timeout"] = timeout
        called["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(tns_mod.requests, "post", fake_post)

    summary = tns_mod.report2TNS([10, 11], setup_dict=setup, tns_api_key="explicit-key")

    assert called["url"] == tns_mod.TNS_BASE_URL_SANDBOX + tns_mod.AT_REPORT_FORM
    assert called["timeout"] == 300
    assert json.loads(called["data"]["data"]) == {
        "at_report": {
            "0": {"internal_name": "LSST-AP-DO-10"},
            "1": {"internal_name": "LSST-AP-DO-11"},
        }
    }
    assert summary["n_posted"] == 1
    assert summary["response_status"] == 201
    assert summary["response_text"] == "created"


def test_report2tns_records_make_and_post_exceptions(monkeypatch, tmp_path):
    setup = {"log_db": tmp_path / "log.db", "csv_dir": tmp_path / "csv"}
    monkeypatch.setattr(tns_mod, "TNS_API_KEY", "global-key")

    def fake_make(dia_object_id, csv_dir, sqlitecursor, logger):
        if dia_object_id == 10:
            raise RuntimeError("make failed")
        return {"internal_name": f"LSST-AP-DO-{dia_object_id}"}

    monkeypatch.setattr(tns_mod, "make_tns_report_dictionary", fake_make)
    monkeypatch.setattr(
        tns_mod.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("post failed")),
    )

    summary = tns_mod.report2TNS([10, 11], setup_dict=setup, tns_api_key="key")

    assert "make failed" in summary["failures"][10]
    assert summary["n_payload"] == 1
    assert summary["n_posted"] == 0
    assert "post failed" in summary["post_exception"]


def test_get_tns_reply_missing_api_key_returns_99(monkeypatch):
    monkeypatch.setattr(tns_mod, "TNS_API_KEY", None)

    assert tns_mod.get_tns_reply("123", tns_api_key=None) == 99


def test_get_tns_reply_posts_and_returns_json(monkeypatch):
    called = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"data": {"feedback": "ok"}}

    def fake_post(url, data=None, timeout=None, headers=None):
        called["url"] = url
        called["data"] = data
        called["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(tns_mod.requests, "post", fake_post)

    reply = tns_mod.get_tns_reply("report-1", tns_api_key="key", sandbox=False)

    assert called["url"] == tns_mod.TNS_BASE_URL + tns_mod.AT_REPORT_REPLY
    assert called["data"] == {"api_key": "key", "report_id": "report-1"}
    assert reply == {"data": {"feedback": "ok"}}


def test_get_tns_reply_returns_none_for_non_200_or_post_exception(monkeypatch):
    class FakeResponse:
        status_code = 500

        def json(self):
            raise AssertionError("json should not be called")

    monkeypatch.setattr(tns_mod.requests, "post", lambda *args, **kwargs: FakeResponse())
    assert tns_mod.get_tns_reply("report-1", tns_api_key="key") is None

    monkeypatch.setattr(
        tns_mod.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network failed")),
    )
    assert tns_mod.get_tns_reply("report-1", tns_api_key="key") is None
