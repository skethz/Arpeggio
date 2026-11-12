#!/usr/bin/env bash
# ap_ber_20261024/a514z on hostA, A5.14 overflow: UNTIMED error counting only (no timing or energy is reported from this run).
# Allowed: GPU5 only (author, 10 Nov 2026: "<instruction>"). Reuses the mimo_ising_20261016 venv read-only (torch 2.11.0+cu128, as hostB).
Z=<SCRATCH>/ap_ber_20261024/a514z
export MIMO_GPU_UUID=<GPU_UUID>
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$MIMO_GPU_UUID
export XDG_CACHE_HOME="$Z/cache/xdg" XDG_CONFIG_HOME="$Z/cache/config" XDG_STATE_HOME="$Z/cache/state" XDG_DATA_HOME="$Z/cache/data"
export PIP_CACHE_DIR="$Z/cache/pip" MPLCONFIGDIR="$Z/cache/mpl" CUDA_CACHE_PATH="$Z/cache/nv" TRITON_CACHE_DIR="$Z/cache/triton"
export TORCH_HOME="$Z/cache/torch" NUMBA_CACHE_DIR="$Z/cache/numba" PYTHONPYCACHEPREFIX="$Z/cache/python"
export TMPDIR="$Z/tmp" TMP="$Z/tmp" TEMP="$Z/tmp" HISTFILE=/dev/null PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMBA_NUM_THREADS=2
export PYTHONPATH="$Z/src:$Z/code_mimo/src"
mkdir -p "$Z"/cache/{xdg,config,state,data,pip,mpl,nv,triton,torch,numba,python} "$Z"/{tmp,logs,results/a514}
source <SCRATCH>/mimo_ising_20261016/venv/bin/activate
cd "$Z"
