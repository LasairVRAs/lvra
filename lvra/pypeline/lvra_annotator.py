"""Annotator for the LVRA. Funtions as a stand alone script and a module.

Oversight: High
Accountable: Heloise

Written by Claude, Reviewed and commented by Heloise

Review Notes
------------

I dont' like the "slot" nomenclature... To rethink in the Big Refactor.

On the wizard syntax in get_pending():
------ WIZARD -----
    for row in scores_df.to_dict("records"):
        slots[row["diaSourceId"]][row["model_role"]] = {"version": row["model_version"],
                                                        **{c: row[c] for c in SCORE_CLASSES}}

----- break down ----------

1.  scores_df.to_dict("records") turns the dataframe into a list with one dict per row:
[{"diaSourceId: 170653063984448679, "diaObjectId", ..., "extragal":... , ...},
{"diaSourceId: 170604720462758706, "diaObjectId", ..., "extragal":... , ...},
...]

so each row of our for loop is one of these dictionaries

2. BEFORE the loop we'd created the slots dictionary, ready to "welcome" our scores:
slots = {170653063984448679: {"champion": None, "challenger": None, "retired": None},
         170604720462758706: {"champion": None, "challenger": None, "retired": None},
         ...}

3. slots[row["diaSourceId"]][row["model_role"]] isolates e.g. 170653063984448679, Champion
and we can fill that with our sub dictionary that contains our version and our class scores, e.g.:

{"version": "0.1", "extragal": 0.91, "mover": 0.01, "real": 0.05, "bogus": 0.02, "agn": 0.01, "gal": None}


After the loop we have our filled "slots" dictionary:
slots = {170653063984448679:   {"champion": {"version": "0.1", "extragal": 0.91, ...},
                                "challenger": {"version": "0.2", "extragal": 0.88, ...},
                                "retired": None},
        170604720462758706:    {"champion": {"version": .......
        }}

"""
import logging
import os
import sqlite3
import sys
from pathlib import Path

import lasair
import pandas as pd

from lvra.utils.classdict import build_classdict, format_classification
from lvra.utils.feature_store import MODEL_ROLES, SCORE_CLASSES, connect, read_features
from lvra.utils.misc import read_lvra_config, set_up


env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:
    SETTINGS_PATH = Path(env_settings)
else:
    SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"

lvra_config_path = os.environ.get("LVRA_V2_CONFIG")
if lvra_config_path:
    LVRA_CONFIG_FILE = Path(lvra_config_path)
else:
    LVRA_CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "lvra_config.yaml"

LOG_NAME = "lvra_annotator.log"
LASAIR_TOKEN = os.getenv("LASAIR_TOKEN") 
# set by the bash script, will be LASAIR_LSST_TOKEN by default or whatever i've given through the CLI. 

# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
# FUNCTIONS CALLED BY MAIN (split for better testing) #
# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #


def stemlist_from_log(sqlite_cursor, logger):
    """Get the list of stems with pending annotations (have a prediction but not annotated yet)"""

    sql = "SELECT annotating.stem FROM annotating JOIN predict ON annotating.stem = predict.stem " \
          "WHERE ABS(annotating.lvra) != 1 AND ABS(predict.lvra) = 1;"
    stem_ls = [row[0] for row in sqlite_cursor.execute(sql).fetchall()]
    logger.info(f"[SQLITE] Fetched {len(stem_ls)} stems")
    return stem_ls


def get_pending(features_con, stems):
    """Get all the data and scores we need to build the pending annotations
    
    Return
    ------
    pd.DataFrame, dict

    Latest features dataframe and the dictionary of all the scores 
    """

    # Get the features for the relevant stems
    features_df = read_features(features_con, stems)
    # Only keep the latest feature values, we do this by ordering by stem and delta_days 
    # (the newer alerts have the longer deltas) and dropping the duplicates
    latest_df = features_df.sort_values(["stem", "delta_days_TOTAL"]).drop_duplicates("diaObjectId", keep="last")

    # We grab our scores
    sql = f"SELECT * FROM model_scores WHERE stem IN ({', '.join('?' * len(stems))})"
    scores_df = pd.read_sql_query(sql, features_con, params=stems)
    # and keep onlt the scores of our LATEST alerts
    scores_df = scores_df[scores_df.diaSourceId.isin(latest_df.diaSourceId)]

    # Here are our "slots" = Model + Version + Role
    slots = {sid: {role: None for role in MODEL_ROLES} for sid in latest_df.diaSourceId}

    # WIZARD SYNTAX - THIS IS A LOT.. SEE NOTES AT TOP OF FILE
    # Essentially fills each diaSourceId with the three sets of scores it will get from
    # t's Champion, Challenger and Retired model predictions. (none if the role isn't filled)
    for row in scores_df.to_dict("records"):
        slots[row["diaSourceId"]][row["model_role"]] = {"version": row["model_version"],
                                                        **{c: row[c] for c in SCORE_CLASSES}}
    
    return latest_df, slots


def annotate_loop(latest_df, slots, L, config, logger):
    """Annotation loop: One annotation per diaObjectId. Sends annotations to Lasair

    PArameters
    -----------
    latest_df: pd.DataFrame
       The feature rows of the latest data points for each diaObjectId. 
    slots: dict
       The scores by slot == (role + model + version)
    L: lasair.lasair_client
       Lasair client object to send the annotations
    config: dict
       The config dictionary. Must contain TOPIC_OUT, EXPLANATION, URL
    logger: logging.Logger
       Logger object  

    Returns
    -------
    int, int

    (number successes and number of failures, failures are recorde in the log file)
    """
    n_success, n_failure = 0, 0
    for row in latest_df.to_dict("records"):
        champion = slots[row["diaSourceId"]]["champion"]
        try:
            L.annotate(topic=config['TOPIC_OUT'],
                       objectId=int(row["diaObjectId"]),
                       classification=format_classification(champion["extragal"]),
                       version=champion["version"],
                       explanation=config['EXPLANATION'],
                       classdict=build_classdict(row, slots[row["diaSourceId"]]), # a whole untils.classdict at work here
                       url=config['URL'])
            n_success += 1
        except Exception as e:
            logger.error(f"[ANNOTATING] diaObjectId {row['diaObjectId']} | {e}")
            n_failure += 1
    return n_success, n_failure

# #-#-# #
# MAIN  #
# #-#-# #

def main():
    # -------------------------------------------------- #
    #                      SET UP                        #
    # -------------------------------------------------- #
    logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
    setup_dict = set_up(settings_path=SETTINGS_PATH, log_name=LOG_NAME, logger=logger)

    if LASAIR_TOKEN is None:
        logger.error("[TOKEN] - FAILURE - LASAIR_TOKEN env variable is None. Exiting")
        return 99

    config, status_code = read_lvra_config(LVRA_CONFIG_FILE, logger)
    if status_code != 0:
        logger.error(f"[LVRA CONFIG] FAIL - status={status_code}. Exiting.")
        return status_code

    # LOG DB CONNECTION
    con = sqlite3.connect(setup_dict['log_db'])
    cur = con.cursor()

    # -------------------------------------------------- #
    #           WHAT IS THERE TO ANNOTATE?               #
    # -------------------------------------------------- #
    stem_list = stemlist_from_log(cur, logger)
    if len(stem_list) == 0:
        logger.info("[SQLITE] No pending annotations to make. Exiting.")
        con.close()
        return 0


    # -------------------------------------------------- #
    #             GET THE DATA AND SCORES                #
    # -------------------------------------------------- #

    # FEATURES DB CONNECTION only if we have a job to do
    features_con = connect(setup_dict['log_db'].parent / "features.db")

    # Get the features and the scores (slots)
    latest_df, slots = get_pending(features_con, stem_list)
    features_con.close()


    # -------------------------------------------------- #
    #                  LASAIR CLIENT                     #
    # -------------------------------------------------- #
    try:
        L = lasair.lasair_client(LASAIR_TOKEN, endpoint=setup_dict['endpoint'])
    except Exception:
        logger.exception("Failed to construct Lasair client")
        con.close()
        return 41

    # ANNOTATE!!!
    n_success, n_failure = annotate_loop(latest_df, slots, L, config, logger)

    if n_failure == 0:
        status_code = 1
    elif n_success == 0:
        status_code = 42
    else:
        status_code = -1
    logger.info(f"[ANNOTATING] {n_success} annotated, {n_failure} failed | status={status_code}")

    # UPDATE THE LOG DB 
    for stem in stem_list:
        cur.execute("UPDATE annotating SET timestamp=current_timestamp, lvra = ? WHERE stem = ?;", (status_code, stem))
    con.commit()
    con.close()
    logger.info("[ANNOTATING] ----- END ------- ")
    return 0


if __name__ == '__main__':
    sys.exit(main())
