#!/usr/bin/bash
export PYTHONPATH=/home/lasair/code/lvra/
CODEBASE=/home/lasair/code/lvra/lvra/pypeline
PYTHON=/home/lasair/anaconda3/envs/lvra/bin/python
LOGDIR=/home/lasair/data/vra_data/logs
export LVRA_SETTINGS=/home/lasair/code/lvra/data/public_settings.yaml


DATE=$(date +"%Y%m%d")
YEAR=$(date +"%Y")

$PYTHON $CODEBASE/kafka_consumer.py >> $LOGDIR/$YEAR/$DATE/lvra_kafka_error.log 2>&1 

