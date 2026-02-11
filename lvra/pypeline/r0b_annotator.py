#!/usr/bin/env python3
import os
import sys
import logging
from pathlib import Path
import pandas as pd
import lasair
from lvra.utils.misc import set_up, read_model_config
import sqlite3
#import lvra.utils as lutils


# #-#-#-#-#-# #
#  CONSTANTS  #
# #-#-#-#-#-# #



env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    SETTINGS_PATH = Path(env_settings)
else:                                            # or go to default file
    SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"

LOG_NAME = "r0b_annotator.log"
# TODO: this shouldn't be hard coded - it's a pain for dev. I need to find a better way, maybe allow taking it form cli
LASAIR_TOKEN = os.getenv("LASAIR_TOKEN")
MODEL_CONFIG_FILE = "r0b_config.yaml"


# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
# FUNCTIONS CALLED BY MAIN (split for better testing) #
# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
       

def get_pending_annotations(sqlite_cursor,  model_name, model_version, logger, ):
    """Join annotating and provenance tbales to find the 
    pending annotations for a given model name and version
    """
    _sql="select p.ID, p.diaObjectId, p.diaSourceId, p.stem, p.score, p.model_name, p.model_version "\
        "from annotating as a join provenance as p on a.stem = p.stem "\
        f"where ABS(a.{model_name})!=1 and "\
        f"p.model_name='{model_name}' and " \
        f"p.model_version='{model_version}' ;"

    res = sqlite_cursor.execute(_sql)
    list_results = res.fetchall()
    pending_anotations=pd.DataFrame(list_results, dtype=str)


    logger.info(f"[SQLITE] SUCCESS | Pending annotations - n={pending_anotations.shape[0]}")

    return pending_anotations

def get_threshold_flags(sqlite_cursor, diaSourceId, stem, logger):

    exit_code = 0
    try:
        _sql = f"SELECT * FROM threshold_flags_provenance "\
            f"WHERE diaSourceId={diaSourceId} and stem='{stem}';"
        res = sqlite_cursor.execute(_sql)
        flags = res.fetchall()
        if len(flags) == 0:
            logger.warning(f"[ANNOTATING] No threshold flags found for diaSourceId={diaSourceId} stem={stem} - This is UNEXEPCTED. All Falgs set to Null")
            flags_dict = {
                    'n_gt22': None,
                    'n_gt21': None,
                    'n_gt20': None,
                    'n_gt19': None,
                    'n_gt18': None,
                    'brighter22': None,
                    'brighter21': None,
                    'brighter20': None,
                    'brighter19': None,
                    'brighter18': None,
                    'first22': None,
                    'first21': None,
                    'first20': None,
                    'first19': None,
                    'first18': None,
                }   
        elif len(flags) > 1:
            logger.warning(f"[ANNOTATING] More than 1 row found in threshold_flags_provenance for diaSourceId={diaSourceId} stem={stem} - This is UNEXPECTED. Taking the first row but this might not be what you intended.")
        else:
            #logger.info(f"[ANNOTATING] Threshold flags found for diaSourceId={diaSourceId} stem={stem} - Adding to annotation provenance")
            pass

        if len(flags) >= 1:
                flags_dict = {
                    'n_gt22': flags[0]['n_gt22'],
                    'n_gt21': flags[0]['n_gt21'],
                    'n_gt20': flags[0]['n_gt20'],
                    'n_gt19': flags[0]['n_gt19'],
                    'n_gt18': flags[0]['n_gt18'],
                    'brighter22': flags[0]['brighter22'],
                    'brighter21': flags[0]['brighter21'],
                    'brighter20': flags[0]['brighter20'],
                    'brighter19': flags[0]['brighter19'],
                    'brighter18': flags[0]['brighter18'],
                    'first22': flags[0]['first22'],
                    'first21': flags[0]['first21'],
                    'first20': flags[0]['first20'],
                    'first19': flags[0]['first19'],
                    'first18': flags[0]['first18'],
                }
    except Exception as e:
        logger.error(f"[ANNOTATING] Failed to grab threshold flags for diaSourceId={diaSourceId} stem={stem} - reason: {e} - All flags set to None")
        flags_dict = {
            'n_gt22': None,
            'n_gt21': None,
            'n_gt20': None,
            'n_gt19': None,
            'n_gt18': None,
            'brighter22': None,
            'brighter21': None,
            'brighter20': None,
            'brighter19': None,
            'brighter18': None,
            'first22': None,
            'first21': None,
            'first20': None,
            'first19': None,
            'first18': None,
        }
        exit_code = 99

    # make a dict to return

    return exit_code, flags_dict

def annotate_loop(pending_annotations, 
                  L, 
                  model_conf_dict, 
                  sqlite_cursor,
                  logger):
    success_dois=[]
    failure_dois=[]
    stem_list = []

    for i, row in pending_annotations.iterrows():
        # Grab the threshold flags from the sqlite table
        exit_code, flags_dict = get_threshold_flags(sqlite_cursor, row['diaSourceId'], row['stem'], logger)

        _class_dict = {'blame_diaSourceId': row['diaSourceId'],
                       'n_gt22': flags_dict['n_gt22'],
                       'n_gt21': flags_dict['n_gt21'],
                       'n_gt20': flags_dict['n_gt20'], 
                       'n_gt19': flags_dict['n_gt19'],
                       'n_gt18': flags_dict['n_gt18'],
                       'brighter22': flags_dict['brighter22'], 
                       'brighter21': flags_dict['brighter21'], 
                       'brighter20': flags_dict['brighter20'], 
                       'brighter19': flags_dict['brighter19'], 
                       'brighter18': flags_dict['brighter18'],
                       'first22': flags_dict['first22'], 
                       'first21': flags_dict['first21'], 
                       'first20': flags_dict['first20'], 
                       'first19': flags_dict['first19'], 
                       'first18': flags_dict['first18'],  
                       'model_version': row['model_version'], 
                       'provenance_ID': row['ID'],
                       'stem': row['stem']
                    }
        try:
            L.annotate(topic=model_conf_dict['TOPIC_OUT'],
                    objectId=row['diaObjectId'],
                    classification=row['score'],
                    version=row['model_version'],
                    explanation=model_conf_dict['EXPLANATION'],
                    classdict=_class_dict,
                    url=model_conf_dict['URL']
            )
            success_dois.append(row['diaObjectId'])
            stem_list.append(row['stem'])
        except Exception as e:
            logger.error(f"[ANNOTATING] diaObjectId {row['diaObjectId']} | {e}")
            failure_dois.append(row['diaObjectId'])

    return success_dois, failure_dois, stem_list

def update_annotating_table(status_code,
                            unique_stems,
                            model_name,
                            sqlite_cursor,
                            connection,
                            logger):
    


    for stem in unique_stems:
        sql = f"UPDATE annotating SET timestamp=current_timestamp, {model_name} = ? WHERE stem = ?;"     
        sqlite_cursor.execute(sql, (status_code, stem,))

    connection.commit()
    logger.info(f"[SQLITE] SUCCESS | Updated annotating table - stems={len(unique_stems)}")

    return 

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
    if LASAIR_TOKEN is None:
        logger.error("[TOKEN] - FAILURE - LASAIR_TOKEN env variable is None. Exiting")
        return 99
    else:
        logger.info("[TOKEN] - Loaded Successfully (Could still be wrong)")
    
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
    #           WHAT IS THERE TO ANNOTATE?               #
    # -------------------------------------------------- #

    # Find stems that don't have annotations but have predictions
    pending_annotations = get_pending_annotations(sqlite_cursor=cur,
                                                  model_name=model_conf_dict['MODEL_NAME'],
                                                  model_version=model_conf_dict['MODEL_VERSION'],
                                                  logger=logger,
                                                  )
    
    if pending_annotations.shape[0]==0:
        logger.info("[SQLITE] No pending annotations to make. Exiting.")
        con.close()
        return 0

    # -------------------------------------------------- #
    #                  LASAIR CLIENT                     #
    # -------------------------------------------------- #


    try:
        L = lasair.lasair_client(LASAIR_TOKEN, endpoint=setup_dict['endpoint'])
    except Exception:
        logger.exception("Failed to construct Lasair client")
        logger.info(f"FAIL annotate model={model_conf_dict['MODEL_NAME']} reason=lasair_client_error")
        return 41

    success_dois, failure_dois, stem_list =annotate_loop(pending_annotations,
                                                         L, 
                                                         model_conf_dict, 
                                                         sqlite_cursor=cur,
                                                         logger=logger)
    
    # LOGGING AND STATUS CODES IN DIFFERENT SCENARIOS
    if len(success_dois) == pending_annotations.shape[0]:
        status_code = 1
        logger.info(f"[ANNOTATING] SUCCESS | status = {status_code}")
    elif len(failure_dois) == pending_annotations.shape[0]:
        status_code = 42
        logger.error(f"[ANNOTATING] FAILURE | status = {status_code} | No diaObjectId annotated ")
    elif (len(success_dois) + len(failure_dois)) == pending_annotations.shape[0] and len(failure_dois) > 0 and len(success_dois) > 0: 
        status_code = -1
        logger.warning(f"[ANNOTATING] PARTIAL SUCCESS | status = {status_code} |  Some diaObjectIds not annotated. See logging above.")
    else:
        status_code = 99
        logger.error(f"[ANNOTATING] FAILURE | status = {status_code} | Not all diaObjectIds accounted for!!!!!!")
    
    # UPDATE THE ANNOTATING TABLE
    status_code = update_annotating_table(status_code,
                                          unique_stems=list(set(stem_list)),
                                          model_name=model_conf_dict['MODEL_NAME'],
                                          sqlite_cursor=cur,
                                          connection=con,
                                          logger=logger
                                          )
    
    con.close()
    logger.info("[SQLITE] CLOSED CONNECTION")






    return 0 

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
