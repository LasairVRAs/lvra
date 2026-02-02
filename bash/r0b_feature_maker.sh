#!/usr/bin/bash

# SPECIFIC ENVIRONMENTS (HERE REMOTE)
export PYTHONPATH=/home/lasair/code/lvra/
CODEBASE=/home/lasair/code/lvra/lvra/pypeline
PYTHON=/home/lasair/anaconda3/envs/lvra/bin/python
LOGDIR=/home/lasair/data/lvra/logs

DATE=$(date +"%Y%m%d")                                                          
YEAR=$(date +"%Y")

$PYTHON $CODEBASE/r0b_feature_maker.py  >> $LOGDIR/$YEAR/$DATE/r0b_feature_maker_error.log  2>&1



 
 
