#!/bin/bash
# Assemble flow v2 on an ASIC server from the unchanged kit/init prefix of flow/pnr/pnr.tcl plus the v2 body.
set -e
A=<SCRATCH>/antiphase_asic_20261017; F=$A/flow_v2_20261024
mkdir -p $F/maps
n=$(grep -n '^globalNetConnect VSS -type tielo -all' $A/flow/pnr/pnr.tcl | head -1 | cut -d: -f1)
head -n $n $A/flow/pnr/pnr.tcl | sed 's#^set ::env(PNR_SDC) \$SYN/out/final.sdc#set ::env(PNR_SDC) $SYN/out/final.sdc\nif {[info exists ::env(PNR_SDC_OVERRIDE)]} {set ::env(PNR_SDC) $::env(PNR_SDC_OVERRIDE)}#' > $F/pnr_v2.tcl
cat $F/pnr_v2_body.tcl >> $F/pnr_v2.tcl
C=$A/common_connectivity_AHC_D32_TT_20261018T023252Z
cp $C/tap_map_private.tcl $C/filler_map_private.tcl $F/maps/
cp $C/layer_map_private.tcl $F/maps/layer_map_private.tcl
echo "set macro_pin_layer <KIT_MACRO_PIN_LAYER>" >> $F/maps/layer_map_private.tcl
site=$(grep -o -E 'floorPlan -site [^ ]+' $A/flow/pnr/pnr.tcl | head -1 | awk '{print $3}')
echo "set site_name $site" >> $F/maps/layer_map_private.tcl
grep -c PNR_SDC_OVERRIDE $F/pnr_v2.tcl; wc -l $F/pnr_v2.tcl; echo assembled
