#!/usr/bin/env bash
# arpeggio_ber_20261024/a519z on hostA, A5.19: UNTIMED error counting only (no timing or energy is reported).
# Allowed: GPU0, GPU2, GPU3. Caller sets MIMO_GPU_UUID.
# Reuses the mimo_ising_20261016 venv read-only (torch 2.11.0+cu128, numpy 2.5.4, as hostB).
Z=<SCRATCH>/arpeggio_ber_20261024/a519z
case "$MIMO_GPU_UUID" in
  <GPU_UUID>|<GPU_UUID>|<GPU_UUID>) ;;
  *) echo "refusing: MIMO_GPU_UUID=$MIMO_GPU_UUID is not an allowed hostA GPU" >&2; return 1 2>/dev/null || exit 1 ;;
esac
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$MIMO_GPU_UUID
export XDG_CACHE_HOME="$Z/cache/xdg" XDG_CONFIG_HOME="$Z/cache/config" XDG_STATE_HOME="$Z/cache/state" XDG_DATA_HOME="$Z/cache/data"
export PIP_CACHE_DIR="$Z/cache/pip" MPLCONFIGDIR="$Z/cache/mpl" CUDA_CACHE_PATH="$Z/cache/nv" TRITON_CACHE_DIR="$Z/cache/triton"
export TORCH_HOME="$Z/cache/torch" NUMBA_CACHE_DIR="$Z/cache/numba" PYTHONPYCACHEPREFIX="$Z/cache/python"
export TMPDIR="$Z/tmp" TMP="$Z/tmp" TEMP="$Z/tmp" HISTFILE=/dev/null PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMBA_NUM_THREADS=2
export PYTHONPATH="$Z/src:$Z/code_mimo/src"
mkdir -p "$Z"/cache/{xdg,config,state,data,pip,mpl,nv,triton,torch,numba,python} "$Z"/{tmp,logs/a519,results/a519}
source <SCRATCH>/mimo_ising_20261016/venv/bin/activate
cd "$Z"
