"""
Name: r0b_feature_maker.py
Author: H.F.Stevance (hfstevance@gmail.com | GitHub: HeloiseS)
Description: When run as a script, calls the main function which
* 1) Reads the config file located in environment variable LVRA_SETTINGS or, if not defined
looks for the "public_seetings.yaml" file located in ../../../data/
* 2) Connects to the log.db SQLite database (strict file structure expected, see docs) and 
returns a list of stems for json files whose features have not been successfully extracted for r0b
* 3) opens the corresponding json files, extracts the features and then outputs the csv files


Dev Notes: 
#TODO: Major Logic change!
# currently the bash script reads the logs and calles this with a filename.json as an argument
# INPUT_PATH here. Instead what we can do is:
# 1. create sqlite connection
# 2. create an sqlite cursor 
# 3. find all stems (index primary ley) where r0b (column) != 1 (1=SUCCESS)
# SELECT stem from feature_making WHERE r0b != 1; 
# This will return either:
# a. NO stems because everything has been done and completed -> Exit
# b. One stem -> read file and do feature creation 
# c. SEVERAL stems if some json files weren't successfuly created features for
# -> TODO: THINK ABOUT HOW TO HANDLE THIS HERE
"""

import logging
from pathlib import Path
import os
from lvra.utils.features import FeaturesRealBogus
import sys
import yaml
import sqlite3
from datetime import datetime




# GET SETTINGS LOCATION: from the environment or grab the default. 
env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    SETTINGS_PATH = Path(env_settings)
else:                                            # or go to default file
    SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"

# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
# FUNCTIONS CALLED BY MAIN (split for better testing) #
# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
 
def set_up(settings_path: Path = SETTINGS_PATH,
          ):
    """Creates the set_up dictionary
    
    Parameters
    ----------    
    settings_path: str
        Public settings file path. Must contain the keys: endpoint, base_dir
    logger: logger object
        logger object already set up at the top of the script. Default is LOGGER (defined at top of module)

    Returns
    -------
    dictionary with keys: TODO -added list
    """   
    # TODO: add a r0b_feature_version to the yaml file to put in FEATURE_SUFFIX 
        
    # The data subdirectories are organised in several levels: TYPE > YYYY > YYYYMMDD
    # so our logs and JSONS would end up in the folders:
    # $base_dir/2026/20260127 and $base_dir/JSON/2026/20260127 respectively
    # So I need the current year and day in that format to make the directories
    current_year = datetime.utcnow().strftime("%Y")
    current_day = datetime.utcnow().strftime("%Y%m%d")
    sub_dir = Path(current_year) / Path(current_day)
    

    with settings_path.open("r") as settings:
        config = yaml.safe_load(settings)
        setup_dict = {'base_dir': Path(config['base_dir']),          
                      'json_dir': Path(config['base_dir'])/ "JSON" / sub_dir,  # where lasair input data stored
                      'csv_dir':  Path(config['base_dir']) / "csv" / sub_dir,  # where csv feature output files stored
                      'log_dir':  Path(config['base_dir']) / "logs" / sub_dir, 
                      'log_db':  Path(config['base_dir']) / "db" / "log.db",   # sqlite log db NOT IN A YEAR/DAY SUBDIR    
                      'endpoint': config['endpoint'],                          # url endpoint Lasair
                     }

    LOGGER = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
    logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s",
                    handlers=[logging.FileHandler(setup_dict['log_dir'] / "r0b_feature_maker.log"),
                        logging.StreamHandler()
                    ])
    LOGGER.info(f"[INIT] - SET UP COMPLETE")

    
    return setup_dict, LOGGER 

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
    sql = "SELECT stem FROM feature_making WHERE r0b != 1;"
    res = sqlite_cursor.execute(sql)
    logger.info(f"[SQLITE] Fetching Stem list")
    # The result from fetchall will look like e.g. [('20260127_115934',), ('20260127_134852',)]
    # so we need to do list comprehension to have a list of just strings and not tuples of strings
    _stem_ls = res.fetchall() 
    stem_ls = [stem[0] for stem in _stem_ls]
    
    logger.info(f"[SQLITE] SUCCESS Fetching Stem list | Connection NOT CLOSED")

    return stem_ls


def make_features(input_path: Path,
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
        logger.error(f"[MAKE_FEATURES] FAIL - reason=FileNotFound")
        return 1
    except Exception as e:
        logger.error(f"[MAKE_FEATURES] FAIL -  reason={e}")
        return 1


# #-#-# #
# MAIN  #
# #-#-# #

def main( settings_path: Path = SETTINGS_PATH
         ):
    # SETUP 
    setup_dict, logger = set_up(settings_path)
         
    # SQLITE CONNECTION
    logger.info(f"[SQLITE] START")
    con = sqlite3.connect(setup_dict['log_db'])     # Creates connection
    cur = con.cursor()                              # cursor objects needed to make changes
    
    # GET OUR STEM LIST
    stem_list = stemlist_from_logdb(cur, logger)
    if len(stem_list) == 0:
        con.close()
        logger.info("[EXIT] - No new stems to process - Closing sqlite connection and exiting (0).")
        return 0  # here this is a bash error code 0 = SUCCESS
    
    for stem in stem_list:
        INPUT_PATH = setup_dict['json_dir'] / f"{stem}.json"
        OUTPUT_PATH = setup_dict['csv_dir'] / f"{stem}.csv"

        exit_code = make_features(input_path = INPUT_PATH,
                                   output_path = OUTPUT_PATH,
                                    endpoint = setup_dict['endpoint'],
                                  logger = logger
                                  )
        if exit_code == 0:
            sql = "UPDATE feature_making SET r0b = 1 WHERE stem = ?;"     
            cur.execute(sql, (stem,))
            con.commit()

            logger.info(f"[SQLITE] stem {stem} r0b status set to 1 (success)")
        else:
            sql = "UPDATE feature_making SET r0b = 99 WHERE stem = ?;" 
            cur.execute(sql, (stem,))
            con.commit()

            logger.info(f"[SQLITE] stem {stem} r0b status set to 99 (tried and failed)")
        
    # CLEAN UP
    con.close()
    logger.info("[SQLITE] connection closed.")
    return 0 # Bash exit code 0 = SUCCESS


if __name__=='__main__':
    sys.exit(main())
