#!/bin/bash
# launch.sh <out dir> <timeout_s> <rss_gib> <cpu list> -- cmd ...
# guard.py (flow v2) + taskset + bwrap (read-only root, <SCRATCH> writable, the accepted run dirs re-bound
# read-only), TMPDIR/XDG in the gate dir. Every start/end is appended to RUNLOG.txt.
G=$(cd "$(dirname "$0")/.." && pwd)
F=<SCRATCH>/antiphase_asic_20261017/flow_v2_20261024
O=$1; TMO=$2; CAP=$3; CPUL=$4; shift 5
mkdir -p $O $G/tmp $G/var_tmp $G/xdg/cache $G/xdg/config
RO=""
for r in ape_d32_p1150_r4 ape_d64_r4 ape_d128_p1050_r4 ape_d128_p1100_r4 ape_d128_p1150_r4 ape_d128_p1200_r4 pimi_hls_r4b; do [ -d $F/$r ] && RO="$RO --ro-bind $F/$r $F/$r"; done
for r in $G/inputs/ro_*; do [ -d $r ] && RO="$RO --ro-bind $r $r"; done
echo "$(date -u +%FT%TZ) start $O cpus=$CPUL host=$(hostname -s) :: $*" >> $G/RUNLOG.txt
env TMPDIR=$G/tmp XDG_CACHE_HOME=$G/xdg/cache XDG_CONFIG_HOME=$G/xdg/config \
  python3 $G/scripts/guard.py $O $TMO $CAP -- taskset -c $CPUL bwrap --die-with-parent --ro-bind / / --dev-bind /dev /dev \
  --bind <SCRATCH> <SCRATCH> $RO --bind $G/tmp /tmp --bind $G/var_tmp /var/tmp --chdir $O nice -n 5 "$@"
echo "$(date -u +%FT%TZ) end $O $(cat $O/guard_public.json)" >> $G/RUNLOG.txt
