import json
import logging
from datetime import datetime
from pathlib import Path
import os
import yaml
import sqlite3


# TODO: Set up logger

# Constants
INSTRUMENTID = 287
REPORTING_GROUP_ID = 111
FILTER_IDS = {
    'u': 160,
    'g': 161,
    'r': 162,
    'i': 163,
    'z': 164,
    'y': 165
}
FLUX_UNITID = 34  # nJy
DATA_SOURCE_GROUPID = 165  # rubin
REPORTER = "HFStevance, et al. "


# need to check an object isn't already in TNS:caveat there may be a delay of a few hours between syncs
# I might want to keep track of what I send to TNS. 
LOGGER = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s")

LOGGER.info(f"[INIT] - tns utils")
# GET SETTINGS LOCATION: from the environment or grab the default. 
env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    SETTINGS_PATH = Path(env_settings)
else:                                            # or go to default file
    SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"


def set_up(settings_path: Path = SETTINGS_PATH,
           logger = LOGGER
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
    logger.info(f" [SETUP] START")
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
                      'log_db':  Path(config['base_dir']) / "db" / "log.db",   # sqlite log db NOT IN A YEAR/DAY SUBDIR    
                     }

    logger.info(f"[SETUP] SUCCESS")
    
    return setup_dict


def make_tns_report_dictionary():
    # PSEUDO CODE:
    # inputs: diaObjectId_list
    # Logic:
    # Read the settings file (grab utility from other modules?)
    # Establish connection with sqlite3 LOG_DB database
    # initialise json_paths list 
    # For diaObjectId in diaObjectId_list:
    #     SELECT stem FROM diaobjid_stems WHERE diaObjectId = ?; (? will be diaObjectId)
    #     Create the jsonpath (will have JSON_DIR from reading the settings file)
    #     append to list of paths
    # for each path:
    #     read the json data for that diaObjectId
    #     make the tns report sub dictionary
    #     add to the main tns_dict 
    #     increment the counter (needed for)
    # return the tns_dict 
    #
    # Note: this is not optimised because objects might be in the same file 
    # but i think that optimising this part of the code will take longer and make it harder to maintain
    # without a needed speed up. 

    tns_dict = {'at_report': {}}
    counter = 0

    # will need to be in a loop over our reported objects
    tns_dict['at_report'][str(counter)] = {'ra': {'value': },
                                           }


tnsDict['at_report'][str(counter)] = {'ra': {'value': str(raAvg)},
                                                  'dec': {'value': str(decAvg)},
                                                  'internal_name': internalName,
                                                  'discovery_datetime': discoveryDate,
                                                  'at_type': str(atType),
                                                  'reporting_group_id': str(groupId),
                                                  'discovery_data_source_id': str(groupId),
                                                  'reporter': reporter,
                                                  'photometry': {'photometry_group': {str(counter): {'obsdate': discoveryDate,
                                                                                                     'flux': str(discoveryMag),
                                                                                                     'flux_error': str(discoveryMagError),
                                                                                                     'limiting_flux': str(limitingMag),
                                                                                                     'flux_units': '1',
                                                                                                     'filter_value': discoveryFilter,
                                                                                                     'instrument_value': discoveryInstrument,
                                                                                                     'exptime': str(discoveryExptime),
                                                                                                     'observer': 'Robot',
                                                                                                     'comments': ''}
                                                                                       }
                                                                 },
                                                  'non_detection': nonDetectionData,
                                                  'proprietary_period_groups': [ str(groupId) ],
                                                  'proprietary_period': { 'proprietary_period_value': '0',
                                                                          'proprietary_period_units': 'days' },
                                                  }

            if addInternalIDs:
                tnsDict['at_report'][str(counter)]['internal_ids'] = {"internal_name": internalName,
                                                                      "internal_objid": str(row['id'])}


# read json file and make TNS report json data
