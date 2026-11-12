#!/bin/bash
# usage: mine.sh <render root> [-k]. Lists this user's processes that carry R4_RENDER_TAG=<root> in their environment
# or run with a working directory under <root>; with -k, kills exactly those PIDs. Nothing else is touched.
ROOT=$1; KILL=${2:-}; ME=$(id -un)
for d in /proc/[0-9]*; do
  pid=${d#/proc/}
  [ "$pid" = "$$" ] && continue
  [ "$(stat -c %U $d 2>/dev/null)" = "$ME" ] || continue
  hit=0
  tr '\0' '\n' < $d/environ 2>/dev/null | grep -qx "R4_RENDER_TAG=$ROOT" && hit=1
  case "$(readlink $d/cwd 2>/dev/null)" in "$ROOT"|"$ROOT"/*) hit=1;; esac
  [ $hit = 1 ] || continue
  echo "MINE $pid $(cat $d/comm 2>/dev/null)"
  [ "$KILL" = "-k" ] && kill -9 "$pid" && echo "KILLED $pid"
done
echo MINE_SCAN_DONE
