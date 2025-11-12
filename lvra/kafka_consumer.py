import json
from lasair import lasair_consumer
import yaml
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s")

settings_path = Path(__file__).resolve().parent.parent / "data" / "public_settings.yaml"
with settings_path.open("r") as settings:
    config = yaml.safe_load(settings)
    kafka_server = config['kafka_server']
    my_topic = config['my_topic']
    group_id = config['group_id']
    json_data_dir = Path(config['json_data_dir'])
json_data_dir.mkdir(parents=True, exist_ok=True)

def main():
    consumer = lasair_consumer(kafka_server, group_id, my_topic)

    # make a timestamped file for this poll/run
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = json_data_dir / f"{ts}.json"

    written = 0
    # open file once and stream JSON objects into an array
    f = out_path.open("w", encoding="utf-8")
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

    # if nothing was written, remove the empty array file
    if written == 0 and out_path.exists():
        out_path.unlink()
        logger.info("No messages received — no file written.")
    else:
        logger.info(f"Wrote {written} messages to {out_path}")

    return 0

if __name__=='__main__':
    main()

