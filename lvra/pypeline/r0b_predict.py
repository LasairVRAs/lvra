#!/usr/bin/env python3
import os
import sys
import logging
from pathlib import Path
import yaml
import joblib
import pandas as pd
import lasair
from lvra.utils.misc import set_up, read_model_config
import sqlite3
from lvra.utils.predict import predict
#import lvra.utils as lutils


# #-#-#-#-#-# #
#  CONSTANTS  #
# #-#-#-#-#-# #



env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    SETTINGS_PATH = Path(env_settings)
else:                                            # or go to default file
    SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"

LOG_NAME = "r0b_predict.log"
MODEL_CONFIG_FILE = "r0b_config.yaml"


# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
# FUNCTIONS CALLED BY MAIN (split for better testing) #
# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #

def stemlist_from_log(sqlite_cursor, 
                      model_name,
                      logger,
                     ):
    """Find the stems for which the feature files were made but annotating was not completed
    """
    
    sql = "SELECT * FROM annotating JOIN feature_making ON" \
        "annotating.stem=feature_making.stem"\
        f"WHERE ABS(annotating.{model_name})!=1 AND ABS(feature_making.{model_name})=1;"
    
    # TODO: AND CHECK STEM NOT IN PROVENANCE TABLE????
    # I WONDER IF DOING THIS EVERYTIME IS SLOWER THAN REPEATING PREDICION
    # OCCASIONALLY....
    
    res = sqlite_cursor.execute(sql)
    logger.info("[SQLITE] Fetching Stem list")
    # The result from fetchall will look like e.g. [('20260127_115934',), ('20260127_134852',)]
    # so we need to do list comprehension to have a list of just strings and not tuples of strings
    _stem_ls = res.fetchall() 
    stem_ls = [stem[0] for stem in _stem_ls]


    
    logger.info("[SQLITE] SUCCESS Fetching Stem list | Connection NOT CLOSED")

    return stem_ls

def update_provenance_table(scores_df,
                            sqlite_cursor,
                            stem,
                            model_name,
                            model_version,
                            connection,
                            logger):
    
    sql_provenance = "INSERT INTO provenance "\
                    "(diaObjectId, diaSourceId, stem, score, model_name, model_version) "\
                    "VALUES (?, ?, ?, ?, ?, ?)"   

    for i in range(scores_df.shape[0]):
        _diaObjectId = scores_df['diaObjectId'].iloc[i]
        _diaSourceId = scores_df['diaSourceId'].iloc[i]
        _score = scores_df['score'].iloc[i]
        sqlite_cursor.execute(sql_provenance, (int(_diaObjectId), 
                                               int(_diaSourceId), 
                                               stem, 
                                               _score, 
                                               model_name, 
                                               model_version))   
    connection.commit()
    logger.info(f"[SQLITE] SUCCESS | Updated provenance table - stem={stem}")           

# #-#-# #
# MAIN  #
# #-#-# #

def main():

    # -------------------------------------------------- #
    #                      SET UP                        #
    # -------------------------------------------------- #

    # General settings and initialisation of the logger
    setup_dict, logger = set_up(settings_path=SETTINGS_PATH, 
                                log_name=LOG_NAME)
    
    # Model specific configs 
    # (that yaml file is in the same directory as SETTINGS_PATH so can take the parent)
    model_conf_dict, status_code = read_model_config(SETTINGS_PATH.parent/MODEL_CONFIG_FILE, 
                                                     logger)
         
    # Initialise our SQLite cursor and connection
    # The use of row_factory is required to get the column names when doing fetchall()
    # which is used later to make a neat dataframe. Not just cosmetic here. 
    logger.info("[SQLITE] START")
    con = sqlite3.connect(setup_dict['log_db'])     
    con.row_factory = lambda cursor, row: {col[0] : row[i] for i, col in enumerate(cursor.description)}
    cur = con.cursor()                              

    # -------------------------------------------------- #
    #           WHAT IS THERE TO SCORE?                  #
    # -------------------------------------------------- #

    # Find the stems that need to be processed:
    # those with "annotating" status not 1 or -1, AND a feature_making status of 1 or -1
    # (we can't make predictions without feature files)
    # TODO: I need to split predict and annotate otherwise I'm going to the the predict step again
    # if the code fails below at the annotation stage!
    stem_list = stemlist_from_log(sqlite_cursor=cur,
                                  model_name=model_conf_dict['MODEL_NAME'],
                                  logger=logger)
    
    if len(stem_list)==0:
        logger.info("[SQLITE] No stems to score. Exiting.")
        con.close()
        return 0
    

    # -------------------------------------------------- #
    #                      SCORING                       #
    # -------------------------------------------------- #


    # Load the model
    model = joblib.load(model_conf_dict['MODEL_PATH'])

    # Load the dataframe for each stem
    for stem in stem_list:
        # LOAD DATA
        logger.info(f"[PREDICT] START - stem={stem}")
        try:
            _df = pd.read_csv((setup_dict['csv_dir'].parent / stem[:8] / stem).with_suffix('.csv'))
        except FileNotFoundError as e:
            logger.error(f"[PREDICT] FAIL - stem={stem} reason=Feature file not found")
            continue

        # PREDICT
        scores_df, status_code =predict(df=_df,
                                        model=model,
                                        logger=logger
                                        )
        if status_code==0:
            logger.info(f"[PREDICT] SUCCESS - stem={stem}")

        # UPDATE PROVENANCE TABLE
        # WARNING: There is another for-loop in this function
        # so this step may slow us dow SIGNIFICANTLY for 
        # large number of diaObjectIds....
        update_provenance_table(scores_df=scores_df,
                                sqlite_cursor=cur,
                                stem=stem,
                                model_name=model_conf_dict['MODEL_NAME'],
                                model_version=model_conf_dict['MODEL_VERSION'],
                                connection=con,
                                logger=logger
                                )
        
    logger.info("[PREDICT] ----- END ------- ")
    return 0 # success shell exit code

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
    #import argparse
    #parser = argparse.ArgumentParser()
    #parser.add_argument("ANNOTATOR")
    #parser.add_argument("MODEL_NAME")
    #parser.add_argument("FEATURES_PATH")
    #parser.add_argument("--debug", action="store_true")
    #args = parser.parse_args()
    #code = main(args.ANNOTATOR, args.MODEL_NAME, args.FEATURES_PATH, debug=args.debug)
    #sys.exit(code)
