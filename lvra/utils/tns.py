#!/usr/bin/env python3
import json
import logging
from pathlib import Path
import os
#from turtle import pd
import requests
import pandas as pd
from lvra.utils.misc import set_up
import sqlite3


# #-#-#-#-#-# #
#  CONSTANTS  #
# #-#-#-#-#-# #


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
REPORTER = "H. F. Stevance (University of Oxford), R. D. Williams, G. P. Francis (University of Edinburgh), D. R. Young (Queen's University Belfast), K. W. Smith, S. J. Smartt (University of Oxford / Queen's University Belfast), A. Lawrence, T. M. Sloan (University of Edinburgh)"
 
LVRA_TNS_MARKER = {"tns_id":197854,"type": "bot", "name":"LVRA"} # From TNS bot page where I got my API key


# GET SETTINGS LOCATION: from the environment or grab the default. 
env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    SETTINGS_PATH = Path(env_settings)
else:                                            # or go to default file
    SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"


# Grabbing the TNS API KEY from our environment.
TNS_API_KEY = os.environ.get("LVRA_TNS_API_KEY", None)


LOG_NAME = "tns_reporter"

# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
# FUNCTIONS CALLED BY MAIN (split for better testing) #
# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
       


    # PSEUDO CODE:
    # HERE LET'S DO ONE OBJECT ID - WE'LL DO THE LOOP SOMEWHERE ELSE.
    # inputs: diaObjectId_list - defined by whatever bot or user decides to report.
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

# 2026-02-27 KWS Added converter from MJD to date fraction (as required by TNS).
def mjdToDateFraction(mjd, delimiter = '-', decimalPlaces = 5):
   """getDateFractionMJD.

   Args:
        mjd:
        delimiter:
        decimalPlaces:
   """

   from datetime import datetime

   floatWidth = decimalPlaces + 3 # always have 00.00 or 00.000 or 00.0000, etc
   unixtime = (mjd + 2400000.5 - 2440587.5) * 86400.0;
   theDate = datetime.utcfromtimestamp(unixtime)
   dateString = theDate.strftime("%Y:%m:%d:%H:%M:%S")
   (year, month, day, hour, min, sec) = dateString.split(':')
   dayFraction = int(day) + int(hour)/24.0 + int(min)/(24.0 * 60.0) + int(sec)/(24.0 * 60.0 * 60.0)
   dateFraction = "%s%s%s%s%0*.*f" % (year, delimiter, month, delimiter, floatWidth, decimalPlaces, dayFraction)
   return dateFraction


def make_tns_report_dictionary(diaObjectId, csv_dir, sqlitecursor, logger):
    # 1) get latest stem from provenance
    _sql = "SELECT stem FROM provenance WHERE diaObjectId = ? ORDER BY timestamp DESC LIMIT 1"
    sqlitecursor.execute(_sql, (diaObjectId,))
    fetched = sqlitecursor.fetchone()
    if not fetched:
        logger.error(f"No provenance record found for diaObjectId={diaObjectId}")
        return 97  # no provenance mapping

    stem = fetched[0]

    # 2) build path and read csv
    path = csv_dir.parent.parent / f"{stem[:4]}/{stem[:8]}/{stem}.csv"
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        logger.error(f"Feature CSV not found at {path} for stem={stem}")
        return 21  # match your existing code for input file missing

    # 3) check required columns exist
    required_cols = {'diaObjectId', 'lastDiaSourceMjdTai', 'psfFlux', 'band', 'ra', 'decl'}
    if not required_cols.issubset(set(df.columns)):
        logger.error(f"Missing required columns in {path}. Required: {required_cols}")
        return 96  # missing columns

    # 4) filter rows for this diaObjectId
    dio_rows = df[df['diaObjectId'] == diaObjectId]
    if dio_rows.empty:
        logger.error(f"No rows for diaObjectId={diaObjectId} in {path}")
        return 98  # no rows for this object in the CSV

    # 5) pick most recent row (works if there's 1 row or many)
    # using nlargest is concise and handles ties consistently
    top_row = dio_rows.nlargest(1, 'lastDiaSourceMjdTai').iloc[0]

    # 6) map band -> filter id, handling unknown bands
    band = top_row['band']
    try:
        FILTERID = FILTER_IDS[band]
    except KeyError:
        logger.error(f"Band {band} not found - REPORT NOT SENT FOR OBJECT {diaObjectId} | stem {stem}")
        return 99

    # 7) build dict (coerce numpy types to Python scalars)
    tns_dict = {
        'at_report': {
            'ra': {'value': str(float(top_row['ra']))},
            'dec': {'value': str(float(top_row['decl']))},
            'internal_name': {'value': f"LSST-AP-DO-{diaObjectId}"},
            'reporting_group_id': str(REPORTING_GROUP_ID),
            "discovery_datetime": mjdToDateFraction(float(top_row['lastDiaSourceMjdTai']))
            'reporter': REPORTER,
            'discovery_data_source_id': str(DATA_SOURCE_GROUPID),
            'non_detection': {'archiveid': "2"},   # 2 = DSS
            'photometry': {
                '0': {
                'obsdate': mjdToDateFraction(float(top_row['lastDiaSourceMjdTai'])),
                'flux': str(float(top_row['psfFlux'])),
                'flux_units': str(FLUX_UNITID),
                'filter_value': str(FILTERID),
                'instrument_value': str(INSTRUMENTID),
                }
            },
        }
    }

    return tns_dict


def report2TNS(diaObjectId_list, 
               setup_dict = None,
               sqlitecursor = None,
               connection = None,
               tns_api_key = None,
               logger = None,
               dry_run = False,
               sandbox = True,
                 ):
    
    if logger is None:
        logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

    if setup_dict is None:
        setup_dict = set_up(settings_path=SETTINGS_PATH, 
                            log_name=LOG_NAME,
                            logger=logger
                            )
        
    api_key = tns_api_key if tns_api_key is not None else TNS_API_KEY
    if api_key is None:
        logger.error("TNS API key not given as arguement nor found in envrionment variable LVRA_TNS_API_KEY")
        return 99
    
    if sqlitecursor is None or connection is None:
        logger.info('Database cursor or connection nor provided - MAKING NOW')

        connection = sqlite3.connect(setup_dict['log_db'])
        sqlitecursor = connection.cursor()
        close_conn = True
        logger.info(f'Database connection established - LOG_DB: {setup_dict["log_db"]}')

    reports = []
    failures = {}

    for diaObjectId in diaObjectId_list:
        try:
            tns_dict = make_tns_report_dictionary(diaObjectId, 
                                                setup_dict['csv_dir'], 
                                                sqlitecursor, logger) 
        except Exception as e:
            logger.error(f"UNEXPECTED Error making TNS report dictionary for diaObjectId={diaObjectId}: {e}")
            failures[diaObjectId] = repr(e)
            continue

        if isinstance(tns_dict, int):
            failures[diaObjectId] = tns_dict
            continue

        reports.append(tns_dict)

    # Build top-level payload. Historically you constructed a single dict;
    # for bulk reports we'll send the list under a wrapper to match earlier usage.
    payload = {'reports': reports} if len(reports) != 1 else reports[0]

    summary = {
        'n_requested': len(diaObjectId_list),
        'n_payload': len(reports),
        'n_posted': None,
        'failures': failures,
        'payload': payload
    }

    if dry_run:
        # do not send to TNS — useful for unit tests
        if close_conn:
            connection.close()
        return summary
    
    # choose endpoint
    base = TNS_BASE_URL_SANDBOX if sandbox else TNS_BASE_URL
    report_url = base + AT_REPORT_FORM

    header = {'User-Agent': 'tns_marker' + json.dumps(LVRA_TNS_MARKER), 'api_key': TNS_API_KEY}

    report_parameters = {'api_key': TNS_API_KEY, 'data': json.dumps(payload)}

    try:
        r = requests.post(report_url, data=report_parameters, timeout=300, headers=header)
        summary['n_posted'] = 1 if r.status_code < 400 else 0
        summary['response_status'] = r.status_code
        summary['response_text'] = getattr(r, 'text', None)
        logger.info(f"TNS POST status: {r.status_code}")
    except Exception as e:
        logger.exception(f"Failed to POST to TNS: {e}")
        summary['n_posted'] = 0
        summary['post_exception'] = repr(e)

    if close_conn:
        connection.close()
        logger.info("Database connection closed")

    
    return summary

# TODO: make function to make the TNS call to get the report from them using the report Id they give back?
# TODO: am I even gettng this info properly above in my post rrequrest? 

def test_tns_report_dictionary():
    # read the json file in lvra/data/test/tns_example.json
    example_path = Path(__file__).resolve().parent.parent.parent / "data" / "test" / "tns_example.json"
    with example_path.open("r") as fh:
        tns_data = json.load(fh)
    return tns_data



# #-#-# #
# MAIN  #
# #-#-# #
def main():
    # Testing

    # -------------------------------------------------- #
    #                      SET UP                        #
    # -------------------------------------------------- #

    logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
    # General settings and initialisation of the logger
    setup_dict = set_up(settings_path=SETTINGS_PATH, 
                        log_name=LOG_NAME,
                        logger=logger
                        )
    
    diaObjectId_list = [169760231711572844, 169760231408535266] # expected to exist in repo test CSV
    summary = report2TNS(diaObjectId_list, 
                         setup_dict = setup_dict, 
                         logger = logger, 
                         dry_run = False, 
                         sandbox = True )
    print(summary)
    return 0 

"""
def main(TESTING = False):
    # -------------------------------------------------- #
    #                      SET UP                        #
    # -------------------------------------------------- #

    logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
    # General settings and initialisation of the logger
    setup_dict = set_up(settings_path=SETTINGS_PATH, 
                        log_name=LOG_NAME,
                        logger=logger
                        )
    
    if TNS_API_KEY is None:
        logger.error("TNS API key not found in environment variable LVRA_TNS_API_KEY")
        raise ValueError("TNS API key not found in environment variable LVRA_TNS_API_KEY")

    if TESTING:
        tns_dict = test_tns_report_dictionary()
        report_url = TNS_BASE_URL_SANDBOX + AT_REPORT_FORM
    else:
        tns_dict = make_tns_report_dictionary(logger=logger)
        report_url = TNS_BASE_URL + AT_REPORT_FORM

    # send to TNS 
    # this code uses as a base the code in here: https://github.com/genghisken/psat-server/blob/master/psat-server/scripts/utils/python/tnsAPI.py
    header = {'User-Agent': 'tns_marker' + json.dumps(LVRA_TNS_MARKER), 'api_key': TNS_API_KEY}



    # DON'T BE FOOLED! Just because requests accepts a dictionary for data, the VALUE of the
    # the 'data' key must still be a JSON string!! This had me confused for hours!!
    report_parameters = {'api_key': TNS_API_KEY, 'data': json.dumps(tns_dict)}

    r = requests.post(report_url, data = report_parameters, timeout = 300, headers = header)
    print('status:', r.status_code)
    #print('response text:', r.text)
    # what was actually sent
    #print('request headers:', r.request.headers)
    #print('request body (first 1000 chars):', getattr(r.request, 'body', None)[:1000])
    print(report_parameters)
""" 


if __name__ == "__main__":
    #main(TESTING=True)
    main()
