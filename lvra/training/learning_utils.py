from typing import Dict, Optional, Tuple
import yaml
from pathlib import Path
import mlflow
from mlflow.tracking import MlflowClient
import logging
import pandas as pd
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

REQUIRED_CONFIG_KEYS = [
    "EXPERIMENT",
    "TRACKING_URI",     # e.g. file:///path/to/mlruns or http://mlflow-server:5000
    # other keys you might require can be added here, e.g. 'PARQUET_GLOB_PATH'
]


def load_config(config_path: str) -> Dict:
    """
    Load a YAML config file and perform a small set of validations.

    Returns:
        dict: parsed YAML configuration
    Raises:
        FileNotFoundError
        ValueError: if required keys missing or YAML invalid
    """
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with p.open("r") as fh:
        cfg = yaml.safe_load(fh)

    if not isinstance(cfg, dict):
        raise ValueError(f"Config file did not contain a mapping (got {type(cfg)}).")

    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in cfg]
    if missing:
        raise ValueError(f"Missing required config keys: {missing}")

    # Normalise some fields if needed
    # e.g. ensure TRACKING_URI is a string
    cfg['TRACKING_URI'] = str(cfg['TRACKING_URI'])

    return cfg


def load_pool_parquet(parquet_path: str) -> pd.DataFrame:
    """
    Minimal loader for X_pool.parquet. Does NOT set index.
    Ensures diaSourceId/diaObjectId columns remain available.
    """
    p = Path(parquet_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Parquet file not found: {p}")
    df = pd.read_parquet(p)
    if not isinstance(df, pd.DataFrame):
        raise ValueError("Parquet did not produce a DataFrame.")

    if 'diaSourceId' not in df.columns and 'diaObjectId' not in df.columns:
        raise ValueError("Data Pool Parquet must contain 'diaSourceId' or 'diaObjectId' column.")

    return df


def load_labels_csv(labels_path: str) -> pd.DataFrame:
    """
    Minimal loader for labels CSV. Returns DataFrame with at least:
      - 'label' column
      - and one of ['diaSourceId', 'diaObjectId'] (prefer diaSourceId)
    If the CSV was written with index column (index_col=0), we ignore that and rely on explicit columns.
    """
    p = Path(labels_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Labels CSV not found: {p}")

    df = pd.read_csv(p, dtype=str)

    # Keep minimal required columns
    if 'label' not in df.columns:
        raise ValueError("Labels CSV must contain a 'label' column.")

    if 'diaSourceId' not in df.columns and 'diaObjectId' not in df.columns:
        raise ValueError("Labels CSV must contain 'diaSourceId' or 'diaObjectId' column.")

    # Prefer diaSourceId for matching; keep both columns if present
    # Keep file order: duplicates will be resolved by keeping last occurrence later
    return df

def load_metrics(model_name, METRICS_DIR):
    path = METRICS_DIR / f"{model_name}.metrics.csv"
    if path.exists() is False:
        df = pd.DataFrame(columns = ['round',
                                     'accuracy',
                                     'precision', 
                                     'recall',
                                     'f1-score',
                                     'timestamp',
                                     'model_name'
                                    ])
    else:
        df = pd.read_csv(str(path.expanduser()), index_col=0)
    return df, path


def load_trainingIds(path):
    #trainingId_path = Path(os.getenv("LVRA_TRAINING_ROOTDIR"))/ "pool"/ f"{cfg['EXPERIMENT']}_trainingIds.csv"
    trainingId_path = Path(path)

    if trainingId_path.exists() is False:
        df = pd.DataFrame(columns = ['diaSourceId',
                                     'diaObjectId',
                                     'timestamp',
                                     'round'])
        training_round = 0
    else:
        df = pd.read_csv(str(trainingId_path.expanduser()), index_col=0)
        training_round = df.iloc[-1]['round']
    return training_round, df


def update_trainingIds(sampled_ids, training_round, trainingId_df):
    ts = datetime.utcnow().isoformat()
    df = sampled_ids.copy()
    df.loc[:,'timestamp'] = ts
    df.loc[:,'round'] = training_round
    return pd.concat((trainingId_df, df)).reset_index(drop=True)


def resolve_model_name(cfg):
    RS = None
    LR = None
    MaxI = None
    SS = None
    if 'random_state' in cfg['MODEL_PARAMS'].keys():
        RS = cfg['MODEL_PARAMS']['random_state']
    if 'learning_rate' in cfg['MODEL_PARAMS'].keys():
        LR = cfg['MODEL_PARAMS']['learning_rate']
    if 'max_iter' in cfg['MODEL_PARAMS'].keys():
        MaxI = cfg['MODEL_PARAMS']['max_iter']
    try: 
        SS = cfg['SAMPLING_STRATEGY']
    except KeyError:
        SS = "UNK"    
    name = f"{cfg['EXPERIMENT']}_LR{LR}_MaxI{MaxI}_RS{RS}_SS{SS}".replace('.',"p")
    return name
    


 #### MIGHT NOT USE MLFLOW AFTER ALL   


def setup_mlflow(cfg: Dict, experiment_create_if_missing: bool = True
                 ) -> Tuple[MlflowClient, str, Optional[dict]]:
    """
    Configure MLflow and return a client, the experiment_id, and metadata about the
    latest successful run (or None if there is none).

    Parameters:
        cfg: configuration dict. Must contain keys 'TRACKING_URI' and 'EXPERIMENT'.
        experiment_create_if_missing: if True, create the experiment when missing.

    Returns:
        (client, experiment_id, last_successful_run_info_or_None)

    Notes:
        - This is intentionally lightweight: it DOES NOT download artifacts or models.
        - It tags the active process by setting mlflow.set_tracking_uri and mlflow.set_experiment.
    """
    if 'TRACKING_URI' not in cfg or 'EXPERIMENT' not in cfg:
        raise ValueError("cfg must contain 'TRACKING_URI' and 'EXPERIMENT' keys.")

    tracking_uri = cfg['TRACKING_URI']
    experiment_name = cfg['EXPERIMENT']

    # Configure MLflow client
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    client = MlflowClient(tracking_uri)

    # Ensure experiment exists (MlflowClient.get_experiment_by_name returns None if missing)
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        if experiment_create_if_missing:
            experiment_id = client.create_experiment(experiment_name)
            logger.info(f"Created MLflow experiment '{experiment_name}' id={experiment_id}")
        else:
            raise ValueError(f"Experiment '{experiment_name}' does not exist.")
        experiment = client.get_experiment(experiment_name)
    experiment_id = experiment.experiment_id

    # Find most recent FINISHED run (if any)
    runs = client.search_runs(
        experiment_ids=[experiment_id],
        filter_string="attributes.status = 'FINISHED'",
        order_by=["start_time DESC"],
        max_results=1,
    )

    last_run_info = None
    if runs:
        run = runs[0]
        # Provide a compact dict with the fields we care about
        last_run_info = {
            "run_id": run.info.run_id,
            "start_time": run.info.start_time,
            "end_time": run.info.end_time,
            "status": run.info.status,
            "metrics": run.data.metrics,
            "params": run.data.params,
            "tags": run.data.tags,
        }
        logger.info(f"Found previous FINISHED run: {last_run_info['run_id']}")
    else:
        logger.info("No previous FINISHED runs found for this experiment.")

    return client, experiment_id, last_run_info

def make_training_sample(
    X_pool: pd.DataFrame,
    y_labels: pd.DataFrame,
    training_Ids: pd.DataFrame,
    mapping: Optional[Dict[str, int]] = None
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Build X_train and y_train from X_pool and y_labels using diaSourceId matching.
    TODO:WRITE DOC STRING
    """
    # minimal validation
    if not isinstance(X_pool, pd.DataFrame) \
    or not isinstance(y_labels, pd.DataFrame) \
    or not isinstance(training_Ids, pd.DataFrame):
        raise ValueError("X_pool, y_labels and training_Ids must be a pandas DataFrame.")

    # Decide matching key in y_labels
    if 'diaSourceId' in y_labels.columns \
    and 'diaSourceId' in X_pool.columns \
    and 'diaSourceId' in training_Ids.columns:
        key_col = 'diaSourceId'
    else:
        raise ValueError("y_labels X_pool and training_Ids are matched on 'diaSourceId'")

    # Keep only needed columns from y_labels: key_col and 'label' (preserve order)
    ysub = y_labels[[key_col, 'label', 'diaObjectId']].copy()

    # Convert keys to str for stable matching
    # no: check they were strings to begin with otherwise throw warning
    if not pd.api.types.is_string_dtype(ysub[key_col]):
        logger.warning(f"Converting y_labels[{key_col}] to string but \
                       index mismatch may occur if trailing zeros were lost in \
                       a scientific notation conversion.")
        ysub[key_col] = ysub[key_col].astype(str)
    X_pool = X_pool.copy()

    if not pd.api.types.is_string_dtype(X_pool[key_col]):
        logger.warning(f"Converting X_pool[{key_col}] to string but \
                       index mismatch may occur if trailing zeros were lost in \
                       a scientific notation conversion.")
        X_pool[key_col] = X_pool[key_col].astype(str)
        
    if not pd.api.types.is_string_dtype(training_Ids[key_col]):
        logger.warning(f"Converting X_pool[{key_col}] to string but \
                       index mismatch may occur if trailing zeros were lost in \
                       a scientific notation conversion.")
        training_Ids[key_col] = training_Ids[key_col].astype(str)
        
    # Build mapping
    if mapping is None:
        mapping = {'real': 1,
                    'extragal': 1,
                    'gal': 1,
                    'agn': 1,
                    'bogus': 0,
                    'varstar': 1,
                    None: np.nan,
                    np.nan: np.nan,
                    }

    # before we do the mapping we extract label rows that correspond to training Ids
    mask_y = ysub[key_col].isin(training_Ids[key_col])
    ysub = ysub[mask_y]
    
    # Map labels to ints
    try:
        ysub['target'] = ysub['label'].map(mapping)
    except Exception as e:
        # propagate a clear error
        raise ValueError(f"Error mapping labels to targets: {e}")

    if ysub['target'].isna().all():
        raise ValueError("After mapping, no labels mapped to a valid target. Check mapping.")

    # Drop rows where mapping produced NaN (irrelevant labels)
    # TODO: should log which diaSourceId and diaObjectId results in NaN
    ysub = ysub[~ysub['target'].isna()].copy()


    # Now select rows from X_pool where pool_key is in ysub[key_col]
    mask_pool = X_pool[key_col].isin(ysub[key_col].values)
    X_train = X_pool.loc[mask_pool].copy()

    if X_train.shape[0] == 0:
        raise ValueError("No matching rows found in X_pool for provided labels.")

    # Set index of X_train to the pool key for convenience
    X_train.index = X_train[key_col].astype(str)

    # Build y_train aligned to X_train index
    # Build mapping from key -> target
    key_to_target = dict(zip(ysub[key_col].astype(str), ysub['target'].astype(int)))
    y_train = pd.Series([key_to_target[k] for k in X_train[key_col].astype(str)],
                        index=X_train.index,
                        name='target',
                        dtype=int)

    # Drop the key column from X_train (optional) — keep it for now since you might want both
    # If you prefer to drop: X_train = X_train.drop(columns=[pool_key])

    return X_train, y_train