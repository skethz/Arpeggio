#!/usr/bin/env bash
# Rebuild the unchanged kernel sources for the RTX 5090 (sm_120) with the venv's nvcc wheel (same as build_kernel.sh,
# different -arch); the AHC kernel with -fmad=false as for ahc_v1.cubin.
set -euo pipefail
A=<SCRATCH>/ap_ber_20261024
NV=$(find $A/venv/lib/python3.12/site-packages/nvidia -name nvcc -type f | head -1)
echo "nvcc: $NV"; $NV --version | tail -2
cd $A/build
$NV -cubin -arch=sm_120 -O3 -std=c++17 -lineinfo -Xptxas -v -o ane_v2_sm120.cubin $A/code_mimo/src/ane_kernel.cu 2> ane_v2_sm120.cubin.ptxas.log
$NV -cubin -arch=sm_120 -O3 -std=c++17 -lineinfo -Xptxas -v -fmad=false -o ahc_v1_sm120.cubin $A/code_mimo/src/ahc_kernel.cu 2> ahc_v1_sm120.cubin.ptxas.log
$NV -cubin -arch=sm_120 -O3 -std=c++17 -lineinfo -Xptxas -v -o pimi_v1_sm120.cubin $A/code_mimo/src/pimi_kernel.cu 2> pimi_v1_sm120.cubin.ptxas.log
sha256sum $A/code_mimo/src/ane_kernel.cu $A/code_mimo/src/ahc_kernel.cu $A/code_mimo/src/pimi_kernel.cu *.cubin | tee build_sm120.sha256
grep -h -E "spill" *.ptxas.log | sort | uniq -c | head
