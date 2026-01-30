#!/usr/bin/env python3

import json
import logging
from datetime import datetime
from pathlib import Path
import os
import yaml
import requests


# TODO: Set up logger

# Constants
AT_REPORT_FORM = "set/bulk-report"
TNS_BASE_URL = "https://www.wis-tns.org/api/" # TODO: check this may be wrong
TNS_BASE_URL_SANDBOX = "https://sandbox.wis-tns.org/api/"

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
 
LVRA_TNS_MARKER = {"tns_id":197854,"type": "bot", "name":"LVRA"} # From TNS bot page where I got my API key

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


# Grabbing the TNS API KEY from our environment.
TNS_API_KEY = os.environ.get("LVRA_TNS_API_KEY", None)
if TNS_API_KEY is None:
    LOGGER.error("TNS API key not found in environment variable LVRA_TNS_API_KEY")
    raise ValueError("TNS API key not found in environment variable LVRA_TNS_API_KEY")




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
    # initialise internalId_list 
    # For diaObjectId in diaObjectId_list:
    #     SELECT stem FROM diaobjid_stems WHERE diaObjectId = ?; (? will be diaObjectId)
    #     Create the jsonpath (will have JSON_DIR from reading the settings file)
    #     append to list of paths
    #     append to list of internal Ids (f"LSST-AP-DO-{diaObjectId}")
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
    #tns_dict['at_report'][str(counter)] = {'ra': {'value': },
    #                                       }

    """
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

    """
# read json file and make TNS report json data


def test_tns_report_dictionary():
    # read the json file in lvra/data/test/tns_example.json
    example_path = Path(__file__).resolve().parent.parent.parent / "data" / "test" / "tns_example.json"
    with example_path.open("r") as fh:
        tns_data = json.load(fh)
    return tns_data



# #######################################################33333
# Code pasted from Ken's module 
# TODO: REFACTOR AND SIMPLIFY FOR MY USE
# ###########################################################


# ###########################################################


def main(TESTING = False):
    setup = set_up()

    if TESTING:
        tns_dict = test_tns_report_dictionary()
        report_url = TNS_BASE_URL_SANDBOX + AT_REPORT_FORM
    else:
        tns_dict = make_tns_report_dictionary()
        report_url = TNS_BASE_URL + AT_REPORT_FORM

    # send to TNS 
    # this code uses as a base the code in here: https://github.com/genghisken/psat-server/blob/master/psat-server/scripts/utils/python/tnsAPI.py
    header = {'User-Agent': 'tns_marker' + json.dumps(LVRA_TNS_MARKER), 'api_key': TNS_API_KEY}



    # DON'T BE FOOLED! Just because requests accepts a dictionary for data, the VALUE of the
    # the 'data' key must still be a JSON string!! This had me confused for hours!!
    report_parameters = {'api_key': TNS_API_KEY, 'data': json.dumps(tns_dict)}

    r = requests.post(report_url, data = report_parameters, timeout = 300, headers = header)
    #print('status:', r.status_code)
    #print('response text:', r.text)
    # what was actually sent
    #print('request headers:', r.request.headers)
    #print('request body (first 1000 chars):', getattr(r.request, 'body', None)[:1000])
    print(report_parameters)


if __name__ == "__main__":
    main(TESTING=True)
