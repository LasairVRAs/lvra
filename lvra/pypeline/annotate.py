#!/usr/bin/env python3
import os
import sys
import logging
from pathlib import Path
import yaml
import joblib
import pandas as pd
import lasair
import lvra.utils as lutils

# --- logging setup (stdout + file handler will be set after config read) ---
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
logger.setLevel(logging.INFO)
_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_stream_handler)

# TODO: Add comments and docstrings in here!
# TODO: tests 

def predict(indexed_features: pd.DataFrame, 
            model, 
            columns_to_exclude = ['diaObjectId', 
                                  'diaSourceId', 
                                  'sherlock_classifications', 
                                  'UTC',
                                  'tns_name'
                                  ]
           ):
    # make a dataframe to store our predictions with our indexes
    preds_df = indexed_features[['diaObjectId', 'diaSourceId']].copy()
    
    # exclude columns that don't belong in features
    X = indexed_features.drop(columns=columns_to_exclude, errors='ignore')
    logger.info(f"Dropped columns not needed for prediction: {columns_to_exclude}")
    
    prob = model.predict_proba(X)
    # sklearn returns Nx2 for binary; take column 1
    preds_df['pred'] = prob[:, 1]
    return preds_df.sort_values('pred', ascending=False)


def annotate_object(objectId, score_i, L, topic_out, classdict, version='0.1'):
    classification = str(score_i)
    explanation = 'Lasair VRA RB score'
    # try/except per-object to avoid catastrophes
    try:
        L.annotate(
            topic_out,
            objectId,
            classification,
            version=version,
            explanation=explanation,
            classdict=classdict,
            url=''
        )
        return True, None
    except Exception as e:
        return False, str(e)


def main(annotator: str, model_name: str, features_path: str, debug: bool=False):
    # Check the python libraries we need to run are correct
    try:
        lutils.check_pckg_versions(debug=debug)
        logger.info("[INFO] Key python library version checks passed")
    except (FileNotFoundError, RuntimeError) as e:
        logger.error(f"[ERROR] Environment check failed: {e}")
        return 2

    # load settings
    env_settings = os.environ.get("LVRA_SETTINGS")
    if env_settings:
        settings_path = Path(env_settings)
    else:
        settings_path = Path(__file__).resolve().parent.parent / "data" / "public_settings.yaml"

    with settings_path.open("r") as fh:
        config = yaml.safe_load(fh)

    endpoint = config['endpoint']
    base_dir = Path(config['base_dir'])
    csv_data_dir = base_dir / "csv"
    log_dir = base_dir / "logs"
    models_dir = base_dir / "models"

    csv_data_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / "lvra_annotators.log"

    # add file handler
    fh = logging.FileHandler(log_path, mode='a')
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    logger.info(f"Starting annotator={annotator} model={model_name} features={features_path}")

    model_path = (models_dir / model_name).with_suffix('.joblib')
    if not model_path.exists():
        logger.error(f"Model file not found: {model_path}")
        logger.info(f"FAIL annotate model={model_name} inpath={features_path} reason=missing_model")
        return 2

    try:
        model = joblib.load(model_path)
    except Exception:
        logger.exception("Failed to load model")
        logger.info(f"FAIL annotate model={model_name} inpath={features_path} reason=joblib_load_error")
        return 2

    csv_path = (csv_data_dir / features_path).resolve()
    if not csv_path.exists():
        logger.error(f"Features file not found: {csv_path}")
        logger.info(f"FAIL annotate model={model_name} inpath={features_path} reason=missing_features")
        return 2

    # quick read with safe options
    try:
        indexed_features = pd.read_csv(csv_path)
    except Exception:
        logger.exception("Failed to read features CSV")
        logger.info(f"FAIL annotate model={model_name} inpath={features_path} reason=csv_read_error")

    nrows = len(indexed_features)
    logger.info(f"Loaded {nrows} rows from {csv_path}")
    if nrows == 0:
        logger.info("Zero rows to annotate; nothing to do.")
        logger.info(f"SUCCESS annotate model={model_name} inpath={features_path} rows=0")
        return 0
    

    # create lasair client
    token = os.getenv("LASAIR_LSST_TOKEN")
    try:
        L = lasair.lasair_client(token, endpoint=endpoint)
    except Exception:
        logger.exception("Failed to construct Lasair client")
        logger.info(f"FAIL annotate model={model_name} inpath={features_path} reason=lasair_client_error")
        return 2

    # predictions
    try:
        scores = predict(indexed_features, model)
    except Exception:
        logger.exception("Prediction failed")
        logger.info(f"FAIL annotate model={model_name} inpath={features_path} reason=prediction_error")
        return 2

    # dedupe on object id (keep top score)
    scores = scores.drop_duplicates(subset=['diaObjectId'])
    logger.info(f"{len(scores)} unique diaObjectId(s) to annotate")

    if debug:
        logger.info("DEBUG: would annotate these objects (top 10):")
        logger.info(scores.head(10).to_string(index=False))
        return 0

    topic_out = annotator
    classdict = {'vra_model': model_name, 'version': '0.1'}
    success_count = 0
    fail_count = 0
    for idx, row in scores.iterrows():
        objectId = row['diaObjectId']
        score_i = row['pred']
        ok, err = annotate_object(objectId, score_i, L, topic_out, classdict)
        if ok:
            success_count += 1
            logger.info(f"ANNOTATED object={objectId} score={score_i:.6f}")
        else:
            fail_count += 1
            logger.error(f"ANNOTATION FAILED object={objectId} err={err}")

    logger.info(f"Finished annotating: success={success_count} fail={fail_count} rows={nrows}")
    # one-liner success marker usable by bash log-greps
    logger.info(f"SUCCESS annotate model={model_name} inpath={features_path} rows={nrows} success={success_count} fail={fail_count}")

    return 0


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("ANNOTATOR")
    parser.add_argument("MODEL_NAME")
    parser.add_argument("FEATURES_PATH")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    code = main(args.ANNOTATOR, args.MODEL_NAME, args.FEATURES_PATH, debug=args.debug)
    sys.exit(code)
