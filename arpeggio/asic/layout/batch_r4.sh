#!/bin/bash
# usage: batch_r4.sh <root> <casefile> <cpu list> <display> <square px> <rules.json>; casefile lines: name|run dir|top
# Restores <run dir>/db/final.enc.dat read-only (the run dir is bound read-only inside bwrap) into <root>/<name>.
set -u
ROOT=$1; CASES=$2; CPUL=$3; DISP=$4; SQ=$5; RULES=$6
while IFS='|' read -r NAME RUN TOP; do
  [ -z "$NAME" ] && continue
  P=$ROOT/$NAME; mkdir -p $P/tmp $P/var_tmp $P/public
  AV=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
  echo "$(date -u +%FT%TZ) start $NAME cpus=$CPUL load=$(cut -d' ' -f1 /proc/loadavg) availKiB=$AV" >> $ROOT/batch.log
  if [ "$AV" -lt 100663296 ]; then echo "$(date -u +%FT%TZ) skip $NAME low memory" >> $ROOT/batch.log; continue; fi
  env PNR_OUT=$P PP_DB=$RUN/db/final.enc.dat PP_TOP=$TOP SQ=$SQ R4_RENDER_TAG=$ROOT \
    python3 $ROOT/guard.py $P 10800 64 -- taskset -c $CPUL bwrap --die-with-parent --ro-bind / / --dev-bind /dev /dev \
      --bind <SCRATCH> <SCRATCH> --ro-bind $RUN $RUN --bind $P/tmp /tmp --bind $P/var_tmp /var/tmp --chdir $P \
      nice -n 5 xvfb-run -n $DISP -s "-screen 0 2000x2000x24 -nolisten tcp" <TOOL_LAUNCHER> innovus -files $ROOT/render_r4.tcl -log $P/tool
  DONE=$(grep -c '^RENDER_R4_DONE' $P/stdout.log)
  echo "$(date -u +%FT%TZ) end $NAME $(cat $P/guard_public.json) done=$DONE" >> $ROOT/batch.log
  if [ "$DONE" -ge 1 ]; then
    R4_RENDER_TAG=$ROOT nice -n 5 taskset -c $CPUL python3 $ROOT/raster.py $P/insts_private.tsv $P/die_public.txt $RULES $P/public/$NAME 1600 >> $ROOT/batch.log 2>&1
    R4_RENDER_TAG=$ROOT nice -n 5 taskset -c $CPUL python3 $ROOT/png_public.py $P/routed_sq_raw.png $P/public/${NAME}_routed_public.png >> $ROOT/batch.log 2>&1
    cp $P/die_public.txt $P/public/${NAME}_die_public.txt
    cp $P/guard_public.json $P/public/${NAME}_guard_public.json
  fi
done < $CASES
echo "$(date -u +%FT%TZ) batch complete $(basename $CASES)" >> $ROOT/batch.log
