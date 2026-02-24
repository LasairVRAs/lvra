#!/usr/bin/bash

# ############ DESCRIPTION ########## #
# This script calls all the other LVRA related scripts: the consumer
# feature makers, predictors and annotators. 
# This is THE SCRIPT CALLED BY CRON. It staggers the other calls
# and ensures processes don't get run twice if the previous one is still running.

# One script to rule them all, 
# One script to find them,
# One script to bring them all,
# and in the darkness run them.

# ############# SETUP ############## #

# Environment
export PYTHONPATH=/home/lasair/code/lvra/
CODEBASE=/home/lasair/code/lvra/lvra/pypeline
PYTHON=/home/lasair/anaconda3/envs/lvra/bin/python
LOGBASE=/home/lasair/data/lvra/logs
LOCKBASE=/home/lasair/data/lvra/locks
BASHBASE=/home/lasair/code/lvra/bash
export LVRA_SETTINGS=/home/lasair/code/lvra/data/public_settings.yaml

### Location of my bash scripts
KAFKA="$BASHBASE/kafka.sh"
R0BFEATURES="$BASHBASE/r0b_feature_maker.sh"
PREDICT="$BASHBASE/r0b_predict.sh"
ANNOT="$BASHBASE/r0b_annotator.sh"

### Set up Logging
DATE=$(date +"%Y%m%d")
YEAR=$(date +"%Y")

LOGDIR="$LOGBASE/$YEAR/$DATE"

if [ ! -d "$LOGDIR" ]; then
  echo "$LOGDIR does not exist. Creating."
  mkdir -p $LOGDIR
fi

LOGFILE=$LOGDIR/bigbashboy.log
touch "$LOGFILE"


# ############  START PIPELINE ############### #
echo "$(date -Iseconds) [LVRA PIPELINE] ------  INIT ------ " >> $LOGFILE


### Check the bash scripts exist
if [ ! -f "$KAFKA" ]; then
    echo "$(date -Iseconds) [LVRA PIPELINE ERR] Kafka script not found at $KAFKA. Exiting." >> $LOGFILE
    exit 1
fi
if [ ! -f "$R0BFEATURES" ]; then
    echo "$(date -Iseconds) [LVRA PIPELINE ERR] r0b Features script not found at $R0BFEATURES. Exiting." >> $LOGFILE
    exit 1
fi
if [ ! -f "$PREDICT" ]; then
    echo "$(date -Iseconds) [LVRA PIPELINE ERR] Predict script not found at $PREDICT. Exiting." >> $LOGFILE
    exit 1
fi
if [ ! -f "$ANNOT" ]; then
    echo "$(date -Iseconds) [LVRA PIPELINE ERR] Annotator script not found at $ANNOT. Exiting." >> $LOGFILE
    exit 1
fi

echo "$(date -Iseconds) [LVRA PIPELINE] +++ All Scripts Found +++ " >> $LOGFILE
#### 

# ------ KAFKA CONSUMER ------- #
#  (fd 9)
exec 9>"$LOCKBASE/consumer.lock"
if ! flock -n 9 ; then
  echo "$(date -Iseconds) [LVRA PIPELINE] ooo SKIP consumer: lock held" >> "$LOGFILE"
else
  echo "$(date -Iseconds) [LVRA PIPELINE] +++ START consumer" >> "$LOGFILE"

  "$KAFKA" # error already redirected within that script so should be okay?

  rc=$?
  if [ $rc -eq 0 ]; then
    echo "$(date -Iseconds) [LVRA PIPELINE] +++ DONE consumer" >> "$LOGFILE"
  else
    echo "$(date -Iseconds) [LVRA PIPELINE] xxx FAIL consumer: exit $rc" >> "$LOGFILE"
  fi
  flock -u 9
fi
exec 9>&- # close fd 9

# .........  SLEEP ......... #
echo "$(date -Iseconds) [LVRA PIPELINE] zzzzzz Sleep 15 zzzzzzz ">> "$LOGFILE"
sleep 15

# ------ r0b FEATURE MAKING ------- #
#  (fd 10)
exec 10>"$LOCKBASE/r0bfeatures.lock"
if ! flock -n 10 ; then
  echo "$(date -Iseconds) [LVRA PIPELINE] ooo SKIP r0b features: lock held" >> "$LOGFILE"
else
  echo "$(date -Iseconds) [LVRA PIPELINE] +++ START r0b features" >> "$LOGFILE"

  "$R0BFEATURES" 

  rc=$?
  if [ $rc -eq 0 ]; then
    echo "$(date -Iseconds) [LVRA PIPELINE] +++ DONE r0b features" >> "$LOGFILE"
  else
    echo "$(date -Iseconds) [LVRA PIPELINE] xxx FAIL r0b features: exit $rc" >> "$LOGFILE"
  fi
  flock -u 10
fi
exec 10>&-

# .........  SLEEP ......... #
echo "$(date -Iseconds) [LVRA PIPELINE] zzzzzz Sleep 20 zzzzzzz ">> "$LOGFILE"
sleep 20

# ------ PREDICTIONS ------- #
# (fd 11)
exec 11>"$LOCKBASE/predict.lock"
if ! flock -n 11 ; then
  echo "$(date -Iseconds) [LVRA PIPELINE] ooo SKIP predict: lock held" >> "$LOGFILE"
else
  echo "$(date -Iseconds) [LVRA PIPELINE] +++ START predict " >> "$LOGFILE"

  "$PREDICT" 

  rc=$?
  if [ $rc -eq 0 ]; then
    echo "$(date -Iseconds) [LVRA PIPELINE] +++ DONE predict " >> "$LOGFILE"
  else
    echo "$(date -Iseconds) [LVRA PIPELINE] xxx FAIL predict: exit $rc" >> "$LOGFILE"
  fi
  flock -u 11
fi
exec 11>&-

# .........  SLEEP ......... #
echo "$(date -Iseconds) [LVRA PIPELINE] zzzzzz Sleep 10 zzzzzzz ">> "$LOGFILE"
sleep 10

# ------ ANNOTATIONS ------- #
# (fd 12)
exec 12>"$LOCKBASE/annotate.lock"
if ! flock -n 12 ; then
  echo "$(date -Iseconds) [LVRA PIPELINE] ooo SKIP annotate: lock held" >> "$LOGFILE"
else
  echo "$(date -Iseconds) [LVRA PIPELINE] +++ START annotate " >> "$LOGFILE"

  "$ANNOT" 

  rc=$?
  if [ $rc -eq 0 ]; then
    echo "$(date -Iseconds) [LVRA PIPELINE] +++ DONE annotate " >> "$LOGFILE"
  else
    echo "$(date -Iseconds) [LVRA PIPELINE] xxx FAIL annotate: exit $rc" >> "$LOGFILE"
  fi
  flock -u 12
fi
exec 12>&-

# ------ EXIT NICELY ------- #
echo "$(date -Iseconds) [LVRA PIPELINE] ------  DONE ------ " >> "$LOGFILE"
exit 0

