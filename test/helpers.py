import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_SCHEMA_PATH = REPO_ROOT / "data" / "log_schema.sql"
FEATURES_SCHEMA_PATH = REPO_ROOT / "data" / "features_schema.sql"


def initialise_log_db(db_path: Path, schema_path: Path = LOG_SCHEMA_PATH) -> Path:
    """Create a log DB from the canonical LVRA SQLite schema."""
    with sqlite3.connect(db_path) as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
    return db_path


# Claude wrote this for LVRA v2 (2026-10-21)
def initialise_features_db(db_path: Path) -> Path:
    return initialise_log_db(db_path, FEATURES_SCHEMA_PATH)


# Claude wrote this for LVRA v2 (2026-10-21)
def fit_tiny_hgb(rows, feature_names, categoricals=("band", "best_distance_flag")):
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier

    train = rows.sample(50, replace=True, random_state=0).reset_index(drop=True)
    X = train[feature_names].astype({n: "category" if n in categoricals else float for n in feature_names})
    X["psfflux"] += np.random.default_rng(0).normal(0, 1000, len(X))
    y = ["agn", "bogus", "extragal", "mover", "real"] * 10
    return HistGradientBoostingClassifier(max_iter=5, min_samples_leaf=1, random_state=0).fit(X, y)
