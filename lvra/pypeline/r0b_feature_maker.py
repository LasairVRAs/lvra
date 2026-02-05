"""
Name: r0b_feature_maker.py
Author: H.F.Stevance (hfstevance@gmail.com | GitHub: HeloiseS)
Description: When run as a script, calls the main function which
* 1) Reads the config file located in environment variable LVRA_SETTINGS or, if not defined
looks for the "public_seetings.yaml" file located in ../../../data/
* 2) Connects to the log.db SQLite database (strict file structure expected, see docs) and 
returns a list of stems for json files whose features have not been successfully extracted for r0b
* 3) opens the corresponding json files, extracts the features and then outputs the csv files

"""

import logging
from pathlib import Path
import os
from lvra.utils.features import FeaturesRealBogus, json2cleandf
from lvra.utils.misc import set_up
import sys
import sqlite3

# #-#-#-#-#-# #
#  CONSTANTS  #
# #-#-#-#-#-# #

COLUMNS_TO_REMOVE = ['visit', 
                     'tns_name',
                     'ssObjectId',
                     'parentDiaSourceId',
                     'midpointMjdTai',
                     'timeProcessedMjdTai',
                     'timeWithdrawnMjdTai',
                     'firstDiaSourceMjdTai',
                     'ra_sourceId',
                     'raErr_sourceId',
                     'decErr_sourceId',
                     'ra_dec_Cov_sourceId',
                     'UTC',
                    ]


env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    SETTINGS_PATH = Path(env_settings)
else:                                            # or go to default file
    SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"

LOG_NAME = "r0b_feature_maker.log"

# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
# FUNCTIONS CALLED BY MAIN (split for better testing) #
# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
 
def stemlist_from_logdb(sqlite_cursor, 
                     logger,
                     ):
    """Takes existing cursor connected to log.db and gets stems from feature_making table where r0b column != 1
    
    Parameters
    ----------

    Return
    ------
    stem_list: list
        The list of stems whose r0b column was not 1 (not successful). If no matches, get empty list.
    """
    sql = "SELECT stem FROM feature_making WHERE ABS(r0b) != 1;"
    res = sqlite_cursor.execute(sql)
    logger.info("[SQLITE] Fetching Stem list")
    # The result from fetchall will look like e.g. [('20260127_115934',), ('20260127_134852',)]
    # so we need to do list comprehension to have a list of just strings and not tuples of strings
    _stem_ls = res.fetchall() 
    stem_ls = [stem[0] for stem in _stem_ls]
    
    logger.info("[SQLITE] SUCCESS Fetching Stem list | Connection NOT CLOSED")

    return stem_ls


def make_features(input_path: Path,
                  output_path: Path,
                  logger):

    # input: logging, input path, output path, endpoint
    # output: exit code
    logger.info(f"[MAKE_FEATURES] START | inpath={input_path} outpath={output_path}") 

    # TODO: add tests that actually go through these exceptions 
    try:
        clean_df, objectIds_withoutAlert_col = json2cleandf(input_path)
    except FileNotFoundError:
        logger.error(f"[MAKE_FEATURES] FAIL - reason = INPUT FileNotFound - inpath={input_path}")
        return 21
    except KeyError as e:
        logger.error(f"[MAKE_FEATURES] FAIL - reason = KeyError {e}")
        return 30
    except Exception as e:
        logger.error(f"[MAKE_FEATURES] FAIL - reason={e}")
        return 1

    try:
        # MAKE NEW FEATURES AND REMOVE COLUMNS WE DON'T WANT
        clean_df['deltaDiaSourceMjdTai'] = clean_df.lastDiaSourceMjdTai - clean_df.firstDiaSourceMjdTai
        columns_to_include = list(set(clean_df.columns) - set(COLUMNS_TO_REMOVE))
        features_df = clean_df[columns_to_include]

        # OUTPUT TO CSV
        # If this is the first process of the day, the daily directory won't exist and we need to create it
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Output to csv
        features_df.to_csv(output_path, index=False)

        if len(objectIds_withoutAlert_col) > 0:
            logger.warning(f"[MAKE_FEATURES] WARNING - {len(objectIds_withoutAlert_col)} diaObjectIds had no alert key in their JSON entry"
                           f"and are NOT INCLUDED IN THE OUTPUT. List of diaObjectIds:\n{objectIds_withoutAlert_col}")
            logger.info(f"[MAKE_FATURES] PARTIAL SUCCESS - {output_path} created ")
            
        logger.info(f"[MAKE_FEATURES] SUCCESS - {output_path} created ")
        return -1

    except FileNotFoundError:
        logger.error("[MAKE_FEATURES] FAIL - reason= OUTPUT FileNotFound")
        return 22
    except Exception as e:
        logger.error(f"[MAKE_FEATURES] FAIL -  reason={e}")
        return 1
    

def make_features_deprecated(input_path: Path,
                  output_path: Path,
                  endpoint: str,
                  logger):

    # input: logging, input path, output path, endpoint
    # output: exit code
    logger.info(f"[MAKE_FEATURES] START | inpath={input_path} outpath={output_path}") 
    try:
        # TODO: logic could change to not use objects? 
        _df = FeaturesRealBogus.from_json(input_path)
        features_df = FeaturesRealBogus.add_diasource_features(df=_df, endpoint=endpoint)

        # If this is the first process of the day, the daily directory won't exist and we need to create it
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Output to csv
        features_df.to_csv(output_path, index=False)

        logger.info(f"[MAKE_FEATURES] SUCCESS - {output_path} created ")
        return 0

    except FileNotFoundError:
        logger.error("[MAKE_FEATURES] FAIL - reason=FileNotFound")
        return 1
    except Exception as e:
        logger.error(f"[MAKE_FEATURES] FAIL -  reason={e}")
        return 1


# #-#-# #
# MAIN  #
# #-#-# #

def main():
    
    logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
    # General settings and initialisation of the logger
    setup_dict = set_up(settings_path=SETTINGS_PATH, 
                        log_name=LOG_NAME,
                        logger=logger
                        )
         
    # SQLITE CONNECTION
    logger.info("[SQLITE] START")
    con = sqlite3.connect(setup_dict['log_db'])     # Creates connection
    cur = con.cursor()                              # cursor objects needed to make changes
    
    # GET OUR STEM LIST
    stem_list = stemlist_from_logdb(cur, logger)
    # IF EMPTY, NO NEW FILES TO PROCESS - EXIT 
    if len(stem_list) == 0:
        con.close()
        logger.info("[EXIT] - No new stems to process - Closing sqlite connection and exiting (0).")
        return 0  # here this is a bash error code 0 = SUCCESS
    
    # FOR EACH FILE WE HAVE TO PROCESS
    for stem in stem_list:
        # 1. Make the correct JSON file path (input) and csv file path (output)
        date = stem[:8]
        INPUT_PATH = setup_dict['json_dir'].parent / date /  f"{stem}.json"
        OUTPUT_PATH = setup_dict['csv_dir'].parent / date /  f"{stem}.csv"

        # 2. Make the features and so
        exit_code = make_features(input_path = INPUT_PATH,
                                  output_path = OUTPUT_PATH,
                                  logger = logger
                                  )
        # 3. Updatee the feature_making table in SQLite depending on 
        #    whether we were successful or not at making our features
        # TODO: Do I want to maybe change my exit codes? I know I wanted
        # to be like bash and have 0 = success but it's a pain in my bum right now
        if exit_code in [0, -1]:
            if exit_code == 0:
                status_code = 1 # SUCCESS
            else:
                status_code = -1 # PARTIAL SUCCESS
            sql = "UPDATE feature_making SET r0b = ? WHERE stem = ?;"     
            cur.execute(sql, (status_code, stem,))
            con.commit()

            logger.info(f"[SQLITE] stem={stem} | status={status_code}")
        else:
            if exit_code == 1:
                status_code = 99  # generic failure
            else:
                status_code = exit_code
            sql = "UPDATE feature_making SET r0b = ? WHERE stem = ?;" 
            cur.execute(sql, (status_code, stem))
            con.commit()

            logger.info(f"[SQLITE] stem={stem} | status={status_code}")
        
    # CLEAN UP
    con.close()
    logger.info("[SQLITE] connection closed.")
    return 0 # Bash exit code 0 = SUCCESS


if __name__=='__main__':
    sys.exit(main())
