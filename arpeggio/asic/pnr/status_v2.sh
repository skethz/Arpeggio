#!/bin/bash
# status_v2.sh <run dir>: public-only status of one flow-v2 run.
O=$1; cd $O 2>/dev/null || { echo "missing $O"; exit 0; }
echo "run $(basename $O): guard=$(cat guard_public.json 2>/dev/null)"
for f in $(ls -tr *_status.txt 2>/dev/null); do echo -n "${f%_status.txt}=$(cat $f) "; done; echo
for f in *_public.txt; do [ -f "$f" ] && echo "$f: $(cat $f)"; done
grep -h -E '^(FLOW_V2_DONE|FLOW_V2_STAGE_FAILED)' stdout.log 2>/dev/null | tail -2
for f in *error_private.txt; do [ -f "$f" ] && { echo "ERR $f:"; head -c 700 "$f" | sed -E 's/<KIT_CELL_PREFIX>[A-Za-z0-9_]+/<CELL>/g; s/<KIT_LIB_PREFIX>[A-Za-z0-9_]+/<LIB>/g'; echo; }; done
