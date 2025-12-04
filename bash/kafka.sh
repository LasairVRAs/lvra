#!/usr/bin/bash
export PYTHONPATH=/home/lasair/code/lvra/
CODEBASE=/home/lasair/code/lvra/lvra/pypeline
PYTHON=/home/lasair/anaconda3/envs/vra/bin/python
LOGDIR=/home/lasair/data/vra_data/logs

$PYTHON $CODEBASE/kafka_consumer.py >> $LOGDIR/lvra_kafka_error.log 2>&1


