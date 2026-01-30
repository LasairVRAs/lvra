import json
from lasair import lasair_consumer
import yaml
import logging
from pathlib import Path
from datetime import datetime
import os
import sqlite3

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])


# Get the "public settings" from the environment or grab the default. 
env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    settings_path = Path(env_settings)
else:                                            # or go to default file
    settings_path = Path(__file__).resolve().parent.parent / "data" / "public_settings.yaml"

# The data subdirectories are organised in several levels: TYPE > YYYY > YYYYMMDD
# so our logs and JSONS would end up in the folders:
# $base_dir/2026/20260127 and $base_dir/JSON/2026/20260127 respectively
# So I need the current year and day in that format to make the directories
current_year = datetime.utcnow().strftime("%Y")
current_day = datetime.utcnow().strftime("%Y%m%d")
sub_dir = Path(current_year) / Path(current_day)

with settings_path.open("r") as settings:
    config = yaml.safe_load(settings)
    kafka_server = config['kafka_server']        # URL of the server
    my_topic = config['my_topic']                # topic associated with filter
    group_id = config['group_id']                # id used to keep your "place" in queue
    base_dir = Path(config['base_dir'])          # base directory for data storage
    json_data_dir = base_dir / "JSON" / sub_dir  # JSON output directory
    log_dir = base_dir / "logs" / sub_dir        # log directory 
    LOG_DB = base_dir / "db" / "log.db"          # sqlite log db NOT IN A YEAR/DAY SUBDIR

# create the directories if they do not exist - this happens if it is the first job of the day
# since our data file strucure is TYPE > YEAR > DAY 
json_data_dir.mkdir(parents=True, exist_ok=True)
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s",
                    handlers=[logging.FileHandler(log_dir / "kafka.log"),
                        #logging.StreamHandler()
                    ])


def main():
    consumer = lasair_consumer(kafka_server, 
                               group_id, 
                               my_topic)

    # make a timestamped file for this poll/run
    stem = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = json_data_dir / f"{stem}.json" # with_suffix below REPLACES the .json
    tmp_path = out_path.with_suffix(".jsn.tmp")  # <-- temporary while writing


    written = 0
    # open file once and stream JSON objects into an array
    f = tmp_path.open("w", encoding="utf-8")
    try:
        f.write("[\n")
        n = 0
        # List to collect the diaObjectIds that I will put in my sqlite table
        diaObjectId_list = []
        while n < 10_000:
            msg = consumer.poll(timeout=20)
            if msg is None:
                break
            if msg.error():
                logger.info(f'{str(msg.error())}')
                break

            # msg.value() may be bytes or str depending on client
            raw = msg.value()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            result = json.loads(raw)

            # write comma before every item except the first
            if written:
                f.write(",\n")
            json.dump(result, f, ensure_ascii=False, indent=2)
            written += 1


            _id = result.get('diaObjectId', 'null')
            
            # collect our diaObjectIds
            # TODO: if _id is null we should catch this and through some error message
            # is there any expected runtime cases where diaObjectId (the INDEX!) is missing and
            # we want to silently continue?
            diaObjectId_list.append(_id)
            logger.debug(f'Got data for: {_id}')

            n += 1

        f.write("\n]\n")
    finally:
        f.close()

    # Post-write handling: rename tmp -> final atomically, or clean up empty file
    try:
        if written == 0:
            # no messages received — remove the temp file if it exists
            if tmp_path.exists():
                tmp_path.unlink()
            logger.info("EMPTY Ran but no messages received — no file written.")
        else:
            # Atomically replace any existing final file with the tmp file
            os.replace(str(tmp_path), str(out_path))
            # TODO: add sqlite3 line to add a row to the feature_making and annotating table
            # with the timestamp (stem) as primary key

            logger.info(f"Establishing Connection with {LOG_DB}")
            con = sqlite3.connect(LOG_DB)             # create connect to log database
            cur = con.cursor()                        # we need a cursor to do read/write operations

            # SQLITE initialising the rows for feature_making and annotating tables
            sql_feature_making = "INSERT INTO feature_making (stem, r0b) VALUES (?, 0)"
            sql_annotating = "INSERT INTO annotating (stem, r0b) VALUES (?, 0)"
            cur.execute(sql_feature_making, (stem,))
            cur.execute(sql_annotating, (stem,))

            # SQLITE insert diaObjectIds into the diaobjid_stem table
            # if the row exists, update the stem column to be the current stem
            sql_diaobjid_stem = "INSERT INTO diaobjid_stems (diaObjectId, stem) VALUES (?, ?) ON CONFLICT(diaObjectId) DO UPDATE SET stem=excluded.stem"
            for diaObjectId in diaObjectId_list:
                cur.execute(sql_diaobjid_stem, (diaObjectId, stem))

            # SQLITE commit (perform the actions) and close connection 
            con.commit()
            con.close()
            logger.info(f"Closed Connection with {LOG_DB}")

            # Log
            logger.info(f"PRODUCED path={out_path} n={written} | row added to log tables stem={stem}")
    except Exception:
        # If rename or cleanup fails, log it and leave temp file for inspection
        logger.exception("Error finalizing output file; temporary file left for inspection.")
        raise

    return 0

if __name__=='__main__':
    main()

