import lasair
import os
import logging
from pathlib import Path
import yaml
from datetime import datetime
import sys
import joblib
import pandas as pd

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s",)



def predict(X, model):
    predictions = X[['diaObjectId', 'diaSourceId']].copy()
    pred = model.predict_proba(X)
    predictions.loc[:, 'pred'] = pred.T[1]
    return predictions.sort_values('pred', ascending=False)


def annotate(objectId, score_i, L, topic_out, classdict, version='0.1'):
    #classdict      = {'vra_model': model_name_nsr, 'version': 'alpha'}
    classification = str(score_i)
    explanation    = 'Lasair VRA RB score'
    
    L.annotate(
        topic_out, 
        objectId, 
        classification,
        version=version, 
        explanation=explanation, 
        classdict=classdict, 
        url='')
    return



def main(annotator: str, model_name: str, features_path: str, debug: bool=False):

    # SET UP THE ENVIRONMENT
    # Get the "public settings" from the environment or grab the default. 
    env_settings = os.environ.get("LVRA_SETTINGS")
    if env_settings:                                 # from environment variable
        settings_path = Path(env_settings)
    else:                                            # or go to default file
        settings_path = Path(__file__).resolve().parent.parent / "data" / "public_settings.yaml"


    with settings_path.open("r") as settings:
        config = yaml.safe_load(settings) 
        endpoint = config['endpoint']                # endpoint for lasair-lsst
        base_dir = Path(config['base_dir'])          # base directory for data storage
        csv_data_dir = base_dir / "csv"              # CSV output directory
        log_dir = base_dir / "logs"                  # log directory 
        models_dir = base_dir / "models"              # models directory


    csv_data_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / f"lvra_annotators.log"

    # LOAD THE MODEL
    model_path = (models_dir / model_name).with_suffix('.joblib')
    logging.info(f"Using model path: {model_path}")

    model = joblib.load(model_path)

    # LOAD THE DATA TO ANNOTATE
    csv_path = csv_data_dir / features_path
    logging.info(f"Loading features from: {csv_path}")
    X = pd.read_cscv(features_path)
    logging.info(f"Loaded {len(X)} rows to annotate.")


    # CREATE THE LASAIR CLIENT
    token = os.getenv("LASAIR_LSST_TOKEN")
    L = lasair.lasair_client(token, endpoint=endpoint)
    logging.info(f"Lasair Client created with endpoint: {endpoint}")

    # MAKE PREDICTIONS
    scores = predict(X, model)
    scores = scores.drop_duplicates(subset=['diaObjectId'])

    if debug:
        logging.info("DEBUG MODE: Note calling the annotator for now")
        return exit(0)
    
    # ANNOTATE THE DATA
    topic_out = ANNOTATOR
    classdict = {'vra_model': model_name, 'version': '0.1'}
    for idx, row in scores.iterrows():
        objectId = row['diaObjectId']
        score_i = row['pred']
        annotate(objectId, score_i, L, topic_out, classdict)


    return exit(0)

if __name__=='__main__':
    if len(sys.argv) != 4:
        print("Usage: python annotator.py <ANN> <MODEL_PATH> <FEATURES_PATH>")
        sys.exit(1)
        
    ANNOTATOR = sys.argv[1] 
    MODEL_NAME = sys.argv[2]
    FEATURES_PATH = sys.argv[3]

    logging.info(f"ANNOTATOR: {ANNOTATOR} | MODEL_NAME: {MODEL_NAME}")
    main(ANNOTATOR, MODEL_NAME, FEATURES_PATH)