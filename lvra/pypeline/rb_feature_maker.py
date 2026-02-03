import logging
from pathlib import Path
import os
from lvra.utils.features import FeaturesRealBogus
import sys
import yaml

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s")

# #### Get our INPUT_PATH ####
if len(sys.argv) < 2:
    logger.error("You must provide an input JSON path.")
    sys.exit(1)

INPUT_PATH = Path(sys.argv[1])
# #### Derive OUTPUT_PATH ####
# Example:
#   INPUT:  data/lvra/JSON/20251204_100000.json
#   OUTPUT: data/lvra/csv/20251204_100000.rb_v1.csv
JSON_DIR_NAME = "JSON"
CSV_DIR_NAME = "csv"
# TODO: should NOT be hard coded
FEATURE_SUFFIX = "rb_v1"  # becomes myfile.rb_v1.csv 

# Get the "public settings" from the environment or grab the default. 
env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    settings_path = Path(env_settings)
else:                                            # or go to default file
    settings_path = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"

with settings_path.open("r") as settings:
    config = yaml.safe_load(settings)
    ENDPOINT= config['endpoint']                # url endpoint Lasair


try:
    # TODO: this will fail when restructure into nested riectory structure
    # JSON -> year -> day. Also not sure what this check actually does. 
    parent = INPUT_PATH.parent
    if parent.name != JSON_DIR_NAME:
        # still try to replace, but warn
        logger.warning(f"Expected parent dir '{JSON_DIR_NAME}', got '{parent.name}'. Input was {INPUT_PATH}. Attempting replacement.")

    # Replace JSON/ → csv/
    # TODO: when directory structure has changed to ndexted year/day his will need
    # to be updated as well. (But the nested strucgture will be the same under CSV)
    OUTPUT_DIR = parent.parent / CSV_DIR_NAME
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stem = INPUT_PATH.stem      # "20251204_100000"
    OUTPUT_PATH = OUTPUT_DIR / f"{stem}_{FEATURE_SUFFIX}.csv"

except Exception as e:
    logger.error(f"Could not determine OUTPUT_PATH: {e}")
    sys.exit(1)

def main():
    
    #TODO: add the OUTPUT_PATH to SQLite feature tracking table
    # TODO: add also the stem used as primary key for SQLite
    logger.info(f"START feature=rb_v1 inpath={INPUT_PATH} outpath={OUTPUT_PATH}") 
    try:
        _df = FeaturesRealBogus.from_json(INPUT_PATH)
        # TODO: if Lasair provides an option to return the whole alert
        # then instead of an object hat has hard coded columns, I can have a separate
        # config file for each model that srates which columns are needed, and then
        # I don't need a new features object, I can just real the json with pandas
        # and do column selection. 
        features_df = FeaturesRealBogus.add_diasource_features(df=_df, endpoint=ENDPOINT)

        # not writing a temp file for atomicity because
        # it's just one step, either it writes out or it doesn't
        # if we start appending to that file and we risk incomplete writes
        # then we can revisit the idea of having .tmp suffixes. 
        features_df.to_csv(OUTPUT_PATH, index=False)

        logger.info(f"SUCCESS feature=rb_v1 inpath={INPUT_PATH} outpath={OUTPUT_PATH}")
        # TODO: ammend log feature version, stem and say ti's in SQLite table 
        # TODO: add also the stem used as primary key for SQLite
        return 0

    except FileNotFoundError:
        logger.error(f"FAIL feature=rb_v1 inpath={INPUT_PATH} reason=FileNotFound")
        # TODO: record in SQLite with specific error code (e.g. 2) ? 
        return 1
    except Exception as e:
        logger.error(f"FAIL feature=rb_v1 inpath={INPUT_PATH} reason={e}")
        # TODO: record in sqlite with error code 99 (generic error code)
        return 1


if __name__ == "__main__":
    sys.exit(main()) # exits with the code 0 or 1 dependng on if main succeeds
