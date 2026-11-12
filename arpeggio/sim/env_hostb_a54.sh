#!/usr/bin/env bash
# ap_ber_20261024 on hostB: UNTIMED error counting only (no timing/energy from a 5090 is ever reported).
# A5.4: allowed GPUs GPU0 <GPU_UUID> and GPU1 <GPU_UUID> only (author, 4 Nov 2026). Caller sets MIMO_GPU_UUID.
A=<SCRATCH>/ap_ber_20261024
case "$MIMO_GPU_UUID" in
  <GPU_UUID>|<GPU_UUID>) ;;
  *) echo "refusing: MIMO_GPU_UUID=$MIMO_GPU_UUID is not an allowed hostB GPU" >&2; return 1 2>/dev/null || exit 1 ;;
esac
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$MIMO_GPU_UUID
export XDG_CACHE_HOME="$A/cache/xdg" XDG_CONFIG_HOME="$A/cache/config" XDG_STATE_HOME="$A/cache/state" XDG_DATA_HOME="$A/cache/data"
export PIP_CACHE_DIR="$A/cache/pip" MPLCONFIGDIR="$A/cache/mpl" CUDA_CACHE_PATH="$A/cache/nv" TRITON_CACHE_DIR="$A/cache/triton"
export TORCH_HOME="$A/cache/torch" NUMBA_CACHE_DIR="$A/cache/numba" PYTHONPYCACHEPREFIX="$A/cache/python"
export TMPDIR="$A/tmp" TMP="$A/tmp" TEMP="$A/tmp" HISTFILE=/dev/null PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMBA_NUM_THREADS=2
export PYTHONPATH="$A/src:$A/code_mimo/src"
export ANE_CUBIN=$A/build/ane_v2_sm120.cubin AHC_CUBIN=$A/build/ahc_v1_sm120.cubin PIMI_CUBIN=$A/build/pimi_v1_sm120.cubin
mkdir -p "$A"/cache/{xdg,config,state,data,pip,mpl,nv,triton,torch,numba,python} "$A"/{tmp,logs,results,build}
source "$A/venv/bin/activate"
cd "$A"
