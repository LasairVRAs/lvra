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
from lvra.utils.features import json2cleandf
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


def threshold_flags_provenance(clean_df,
                               stem,
                             sqlite_cursor,
                             connection,
                             logger
                             ):
    

    columns = ['diaObjectId',
               'diaSourceId', 
               'N_above_22', 'N_above_21', 'N_above_20', 'N_above_19', 'N_above_18',
               'is_above_22', 'is_above_21', 'is_above_20', 'is_above_19', 'is_above_18',
               'first_time_22', 'first_time_21', 'first_time_20', 'first_time_19', 'first_time_18',
               ]

    try:
        _df = clean_df[columns]
    except KeyError as e:
        logger.error(f"[ADD_FLAG_PROVENANCE_ROWS] FAIL - reason = KeyError {e} - columns not found in clean_df")
        return 99
    
    for index, row in _df.iterrows():
        sql="INSERT INTO threshold_flags_provenance "\
            "(diaObjectId, diaSourceId, stem, " \
            "n_gt22, n_gt21, n_gt20, n_gt19, n_gt18,"\
            "brighter22, brighter21, brighter20, brighter19, brighter18, "\
            "first22, first21, first20, first19, first18) "\
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        
        values = (row['diaObjectId'], row['diaSourceId'], stem,
                  row['N_above_22'], row['N_above_21'], row['N_above_20'], row['N_above_19'], row['N_above_18'],
                  row['is_above_22'], row['is_above_21'], row['is_above_20'], row['is_above_19'], row['is_above_18'],
                  row['first_time_22'], row['first_time_21'], row['first_time_20'], row['first_time_19'], row['first_time_18']
                 )
        try:
            sqlite_cursor.execute(sql, values)
        except Exception as e:
            logger.error(f"[ADD_FLAG_PROVENANCE_ROWS] FAIL - reason = {e} - diaObjectId={row['diaObjectId']} diaSourceId={row['diaSourceId']}")
            return 99

    connection.commit()
    logger.info(f"[ADD_FLAG_PROVENANCE_ROWS] SUCCESS - Threshold flags logged in sqlite3 for stem={stem}")
    return 0


def make_features(input_path: Path,
                  output_path: Path,
                  logger):
    """Takes the path to a json file, extracts the features and outputs a csv file with those features.

    Parameters
    ----------
    input_path: Path
        The path to the json file we want to extract features from. Expected to be in the format 
        "../../../data/json/YYYY/YYYYMMDD_HHMMSS.json"
    output_path: Path
        The path to the csv file we want to output. Expected to be in the format 
        "../../../data/csv/YYYY/YYYYMMDD_HHMMSS.csv"
    logger: logging.Logger
        The logger object to log info, warnings and errors to the log file.

    Returns
    -------
    exit_code: int
        The exit code to log in the feature_making table in SQLite. 
        0 = SUCCESS, 1 = FAILURE, 21 = INPUT FILE NOT FOUND, 22 = OUTPUT FILE NOT FOUND, 30 = KEY ERROR IN JSON
    """

    # input: logging, input path, output path, endpoint
    # output: exit code
    logger.info(f"[MAKE_FEATURES] START | inpath={input_path} outpath={output_path}") 

    # TODO: add tests that actually go through these exceptions 
    try:
        clean_df, objectIds_withoutAlert_col = json2cleandf(input_path)
    except FileNotFoundError:
        logger.error(f"[MAKE_FEATURES] FAIL - reason = INPUT FileNotFound - inpath={input_path}")
        return 21, None
    except KeyError as e:
        logger.error(f"[MAKE_FEATURES] FAIL - reason = KeyError {e}")
        return 30, None
    except Exception as e:
        logger.error(f"[MAKE_FEATURES] FAIL - reason={e}")
        return 1, None

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
            logger.warning(f"[MAKE_FEATURES] WARNING - {len(objectIds_withoutAlert_col)}/{features_df.shape[0]} diaObjectIds had no alert key in their JSON entry"
                           f"and are NOT INCLUDED IN THE OUTPUT. List of diaObjectIds:\n{str(objectIds_withoutAlert_col)}")
            logger.info(f"[MAKE_FATURES] PARTIAL SUCCESS - {output_path} created ")
            
        logger.info(f"[MAKE_FEATURES] SUCCESS - {output_path} created ")
        return -1, clean_df

    except FileNotFoundError:
        logger.error("[MAKE_FEATURES] FAIL - reason= OUTPUT FileNotFound")
        return 22, None
    except Exception as e:
        logger.error(f"[MAKE_FEATURES] FAIL -  reason={e}")
        return 1, clean_df
    

# #-#-# #
# MAIN  #
# #-#-# #

def main():

    # -------------------------------------------------- #
    #                      SET UP                        #
    # -------------------------------------------------- #
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
    
    # -------------------------------------------------- #
    #     FOR EACH FILE WE HAVE TO PROCESS...            #
    # -------------------------------------------------- #
    for stem in stem_list:
        # 1. Make the correct JSON file path (input) and csv file path (output)
        date = stem[:8]
        INPUT_PATH = setup_dict['json_dir'].parent / date /  f"{stem}.json"
        OUTPUT_PATH = setup_dict['csv_dir'].parent / date /  f"{stem}.csv"

        # 2. Make the features and so
        exit_code, clean_df = make_features(input_path = INPUT_PATH,
                                            output_path = OUTPUT_PATH,
                                            logger = logger
                                            )
        
        
        # 3. Update the feature_making table in SQLite depending on 
        #    whether we were successful or not at making our features
        #    Also records the threshold flags into their provenance table
        if exit_code in [0, -1]:
            # WORKED AT LEAST A BIT SO CAN DO THE THE THRESHOLD FLAGS 
            prov_exit_code = threshold_flags_provenance(clean_df=clean_df,
                                                        stem=stem,
                                                        sqlite_cursor=cur,
                                                        connection=con,
                                                        logger=logger
                                                        )
            if prov_exit_code != 99:
                logger.info(f"[ADD FLAG PROVENANCE] SUCCESS - provenance rows added for stem={stem}")
            else:
                logger.error(f"[ADD FLAG PROVENANCE] FAIL - reason = see previous logs for details - stem={stem}")

            # UPDATE THE FEATURE_MAKING STATUS
            if exit_code == 0:
                status_code = 1 # SUCCESS
            else:
                status_code = -1 # PARTIAL SUCCESS
            sql = "UPDATE feature_making SET timestamp=current_timestamp,r0b = ? WHERE stem = ?;"     
            cur.execute(sql, (status_code, stem,))
            con.commit()

            logger.info(f"[SQLITE] stem={stem} | status={status_code}")
        else:
            # FAILED so just log 
            if exit_code == 1:
                status_code = 99  # generic failure
            else:
                status_code = exit_code
            sql = "UPDATE feature_making SET timestamp=current_timestamp, r0b = ? WHERE stem = ?;" 
            cur.execute(sql, (status_code, stem))
            con.commit()

            logger.info(f"[SQLITE] stem={stem} | status={status_code}")
        
    # CLEAN UP
    con.close()
    logger.info("[SQLITE] connection closed.")
    return 0 # Bash exit code 0 = SUCCESS


if __name__=='__main__':
    sys.exit(main())
