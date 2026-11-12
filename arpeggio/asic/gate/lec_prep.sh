#!/bin/bash
# lec_prep.sh <eng d32|d64> : prepares lec/<eng>_{rtl_syn,syn_routed} work dirs (copies of the verified inputs only)
set -eu
G=$(cd "$(dirname "$0")/.." && pwd); A=<SCRATCH>/antiphase_asic_20261017; F=$A/flow_v2_20261024
E=$1
case $E in
  d32) SYN=v14_d32_p1000; RUN=ape_d32_p1150_r4; TOP=ape_engine_D32_A4_SEEDL1;;
  d64) SYN=v14_d64_p1000; RUN=ape_d64_r4; TOP=ape_engine_D64_A4_SEEDL2;;
  d128) SYN=v14_d128_p1000; RUN=ape_d128_p1050_r4; TOP=ape_engine_D128_A4_SEEDL4;;
esac
S=$G/inputs/ro_src/syn/$SYN
W=$G/lec/${E}_rtl_syn; mkdir -p $W
cp -r $S/fv $W/fv
# server-only library block: from 'add_search_path . ' through the end of the read_library continuation lines
awk '/^add_search_path \. /{f=1} f{print} f&&/^read_library/{r=1} r&&!/\\$/{exit}' $S/fv/$TOP/rtl_to_fv_map.do > $W/libs_private.do
echo "TOP=$TOP SYN=$SYN RUN=$RUN" > $W/info.txt
W2=$G/lec/${E}_syn_routed; mkdir -p $W2
cp $W/libs_private.do $W2/libs_private.do
# the macro black-box declaration of Genus' dofile (same line, server-only names)
grep '^add_notranslate_modules' $S/fv/$TOP/rtl_to_fv_map.do >> $W2/libs_private.do
echo "TOP=$TOP SYN=$SYN RUN=$RUN" > $W2/info.txt
sha256sum $A/ape/syn/$SYN/out/netlist.v $F/$RUN/final_netlist_private.v $S/out/netlist.v > $W2/INPUTS.sha256
wc -l $W/libs_private.do $W2/libs_private.do | awk '{print $1}' | tr '\n' ' '; echo
