#!/usr/bin/bash

# SPECIFIC ENVIRONMENTS (HERE REMOTE)
export PYTHONPATH=/home/lasair/code/lvra/
CODEBASE=/home/lasair/code/lvra/lvra/pypeline
PYTHON=/home/lasair/anaconda3/envs/vra/bin/python
LOGDIR=/home/lasair/data/vra_data/logs
JSONDIR=/home/lasair/data/vra_data/JSON

# EVERYTHING BELOW CAN BE COPY PASTED BETWEEN LOCAL AND REMOTE

CONSUMER_LOG=$LOGDIR/lvra_kafka_consumer.log
FEATURE_LOG=$LOGDIR/feature_rb_v1.log
#SAFETY_SEC=120

# 1. If any .jsn.tmp exist, exit (consumer still running)
if ls "$JSONDIR"/*.jsn.tmp 1> /dev/null 2>&1; then
  echo "Consumer still running; exit" >> $FEATURE_LOG
  exit 0
fi

# 2. pick recent produced entries (oldest-first) and filter out already processed
mapfile -t produced_paths < <(grep 'PRODUCED' "$CONSUMER_LOG" | tail -n 50 | awk -F'path=' '{print $2}' | awk '{print $1}')
for path in "${produced_paths[@]}"; do
  #echo $path
  # check safety window using file timestamp or parse timestamp from the PRODUCED line
  #ts=$(grep "path=${path}" "$CONSUMER_LOG" | tail -n 1 | awk '{print $1 " " $2}')  # crude
  #if [ "$(date -d "$ts" +%s)" -ge $(( $(date +%s) - SAFETY_SEC )) ]; then
     # too new, skip this one
  #   continue
  #fi

  # skip if already processed successfully
  if grep -q "SUCCESS feature=rb_v1 inpath=${path}" "$FEATURE_LOG"; then
     #echo $path found so already don
     continue
  fi
  
  #echo echo!
  # call python worker on this file; capture its stdout/stderr
  $PYTHON $CODEBASE/rb_feature_maker.py "$path" >> $LOGDIR/lvra_rb_feature_maker_error.log 2>&1
done



 
 