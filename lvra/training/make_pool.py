# utils/training.py
from pathlib import Path
import re
import logging
import tempfile
from datetime import datetime
import pandas as pd
from lvra.utils.misc import sha256_of_file  # your existing function
import os 

LOG_FILENAME = "make_pool.log"
try:
    LOG_DIR =  Path(os.getenv("LVRA_TRAINING_ROOTDIR")).resolve()/"logs"
except TypeError:
    raise RuntimeError("Environment variable LVRA_TRAINING_ROOTDIR not set.")
    
CSV_DIR =  Path(os.getenv("LVRA_TRAINING_ROOTDIR")).resolve()/"csv"
PARQUET_DIR = Path(os.getenv("LVRA_TRAINING_ROOTDIR")).resolve()/"parquet"

# match lines we will write: ADDED_TO_XPOOL file=/full/path sha256=... nrows=... xpool=/parquet/X_pool.parquet
_RE_ADDED = re.compile(r'ADDED_TO_XPOOL\s+file=(\S+)')


def _setup_logger(log_path: Path):
    logger = logging.getLogger("make_pool")
    logger.setLevel(logging.INFO)
    # avoid adding multiple handlers in repeated imports
    if not logger.handlers:
        fh = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        # time format similar to your example: 2025-12-04 15:07:51,430
        formatter = logging.Formatter(fmt, datefmt='%Y-%m-%d %H:%M:%S,%f')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

def _parse_logs_for_added(logs_dir: Path):
    """Return set of absolute paths (strings) that were already added to X_pool."""
    added = set()
    for p in sorted(logs_dir.glob("*.log")):
        with open(p, "r", encoding="utf-8") as fh:
            for line in fh:
                m = _RE_ADDED.search(line)
                if m:
                    added.add(str(Path(m.group(1)).resolve()))
    return added

def update_X_pool(csv_dir: str = CSV_DIR, 
                  logs_dir: str = LOG_DIR, 
                  parquet_dir: str = PARQUET_DIR,
                  index_col="diaObjectId"
                  ):

    log_path = logs_dir / LOG_FILENAME
    logger = _setup_logger(log_path)

    # 1) which files already ADDED_TO_XPOOL?
    already_added_set = _parse_logs_for_added(logs_dir)
    

    # 2) find CSV files in csv_dir
    csv_files = sorted(csv_dir.glob("*.csv"))
    full_csv_set = set([str(p.resolve()) for p in csv_files])
    to_add_set = full_csv_set - already_added_set
    
    if not to_add_set:
        logger.info("No new CSV files to add to X_pool.")
        return 
    
    xpool_path = parquet_dir / "X_pool.parquet"
    try:
        df_pool = pd.read_parquet(xpool_path)
    except FileNotFoundError:
        logger.info(f"X_pool.parquet not found at {xpool_path}, starting new pool.")
        df_pool = pd.DataFrame(columns=[index_col])

    new_dfs = []
    metadata_tolog = [] 
    for csv_path_str in sorted(to_add_set):
        df = pd.read_csv(csv_path_str, dtype={index_col: str})
        df[index_col] = df[index_col].astype("string")
        nrows = len(df)
        sha = sha256_of_file(csv_path_str)
        new_dfs.append(df)
        metadata_tolog.append((csv_path_str, sha, nrows))


    combined = pd.concat([df_pool] + new_dfs, ignore_index=True)
    combined = combined.drop_duplicates(subset=[index_col], keep="first")

    # 7) atomic write to parquet
    # TLDR: A HALF WRITTEN PARQUET FILE IS NOT READABLE AT ALL!
    # this is so if the write fails half way through we don't overwrite
    # our pool of data with a corrupted file.
    # This is especially important with a parquet file since it's a binary file that contains
    # page indexes, row groups, column chunks, metadata footer that must be written last
    # If the process dies before the footer is written, the file is garbage.
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".parquet", dir=str(parquet_dir)) as tf:
        tmp_path = Path(tf.name)
    combined.to_parquet(tmp_path, index=False)
    tmp_path.replace(xpool_path)


    # 8) append human-readable log lines (same style as your team)
    for p, sha, nrows in metadata_tolog:
        # message example:
        # 2025-12-08 12:44:28,771 [INFO] update_xpool.main: ADDED_TO_XPOOL file=/full/path.csv sha256=... nrows=123 xpool=/parquet/X_pool.parquet
        msg = f"ADDED_TO_XPOOL file={str(Path(p).resolve())} sha256={sha} nrows={nrows} xpool={str(xpool_path.resolve())}"
        logger.info(msg)

    return 0

if __name__ == "__main__":
    update_X_pool()