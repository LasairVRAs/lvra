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

#TODO: Major Logic change!
# currently the bash script reads the logs and calles this with a filename.json as an argument
# INPUT_PATH here. Instead what we can do is:
# 1. create sqlite connection
# 2. create an sqlite cursor 
# 3. find all stems (index primary ley) where r0b (column) != 1 (1=SUCCESS)
# SELECT stem from feature_making WHERE r0b != 1; 
# This will return either:
# a. NO stems because everything has been done and completed -> Exit
# b. One stem -> read file and do feature creation 
# c. SEVERAL stems if some json files weren't successfuly created features for
# -> TODO: THINK ABOUT HOW TO HANDLE THIS HERE
INPUT_PATH = Path(sys.argv[1])

# #### Derive OUTPUT_PATH ####
# Example:
#   INPUT:  data/lvra/JSON/20251204_100000.json
#   OUTPUT: data/lvra/csv/20251204_100000.rb_v1.csv
# TODO: don't hard code this here, use yaml file like in the consumer
JSON_DIR_NAME = "JSON"
CSV_DIR_NAME = "csv"
FEATURE_SUFFIX = "rb_v1"  # becomes myfile.rb_v1.csv

# Get the "public settings" from the environment or grab the default. 
env_settings = os.environ.get("LVRA_SETTINGS")
if env_settings:                                 # from environment variable
    settings_path = Path(env_settings)
else:                                            # or go to default file
    settings_path = Path(__file__).resolve().parent.parent.parent / "data" / "public_settings.yaml"

# TODO: make a set_up function that returns ENDPOINT, STEMS, sub_dir => return DICTIONARY NOT A TUPLE
# TODO: add the current_year and current_day and sub_dir vals fro consumer
# TODO: add the JSON and csv dir from yaml file like in consumer
# TODO: add a r0b_feature_version to the yaml file to put in FEATURE_SUFFIX 
with settings_path.open("r") as settings:
    config = yaml.safe_load(settings)
    ENDPOINT= config['endpoint']                # url endpoint Lasair


try:
    parent = INPUT_PATH.parent
    if parent.name != JSON_DIR_NAME:
        # still try to replace, but warn
        logger.warning(f"Expected parent dir '{JSON_DIR_NAME}', got '{parent.name}'. Input was {INPUT_PATH}. Attempting replacement.")

    # Replace JSON/ → csv/
    OUTPUT_DIR = parent.parent / CSV_DIR_NAME
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # TODO: this changes if we have more than one stem earlier 
    stem = INPUT_PATH.stem      # "20251204_100000"
    OUTPUT_PATH = OUTPUT_DIR / f"{stem}_{FEATURE_SUFFIX}.csv"

except Exception as e:
    logger.error(f"Could not determine OUTPUT_PATH: {e}")
    sys.exit(1)

def main():
    # TODO: this is NOT main - this is a function to create features for ONE of the json files
    # main should:
    # 0. read the yaml file
    # 1. create the database connection and find the file stems
    # 2. deal with the options a. . or .c (0, 1 or many stems found)
    # 3. call function to make the feature files (this curent logic below) 
    # MAIN input = yaml file name. Output = exit code
    logger.info(f"START feature=rb_v1 inpath={INPUT_PATH} outpath={OUTPUT_PATH}") 
    try:
        _df = FeaturesRealBogus.from_json(INPUT_PATH)
        features_df = FeaturesRealBogus.add_diasource_features(df=_df, endpoint=ENDPOINT)

        # not writing a temp file for atomicity because
        # it's just one step, either it writes out or it doesn't
        # if we start appending to that file and we risk incomplete writes
        # then we can revisit the idea of having .tmp suffixes. 
        features_df.to_csv(OUTPUT_PATH, index=False)

        logger.info(f"SUCCESS feature=rb_v1 inpath={INPUT_PATH} outpath={OUTPUT_PATH}")
        return 0

    except FileNotFoundError:
        logger.error(f"FAILfeature=rb_v1 inpath={INPUT_PATH} reason=FileNotFound")
        return 1
    except Exception as e:
        logger.error(f"FAIL feature=rb_v1 inpath={INPUT_PATH} reason={e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) # exits with the code 0 or 1 dependng on if main succeeds
