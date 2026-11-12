#!/bin/bash
# A5.11 synthesis of the first-accept engine, same settings as v14 (PROTOCOL_A511 §2)
export HOME=<SCRATCH>/antiphase_asic_20261017/home XDG_CONFIG_HOME=<SCRATCH>/antiphase_asic_20261017/home/.config XDG_CACHE_HOME=<SCRATCH>/antiphase_asic_20261017/home/.cache
export SYN_TOP=ape_engine SYN_FILES="<SCRATCH>/antiphase_asic_20261017/ape/rtl_srv/ape_mem_gf22.sv <SCRATCH>/antiphase_asic_20261017/ape/rtl/ape_engine_fa.sv" SYN_DEFINES="" SYN_EFFORT=medium
d=$1; sl=$2
export SYN_PARAMS="D=$d A=4 SEEDL=$sl" SYN_MACROS="$(cat <SCRATCH>/antiphase_asic_20261017/flow_v2_20261024/macros_ape_d$d.txt)"
echo "$(date -u +%FT%TZ) start syn fa_d${d}_p1000" >> <SCRATCH>/antiphase_asic_20261017/fa_a511/RUNLOG.txt
nice -n 5 <SCRATCH>/antiphase_asic_20261017/flow/run_syn.sh <SCRATCH>/antiphase_asic_20261017/fa_a511/syn/fa_d${d}_p1000 1000 6
echo "$(date -u +%FT%TZ) end syn fa_d${d}_p1000 $(tail -1 <SCRATCH>/antiphase_asic_20261017/fa_a511/syn/fa_d${d}_p1000/time.log)" >> <SCRATCH>/antiphase_asic_20261017/fa_a511/RUNLOG.txt
