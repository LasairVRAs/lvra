#!/usr/bin/env bash
set -euo pipefail

# SPECIFIC ENVIRONMENTS (HERE REMOTE)
export PYTHONPATH=/home/lasair/code/lvra/
CODEBASE=/home/lasair/code/lvra/lvra/pypeline
PYTHON=/home/lasair/anaconda3/envs/lvra/bin/python
LOGDIR=/home/lasair/data/vra_data/logs
CSVDIR=/home/lasair/data/vra_data/csv
export LVRA_SETTINGS=/home/lasair/code/lvra/data/public_settings.yaml

ANNOT_LOG=$LOGDIR/lvra_annotators.log


# 0. If any .csv.tmp exist, consumer/producer may be running -> exit
if ls "$CSVDIR"/*.csv.tmp 1> /dev/null 2>&1; then
  echo "$(date -Is) Consumer/producer still running; exit" >> $ANNOT_LOG
  exit 0
fi

# 1. list recent csv files (oldest first) and filter out already processed
#    you can adjust tail -n 200 window if you want
mapfile -t produced_paths < <(ls -1t "$CSVDIR"/*.csv 2>/dev/null | tail -n 200 | tac)

# For each csv file, check if a SUCCESS line is already in the annotator log, else run annotator
for path in "${produced_paths[@]}"; do
  fname=$(basename "$path")
  # skip if already annotated successfully for this file
  if grep -F "inpath=${fname}" "$ANNOT_LOG" 2>/dev/null | grep -Fq "SUCCESS annotate"; then
    echo "$fname already annotated successfully; skip" 
    continue
  fi
  #if grep -F "SUCCESS annotate" "$ANNOT_LOG" 2>/dev/null | grep -F "inpath=${fname}" >/dev/null 2>&1; then
  #  # already succeeded
  #  continue
  #fi


  # call the annotator worker; capture stdout/stderr to a worker log
  # pass annotator name and model name; adjust MODEL_NAME as needed
  # e.g. ANNOT_NAME can be 'vra_rb_v1' and MODEL_NAME 'vra_rb_v1.joblib' (without suffix)
  # MODEL_NAME="009_rbscore_LR0p1_MaxI30_RS42_SSnsr_sampling"
  MODEL_NAME="005_rbscore_LR0p1_MaxI30_RS42_SSnsr_sampling.joblib"
  ANNOT_NAME="vra_rb_v2"

  # IF WANT DEBUG MODE WHERE DON'T DO API CALL CAN SEE THE PYTHON LIBRARIES REQUIREMENT VS LOADED                                        
  # ADD --debug AFTER "$fname" 
  "$PYTHON" "$CODEBASE/annotate.py" "$ANNOT_NAME" "$MODEL_NAME" "$fname" --debug >> "$ANNOT_LOG" 2>&1 || {
    echo "$(date -Is) Exited with non-zero, Python code must have returned an error for $fname" >> "$ANNOT_LOG"
    # continue to next file (do not exit whole loop)
    continue
  }

done
