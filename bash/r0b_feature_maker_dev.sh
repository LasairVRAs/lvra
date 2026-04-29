#!/usr/bin/bash

# SPECIFIC ENVIRONMENTS (HERE REMOTE)
export PYTHONPATH=/home/lasair/code/lvra/
CODEBASE=/home/lasair/code/lvra/lvra/pypeline
PYTHON=/home/lasair/anaconda3/envs/lvra/bin/python
LOGBASE=/home/lasair/data/lvra_dev/logs

DATE=$(date +"%Y%m%d")                                                          
YEAR=$(date +"%Y")

LOGDIR=$LOGBASE/$YEAR/$DATE
ERR_LOG_NAME=$LOGDIR/r0b_feature_maker_error.log

if [ ! -d "$LOGDIR" ]; then
  echo "$LOGDIR does not exist. Creating."
  mkdir -p $LOGDIR
fi

if [ ! -f "$ERR_LOG_NAME" ]; then
  echo "$ERR_LOG_NAME does not exist. Creating."
  touch $ERR_LOG_NAME
fi

$PYTHON $CODEBASE/r0b_feature_maker.py  >> $ERR_LOG_NAME  2>&1



 
 
