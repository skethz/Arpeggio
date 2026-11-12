#!/usr/bin/env bash
# Build a kernel source to a cubin for the B200 (sm_100) with the CUDA 13.4 nvcc wheel of the project venv.
# Usage: build_kernel.sh SRC.cu OUT.cubin
set -euo pipefail
SRC=$(realpath "$1"); OUT=$(realpath -m "$2")
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1
NV=$(find $R/venv/lib/python3.12/site-packages/nvidia -name nvcc -type f | head -1)
mkdir -p $R/build
$NV -cubin -arch=sm_100 -O3 -std=c++17 -lineinfo -Xptxas -v ${NVFLAGS:-} -o "$OUT" "$SRC" 2> "$OUT.ptxas.log"   # NVFLAGS: e.g. -fmad=false
grep -E "registers|spill|Compiling entry" "$OUT.ptxas.log" | sed 's/^ptxas info    : //' | head -40
sha256sum "$SRC" "$OUT" > "$OUT.sha256"
