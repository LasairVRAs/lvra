"""Make features for the LVRA models. Runs as a stand alone script or can be used as a module. 
Oversight: High
Accountable: Heloise

Written by Claude, based on r0b_feature_maker.py and our specs. Reviewed and commented by Heloise

Review Notes
------------


"""
import logging
import os
import sqlite3
import sys
from pathlib import Path

from lvra.utils.alert_rows import json_to_feature_rows
from lvra.utils.feature_store import connect, insert_features
from lvra.utils.misc import set_up


env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:
    SETTINGS_PATH = Path(env_settings)
else:
    SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"

LOG_NAME = "lvra_feature_maker.log"


# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
# FUNCTIONS CALLED BY MAIN (split for better testing) #
# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #

def stemlist_from_logdb(sqlite_cursor, logger):
    """Get the list of stems that are pending to be processed"""

    # we query for everything that has not completed (1) or partially completed (-1)
    res = sqlite_cursor.execute("SELECT stem FROM feature_making WHERE ABS(lvra) != 1;")

    # fetchall into a list
    stem_ls = [stem[0] for stem in res.fetchall()]

    logger.info(f"[SQLITE] Fetched {len(stem_ls)} stems")
    return stem_ls


def make_features(input_path: Path, features_con, stem: str, logger) -> int:
    """
    Takes the path to a json file, extracts the features and puts them in the features data base.

    Parameters
    ----------
    input_path: Path
        The path to the json file we want to extract features from. Expected to be in the format 
        "../../../data/json/YYYY/YYYYMMDD_HHMMSS.json"
    logger: logging.Logger
        The logger object to log info, warnings and errors to the log file.

    Note
    -----
    there is no outpath (contrary to r0b) because I don't save the features as csvs but in the 
    features database instead. 
    """


    logger.info(f"[MAKE_FEATURES] START | inpath={input_path}")
    try:
        # from utils.alert_rows. Takes json and makes our big features dataframe
        rows_df, no_alert = json_to_feature_rows(input_path) 
        # Then we us utils.feature_store.insert_features to put that into sql
        # TODO: During big refactor, we can probably skip the data frame entierly and go from json to db
        #       Or even better still, if the features are cheap we might be able to calculate them on the fly
        #       upon receiving the kafka stream. (put it means if i fuck up those calculations i don't have the raw JSON
        #       to fall back on). To sort later. 
        n_inserted = insert_features(features_con, rows_df, stem)
    except FileNotFoundError:
        logger.error(f"[MAKE_FEATURES] FAIL - reason = INPUT FileNotFound - inpath={input_path}")
        return 21
    except Exception as e:
        logger.error(f"[MAKE_FEATURES] FAIL - reason={e}")
        return 99

    logger.info(f"[MAKE_FEATURES] {n_inserted}/{len(rows_df)} rows inserted in features.db | stem={stem}")
    if no_alert:
        logger.warning(f"[MAKE_FEATURES] PARTIAL SUCCESS - {len(no_alert)} diaObjectIds had no alert key "
                       f"and are NOT INCLUDED. List of diaObjectIds:\n{no_alert}")
        return -1
    return 1


# #-#-# #
# MAIN  #
# #-#-# #

def main():
    # -------------------------------------------------- #
    #                      SET UP                        #
    # -------------------------------------------------- #
    logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
    # General settings 
    setup_dict = set_up(settings_path=SETTINGS_PATH, log_name=LOG_NAME, logger=logger)

    # LOG DATABSE CONNECTION
    con = sqlite3.connect(setup_dict['log_db'])
    cur = con.cursor()

    # GET OUR STEM LIST
    stem_list = stemlist_from_logdb(cur, logger)
    # IF EMTY, NOWT TO DO.
    if len(stem_list) == 0:
        con.close()
        logger.info("[EXIT] - No new stems to process - Closing sqlite connection and exiting (0).")
        return 0

    # FEATURE STORE DATA BASE CONNECTION
    features_con = connect(setup_dict['log_db'].parent / "features.db")

    # -------------------------------------------------- #
    #     FOR EACH FILE WE HAVE TO PROCESS...            #
    # -------------------------------------------------- #
    for stem in stem_list:
        # 1. Get the JSON file path
        input_path = setup_dict['base_dir'] / "JSON" / stem[:4] / stem[:8] / f"{stem}.json"
        # 2. Make the features (inserts into feature database)
        status_code = make_features(input_path, features_con, stem, logger)

        # 3. update the log database with the correct status code
        cur.execute("UPDATE feature_making SET timestamp=current_timestamp, lvra = ? WHERE stem = ?;",
                    (status_code, stem))
        con.commit()
        logger.info(f"[SQLITE] stem={stem} | status={status_code}")

    features_con.close()
    con.close()
    logger.info("[SQLITE] connections closed.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
