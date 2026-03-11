from pathlib import Path
import tempfile
from typing import Callable, Dict, Optional
import uuid
import webbrowser
import pandas as pd
import os
import time
from datetime import datetime
import logging



try:
    LOG_DIR =  Path(os.getenv("LVRA_TRAINING_ROOTDIR")).resolve()/"logs"
except TypeError:
    raise RuntimeError("Environment variable LVRA_TRAINING_ROOTDIR not set.")
    
CSV_DIR =  Path(os.getenv("LVRA_TRAINING_ROOTDIR")).resolve()/"csv"
POOL_DIR = Path(os.getenv("LVRA_TRAINING_ROOTDIR")).resolve()/"pool"

LABELFILE_COLUMNS = ["diaSourceId", 
                     "diaObjectId", 
                     "label", 
                     "timestamp", 
                     "session_id", 
                     "url"]

LOG_FILENAME = "label.log"
LOG_PATH = LOG_DIR / LOG_FILENAME





def _atomic_save(df: pd.DataFrame,
                 out_path: str) -> None:
    """Atomically save DataFrame to CSV file.
    Allows for easy undo. 
    """
    out = Path(out_path).expanduser() #what does this do?
    out.parent.mkdir(parents=True, exist_ok=True)

    df_copy = df.copy()

    with tempfile.NamedTemporaryFile(mode="w", 
                                     delete=False,
                                     dir=str(out.parent),
                                     suffix=".csv") as tf:
        tmp = Path(tf.name)
        df_copy.to_csv(tmp, index=False)

    tmp.replace(out)

def load_labels(path: str
                ) -> pd.DataFrame:
    """
    Load labels CSV, normalising column names and ensuring candid is string.
    Returns empty DataFrame with canonical columns if file missing.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return pd.DataFrame(columns=LABELFILE_COLUMNS, dtype=str)

    df = pd.read_csv(p, dtype=str)

    return df


def interactive_labeling(
    df_pool: pd.DataFrame,
    output:  str = POOL_DIR / "y_labeled.csv",
    allowed_labels: Optional[Dict[str, str]] = None,
    resume: bool = True,
    url_template: str = "https://lasair.lsst.ac.uk/objects/{oid}", #"https://lasair-lsst.lsst.ac.uk/objects/{oid}",
    input_func: Callable[[str], str] = input,
    opener: Callable[[str], None] = webbrowser.open,
    session_id: Optional[str] = None,
    sleep: float = 0.5,
) -> pd.DataFrame:
    """
    Interactive labeling loop that accepts a DataFrame `df_pool` and saves labels atomically.

    Required columns in df_pool:
      - 'diaSourceId' (unique alert id)
      - 'diaObjectId' (may be empty string)

    Parameters
    ----------
    df_pool : pd.DataFrame
        Must contain 'diaSourceId' and 'diaObjectId' columns.
    output : str
        Path to CSV file to store labels (atomic replace).
    allowed_labels : dict, optional
        Mapping of single-char shortcuts to canonical labels. Default provided.
    resume : bool
        If True, load existing labels and skip already-labeled diaSourceIds.
    url_template : str
        Template to open object pages; must include '{oid}'.
    input_func : callable
        Function(prompt) -> str; injected for tests (default: built-in input).
    opener : callable
        Function(url) -> None; injected for tests (default: webbrowser.open).
    session_id : optional str
        Session id to write into rows. If None, generated with uuid4.
    sleep : float
        Seconds to wait after calling opener(url) so page can load.

    Returns
    -------
    pd.DataFrame
        The final labels DataFrame loaded from disk (canonical column set).
    """
    out_path = Path(output).expanduser()
    session_id = session_id or str(uuid.uuid4())

    # if log doesn't exist, create it
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


    # ---- validation ----
    if not isinstance(df_pool, pd.DataFrame):
        raise TypeError("df_pool must be a pandas DataFrame")

    required = {"diaSourceId", "diaObjectId"}
    if not required.issubset(set(df_pool.columns)):
        raise ValueError(f"df_pool must contain columns: {required}")

    if allowed_labels is None:
        allowed_labels = {
            "r": "real",
            "x": "extragal",
            "g": "gal",
            "a": "agn",
            "b": "bogus",
            "v": "varstar",
            "m": "mover",
        }

    print(allowed_labels)

    # load existing labels if resume requested
    if resume and out_path.exists():
        existing = load_labels(str(out_path))
        print(f"Resuming: found {len(existing)} existing labels in {out_path}")
    else:
        existing = pd.DataFrame(columns=LABELFILE_COLUMNS, dtype=str)

    # canonicalize pool: keep order, ensure strings
    pool = df_pool.copy()
    pool["diaSourceId"] = pool["diaSourceId"].astype(str)
    pool["diaObjectId"] = pool["diaObjectId"].astype(str)

    # build work list preserving the original order
    labeled_src = set(existing["diaSourceId"].astype(str)) if "diaSourceId" in existing.columns else set()
    work_df = pool[~pool["diaSourceId"].isin(labeled_src)].reset_index(drop=True)
    total = len(work_df)
    if total == 0:
        print("Nothing to label. Exiting.")
        return existing

    logger = logging.getLogger(__name__)
    logger.info(
        f"START session_id={session_id} output={out_path} "
        f"resume={resume} pool_size={len(df_pool)} to_label={total}"
    )
    
    i = 0
    try:
        while i < total:
            row = work_df.iloc[i]
            sid = str(row["diaSourceId"])
            oid = str(row["diaObjectId"]) if ("diaObjectId" in row and row["diaObjectId"] is not None) else ""
            # choose URL
            url = url_template.format(oid=oid) 

            print(f"\n{i+1}/{total} - mjd={row.get('lastDiaSourceMjdTai', '(unknown)')} - diaSourceId={sid} diaObjectId={oid or '(unknown)'}")
            try:
                opener(url)
            except Exception as e:
                print(f"Warning: opener failed: {e}")
            if sleep and sleep > 0:
                time.sleep(sleep)

            prompt = f"Label [ {', '.join(sorted(allowed_labels.keys()))} ] (s=skip, q=quit): "
            inp = input_func(prompt).strip().lower()

            if inp == "q":
                print("Quitting. Progress saved (if any new labels).")
                break

            if inp == "s" or inp == "":
                print("Skipped.")
                i += 1
                continue

            if inp not in allowed_labels:
                print(f"Invalid input '{inp}'. Valid keys: {', '.join(sorted(allowed_labels.keys()))}, s, q")
                continue

            lab = allowed_labels[inp]
            ts = datetime.utcnow().isoformat()
            out_row = {
                "diaSourceId": sid,
                "diaObjectId": oid,
                "label": lab,
                "mjd": row.get("lastDiaSourceMjdTai", ""),
                "timestamp": ts,
                "session_id": session_id,
                "url": url,
            }

            # append to in-memory 'existing' and atomically save
            existing = pd.concat([existing, pd.DataFrame([out_row])], ignore_index=True, sort=False)
            _atomic_save(existing, out_path)
            logger.info(f"LABEL session_id={session_id} sid={sid} oid={oid} label={lab}")
            i += 1

    except KeyboardInterrupt:
        logger.warning(f"INTERRUPT session_id={session_id} saved_progress={len(existing)}")
        _atomic_save(existing, out_path)

    final = load_labels(str(out_path))
    logger.info(f"END session_id={session_id} total_labels={len(final)}")
    return session_id
