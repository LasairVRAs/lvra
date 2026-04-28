import json
from lasair import lasair_consumer
import logging
from pathlib import Path
from datetime import datetime
import os
import sqlite3
from lvra.utils.misc import set_up  

# #-#-#-#-#-# #
#  CONSTANTS  #
# #-#-#-#-#-# #

#N_MESSAGES = 10_000 # number of messages to poll for 
N_MESSAGES = 10
env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    SETTINGS_PATH= Path(env_settings)
else:                                            # or go to default file
    SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "public_settings.yaml"

LOG_NAME = "kafka.log"

# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #
# FUNCTIONS CALLED BY MAIN (split for better testing) #
# #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-# #



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
         
    consumer = lasair_consumer(setup_dict['kafka_server'], 
                               setup_dict['group_id'], 
                               setup_dict['my_topic'])

    # make a timestamped file for this poll/run
    stem = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = setup_dict['json_dir'] / f"{stem}.json" # with_suffix below REPLACES the .json
    tmp_path = out_path.with_suffix(".jsn.tmp")  # <-- temporary while writing


    
    # -------------------------------------------------- #
    #             WRITE EACH ALERT TO FILE               #
    # -------------------------------------------------- #

    written = 0

    # We open our temporary file which will be renamed upon success
    # (we are doing things atomically in this house!)
    with tmp_path.open("w", encoding="utf-8") as f: 
        f.write("[\n")

        n = 0
        # List to collect the diaObjectIds that I will put in my sqlite table
        diaObjectId_list = []

        # Whilst we still have messages to poll in our kafka topic (up to how max limit)... 
        while n < N_MESSAGES:
            # 1. We poll! 
            msg = consumer.poll(timeout=20)

            # If we get nothing or there is an error, we break out of the loop. 
            if msg is None:
                break
            if msg.error():
                logger.info(f'{str(msg.error())}')
                break
            
            # 2. If we make it here it means we have messages. 
            raw = msg.value()
            # msg.value() may be bytes or str depending on client
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")

            # 3. Get the JSON data for our alert.
            result = json.loads(raw)

            # 4. Write it to file with the correct logic:
            #    Comma before every item except the first
            if written:
                f.write(",\n")
            json.dump(result, f, ensure_ascii=False, indent=2)

            # 5. Increment our written counter
            written += 1

            # 6. collect our diaObjectIds (no idea when they would be null)
            # TODO: if _id is null we should catch this and through some error message
            # is there any expected runtime cases where diaObjectId (the INDEX!) is missing and
            # we want to silently continue?
            _id = result.get('diaObjectId', 'null')
            diaObjectId_list.append(_id)

            # This only if I'm trying to see each alert come through 
            logger.debug(f'Got data for: {_id}')

            # 6. Increment our message counter.... I am not sure if this is ever different from "written". 
            #    Redundant?
            n += 1

        # The File has to end with a closing squre bracket
        f.write("\n]\n")

    # -------------------------------------------------- #
    #                POST-WRITE LOGISTICS                #
    #    Rename File and Initialise SQLite table rows    #
    # -------------------------------------------------- #
  
    try:
        if written == 0:
            # no messages received — remove the temp file if it exists
            if tmp_path.exists():
                tmp_path.unlink()
            logger.info("EMPTY Ran but no messages received — no file written.")
        else:
            # RENAMING
            # Atomically replace any existing final file with the tmp file
            os.replace(str(tmp_path), str(out_path))

            # SQLITE setup
            # Here because don't need to connect to db if we didn't have any messages
            logger.info(f"Establishing Connection with {setup_dict['log_db']}")
            con = sqlite3.connect(setup_dict['log_db'])             # create connect to log database
            cur = con.cursor()                        # we need a cursor to do read/write operations

            # SQLITE initialising the rows for feature_making and annotating tables
            sql_feature_making = "INSERT INTO feature_making (stem, r0b) VALUES (?, 0)"
            sql_predict = "INSERT INTO predict (stem, r0b) VALUES (?, 0)"
            sql_annotating = "INSERT INTO annotating (stem, r0b) VALUES (?, 0)"
            cur.execute(sql_feature_making, (stem,))
            cur.execute(sql_predict, (stem,))
            cur.execute(sql_annotating, (stem,))

            # SQLITE insert diaObjectIds into the diaobjid_stem table
            # if the row exists, update the stem column to be the current stem
            sql_diaobjid_stem = "INSERT INTO diaobjid_stems (diaObjectId, stem, timestamp) VALUES (?, ?, current_timestamp) ON CONFLICT(diaObjectId) DO UPDATE SET stem=excluded.stem"
            for diaObjectId in diaObjectId_list:
                cur.execute(sql_diaobjid_stem, (diaObjectId, stem))

            # SQLITE commit (perform the actions) and close connection 
            con.commit()
            con.close()
            logger.info(f"[SQLITE] Closed Connection with {setup_dict['log_db']}")

            # Log
            logger.info(f"PRODUCED path={out_path} n={written} | row added to log tables stem={stem}")

    except Exception:
        # If rename or cleanup fails, log it and leave temp file for inspection
        logger.exception("Error finalizing output file; temporary file left for inspection.")
        raise

    return 0

if __name__=='__main__':
    main()

