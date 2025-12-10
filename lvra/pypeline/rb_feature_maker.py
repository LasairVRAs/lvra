import logging
from pathlib import Path
import os
from lvra.utils.features import FeaturesRealBogus
import sys

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
FEATURE_SUFFIX = "rb_v1"  # becomes myfile.rb_v1.csv

try:
    parent = INPUT_PATH.parent
    if parent.name != JSON_DIR_NAME:
        # still try to replace, but warn
        logger.warning(f"Expected parent dir '{JSON_DIR_NAME}', got '{parent.name}'. Input was {INPUT_PATH}. Attempting replacement.")

    # Replace JSON/ → csv/
    OUTPUT_DIR = parent.parent / CSV_DIR_NAME
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stem = INPUT_PATH.stem      # "20251204_100000"
    OUTPUT_PATH = OUTPUT_DIR / f"{stem}_{FEATURE_SUFFIX}.csv"

except Exception as e:
    logger.error(f"Could not determine OUTPUT_PATH: {e}")
    sys.exit(1)

def main():
    logger.info(f"START feature=rb_v1 inpath={INPUT_PATH} outpath={OUTPUT_PATH}") 
    try:
        features_df = (FeaturesRealBogus.from_json(INPUT_PATH
                                                   ).pipe(FeaturesRealBogus.add_diasource_features))

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
