#!/usr/bin/bash
export PYTHONPATH=/home/lasair/code/lvra/
CODEBASE=/home/lasair/code/lvra/lvra/pypeline
PYTHON=/home/lasair/anaconda3/envs/lvra/bin/python
LOGBASE=/home/lasair/data/lvra/logs
export LVRA_SETTINGS=/home/lasair/code/lvra/data/public_settings.yaml


DATE=$(date +"%Y%m%d")
YEAR=$(date +"%Y")

LOGDIR="$LOGBASE/$YEAR/$DATE"

if [ ! -d "$LOGDIR" ]; then
  echo "$LOGDIR does not exist. Creating."
  mkdir -p $LOGDIR
fi


$PYTHON $CODEBASE/kafka_consumer.py >> $LOGDIR/lvra_kafka_error.log 2>&1 

