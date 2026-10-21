"""Make predictions for LVRA models. Runs individually as a script, or can be used as a module. 
Oversight: High
Accountable: Heloise

Written by Claude, based on r0b_feature_maker.py and our specs. Reviewed and commented by Heloise

Review Notes
------------

I just realised I have the "features" database name. It contains scores. 
I'll fix it later

"""
import logging
import os
import sqlite3
import sys
from pathlib import Path

import joblib

from lvra.utils.feature_store import connect, insert_scores, read_features
from lvra.utils.misc import read_lvra_config, set_up
from lvra.utils.predict import predict_multiclass


env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:
    SETTINGS_PATH = Path(env_settings)
else:
    SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"

# doesn't exist yet, miight name if something else or bring together with public settings
# when r0b is removed (durng or post Big Refactor)
lvra_config_path = os.environ.get("LVRA_V2_CONFIG") 
if lvra_config_path:
    LVRA_CONFIG_FILE = Path(lvra_config_path)
else:
    LVRA_CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "lvra_config.yaml"

LOG_NAME = "lvra_predict.log"

# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
# FUNCTIONS CALLED BY MAIN (split for better testing) #
# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #

def stemlist_from_log(sqlite_cursor, logger):
    """Find the stem list for which we will need to grab our features later
    
    Note
    -----
    for now we still don't "redo" on a partial success, we just move on. 
    # TODO: Think of a better way to handle partial successes in Big Refactor
    """
    sql = "SELECT predict.stem FROM predict JOIN feature_making ON predict.stem = feature_making.stem " \
          "WHERE ABS(predict.lvra) != 1 AND ABS(feature_making.lvra) = 1;"
    stem_ls = [row[0] for row in sqlite_cursor.execute(sql).fetchall()]
    logger.info(f"[SQLITE] Fetched {len(stem_ls)} stems")
    return stem_ls


def load_slots(config):
    """Creates the slots, defined as: Model + Version + Role

    Of course the model, version (and roles) are difined in the config
    (Role is e.g. Champion, Challenger)
    """
    return {role: (joblib.load(slot['PATH']), str(slot['VERSION']))
            for role, slot in config['MODELS'].items() if slot is not None}


def score_stem(features_con, stem, slots, logger):
    """Calculate the scores for the alerts in a given Stem
    
    Parameters
    -----------
    features_con: sqlite3.Connection
       The connection to the features database (not the log databse)
    stem: str
       The stem
    roles: list[str]
       The list of valid roles, as defined by our config (e.g. Champion, Challenger, Retired)
    logger: logging.Logger 
       Our logger 
    """

    # 1. Get the features from the database using .utils.feature_store.read_features
    # NOTE: Not sure if there is any reason to allow read_features to handle a list of stems
    # if we only ever pass one at a time. To look at again
    features_df = read_features(features_con, [stem])


    if features_df.empty:
        # This only happens if for example the json alerts didn't have the 'alert' field 
        # or if the diaSourceIds from a given stem were ALL repeats from a previous set of alerts
        # because features is keyed on diaSourceId and I do INSERT OR IGNORE. 
        # WE HAVE HAD REPEATS IN THE PAST, and I've never understood why. 
        # It might never happen again but we safeguard from it. A status code of 1 means we'll
        # never predict on that stem again. 
        logger.warning(f"[PREDICT] No features in features.db for stem={stem}. Nothing to score.")
        return 1

    
    for role, (model, version) in slots.items():
        # predict multiclass from utils.predict.
        scores_df, status_code = predict_multiclass(features_df, model, logger)

        if status_code != 0:
            logger.error(f"[PREDICT] FAIL - stem={stem} role={role} version={version} status={status_code}")
            return status_code

        # We add the scores to our model scores table, which allows for all the scores from the multiclass
        # probabilities to be stored (the old provenance table is insuficient)
        n_inserted = insert_scores(features_con, scores_df, stem, role, version)
        # TODO don't we want to fill in the provenance table regardless? Maybe not, maybe it's obsolete now. 
        logger.info(f"[PREDICT] {n_inserted}/{len(scores_df)} scores inserted | stem={stem} role={role} version={version}")

    return 1

# #-#-# #
# MAIN  #
# #-#-# #

def main():
    # -------------------------------------------------- #
    #                      SET UP                        #
    # -------------------------------------------------- #
    logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
    setup_dict = set_up(settings_path=SETTINGS_PATH, log_name=LOG_NAME, logger=logger)

    # CONFIG 
    config, status_code = read_lvra_config(LVRA_CONFIG_FILE, logger)
    if status_code != 0:
        logger.error(f"[LVRA CONFIG] FAIL - status={status_code}. Exiting.")
        return status_code

    # LOG DB CONNECTION 
    con = sqlite3.connect(setup_dict['log_db'])
    cur = con.cursor()


    # -------------------------------------------------- #
    #           WHAT IS THERE TO SCORE?                  #
    # -------------------------------------------------- #

    # GET OUR LIST OF STEMS 
    stem_list = stemlist_from_log(cur, logger)
    if len(stem_list) == 0:
        logger.info("[SQLITE] No stems to score. Exiting.")
        con.close()
        return 0

    # Make our model "slots" and check we can find the bloody models
    # (a model slot = Model + Version + Role)
    try:
        slots = load_slots(config)
    except FileNotFoundError as e:
        logger.error(f"[MODEL] FAIL - model file not found | {e}")
        con.close()
        return 21
    except Exception as e:
        logger.error(f"[MODEL] FAIL - could not load model | {e}")
        con.close()
        return 99

    # OPEN FEATURE DB CONNECTION (now that we know we need it)
    features_con = connect(setup_dict['log_db'].parent / "features.db")

    # -------------------------------------------------- #
    #                      SCORING                       #
    # -------------------------------------------------- #
    for stem in stem_list:
        # Score all the alerts in our stem - Updates the model_scores table in the features databse
        status_code = score_stem(features_con, stem, slots, logger)
        # update the log database. 
        cur.execute("UPDATE predict SET timestamp=current_timestamp, lvra = ? WHERE stem = ?;", (status_code, stem))
        con.commit()
        logger.info(f"[SQLITE] stem={stem} | status={status_code}")

    features_con.close()
    con.close()
    logger.info("[PREDICT] ----- END ------- ")
    return 0


if __name__ == '__main__':
    sys.exit(main())
