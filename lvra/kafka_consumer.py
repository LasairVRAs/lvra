import json
from lasair import lasair_consumer
import yaml
import logging
from pathlib import Path
from datetime import datetime
import os

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s")


# Get the "public settings" from the environment or grab the default. 
env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    settings_path = Path(env_settings)
else:                                            # or go to default file
    settings_path = Path(__file__).resolve().parent.parent / "data" / "public_settings.yaml"


with settings_path.open("r") as settings:
    config = yaml.safe_load(settings)
    kafka_server = config['kafka_server']        # URL of the server
    my_topic = config['my_topic']                # topic associated with filter
    group_id = config['group_id']                # id used to keep your "place" in queue
    json_data_dir = Path(config['json_data_dir'])# output directory 

json_data_dir.mkdir(parents=True, exist_ok=True)

def main():
    consumer = lasair_consumer(kafka_server, 
                               group_id, 
                               my_topic)

    # make a timestamped file for this poll/run
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = json_data_dir / f"{ts}.json" # with_suffix below REPLACES the .json
    tmp_path = out_path.with_suffix(".jsn.tmp")  # <-- temporary while writing


    written = 0
    # open file once and stream JSON objects into an array
    f = tmp_path.open("w", encoding="utf-8")
    try:
        f.write("[\n")
        n = 0
        while n < 4000:
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

            _id = result.get('diaObjectId', 'no-id')
            logger.info(f'Got data for: {_id}')

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
            logger.info("No messages received — no file written.")
        else:
            # Atomically replace any existing final file with the tmp file
            os.replace(str(tmp_path), str(out_path))
            logger.info(f"Wrote {written} messages to {out_path}")
    except Exception:
        # If rename or cleanup fails, log it and leave temp file for inspection
        logger.exception("Error finalizing output file; temporary file left for inspection.")
        raise

    return 0

if __name__=='__main__':
    main()

