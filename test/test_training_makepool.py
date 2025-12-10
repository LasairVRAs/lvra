# tests/test_training_makepool.py
import hashlib
import importlib
import os
import sys
from pathlib import Path

import pandas as pd
import pytest


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, df: pd.DataFrame):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _reload_training_module(tmp_path: Path):
    """
    Set LVRA_TRAINING_ROOTDIR, ensure tmp_path is importable and import the
    module containing make_pool (expected at lvra/training/make_pool.py).
    Returns the imported module object.
    """
    os.environ["LVRA_TRAINING_ROOTDIR"] = str(tmp_path)

    # make sure the dir containing 'lvra' is on sys.path
    root_str = str(tmp_path)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    # prefer lvra.training.make_pool (your code lives there)
    modname = "lvra.training.make_pool"

    # remove any existing modules under this name to force re-import
    to_delete = [k for k in list(sys.modules.keys())
                 if k == modname or k.startswith(modname + ".")]
    for k in to_delete:
        del sys.modules[k]

    return importlib.import_module(modname)


# --- Pytest fixtures / utilities ------------------------------------------------
@pytest.fixture(autouse=True)
def clear_make_pool_logger():
    """
    Ensure the process-global 'make_pool' logger has no handlers that point at
    old temp directories. This avoids log files being written to stale paths
    when tests reuse the same process.
    """
    import logging
    logger = logging.getLogger("make_pool")
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    yield
    # cleanup after test as well
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass


# --- Tests ---------------------------------------------------------------------
def test_parse_logs_and_no_new_csvs(tmp_path, monkeypatch):
    """
    If a CSV's sha matches an entry in the logs, update_X_pool should detect
    there are no new files and return without creating an X_pool.parquet.
    """
    # arrange: directory structure
    root = tmp_path
    csv_dir = root / "csv"
    logs_dir = root / "logs"
    pool_dir = root / "pool"
    csv_dir.mkdir()
    logs_dir.mkdir()
    pool_dir.mkdir()

    # create a csv file
    csv_path = csv_dir / "a.csv"
    df = pd.DataFrame({"diaObjectId": ["1", "2"], "diaSourceId": ["10", "20"]})
    write_csv(csv_path, df)

    # compute sha and write a log that contains that sha (so module should skip)
    sha = file_sha256(csv_path)
    logfile = logs_dir / "make_pool.log"
    logfile.write_text(
        f"2025-12-08 12:44:28,771 [INFO] something: ADDED_TO_XPOOL file={csv_path} sha256={sha} nrows=2 xpool=/pool/X_pool.parquet\n"
    )

    # import module (fresh)
    training = _reload_training_module(root)

    # monkeypatch the module's sha256_of_file to the real one (deterministic)
    monkeypatch.setattr(training, "sha256_of_file", lambda p: file_sha256(Path(p)))

    # call update_X_pool - should return None (no new files) and not create X_pool.parquet
    ret = training.update_X_pool(csv_dir=csv_dir, logs_dir=logs_dir, pool_dir=pool_dir)
    assert ret is None
    assert not (pool_dir / "X_pool.parquet").exists()

    # check the log file contains the "No new CSV" message appended
    log_text = (logs_dir / "make_pool.log").read_text()
    assert "No new CSV files to add to X_pool." in log_text


def test_update_x_pool_creates_pool_and_logs(tmp_path, monkeypatch):
    """
    When new CSV(s) are present, update_X_pool should create X_pool.parquet,
    deduplicate, and append ADDED_TO_XPOOL lines to the log.
    """
    root = tmp_path
    csv_dir = root / "csv"
    logs_dir = root / "logs"
    pool_dir = root / "pool"
    csv_dir.mkdir()
    logs_dir.mkdir()
    pool_dir.mkdir()

    # two csv files to add
    a = pd.DataFrame({"diaObjectId": ["1", "2"], "diaSourceId": ["10", "20"], "val": [100, 200]})
    b = pd.DataFrame({"diaObjectId": ["3"], "diaSourceId": ["30"], "val": [300]})
    a_path = csv_dir / "a.csv"
    b_path = csv_dir / "b.csv"
    write_csv(a_path, a)
    write_csv(b_path, b)

    training = _reload_training_module(root)

    # patch sha256_of_file to actual contents
    monkeypatch.setattr(training, "sha256_of_file", lambda p: file_sha256(Path(p)))

    # run
    ret = training.update_X_pool(csv_dir=csv_dir, logs_dir=logs_dir, pool_dir=pool_dir)
    assert ret == 0

    # xpool exists and contains 3 unique rows
    xpool = pd.read_parquet(pool_dir / "X_pool.parquet")
    assert set(xpool["diaObjectId"].astype(str)) == {"1", "2", "3"}
    assert len(xpool) == 3

    # log file should contain ADDED_TO_XPOOL lines for both CSVs
    log_path = logs_dir / "make_pool.log"
    log_text = log_path.read_text()
    assert "ADDED_TO_XPOOL" in log_text
    # check each sha appears in log
    assert file_sha256(a_path) in log_text
    assert file_sha256(b_path) in log_text


def test_update_preserves_existing_rows_and_dedup(tmp_path, monkeypatch):
    """
    If an existing X_pool.parquet already contains a row with a given diaObjectId,
    and the incoming CSV contains the same id, keep the existing row (first),
    and still add new unique rows.
    """
    root = tmp_path
    csv_dir = root / "csv"
    logs_dir = root / "logs"
    pool_dir = root / "pool"
    csv_dir.mkdir()
    logs_dir.mkdir()
    pool_dir.mkdir()

    # existing pool has diaObjectId '1' with val_old
    existing = pd.DataFrame({"diaObjectId": ["1"], "diaSourceId": ["X"], "val": ["old"]})
    (pool_dir / "X_pool.parquet").parent.mkdir(parents=True, exist_ok=True)
    existing.to_parquet(pool_dir / "X_pool.parquet", index=False)

    # new csv contains '1' (should be dropped in favour of existing) and '2' (new)
    new = pd.DataFrame({"diaObjectId": ["1", "2"], "diaSourceId": ["10", "20"], "val": ["new", "fresh"]})
    new_path = csv_dir / "new.csv"
    write_csv(new_path, new)

    training = _reload_training_module(root)
    monkeypatch.setattr(training, "sha256_of_file", lambda p: file_sha256(Path(p)))

    ret = training.update_X_pool(csv_dir=csv_dir, logs_dir=logs_dir, pool_dir=pool_dir)
    assert ret == 0

    out = pd.read_parquet(pool_dir / "X_pool.parquet")

    # ensure dedup: have both '1' and '2'
    assert set(out["diaObjectId"].astype(str)) == {"1", "2"}
    # ensure diaObjectId '1' kept the original 'val' value ("old")
    row1 = out[out["diaObjectId"].astype(str) == "1"].iloc[0]
    assert row1["val"] == "old"
