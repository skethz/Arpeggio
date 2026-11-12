#!/usr/bin/env bash
# Amendment 7 launcher: one trace_a56.py worker per hostB GPU (UUID-checked, idle required), nice 10, 2 threads, 20% memory.
# Usage: launch_a57.sh PLAN ROOT TAG   (run from <SCRATCH>/ap_ber_20261024)
set -u
A=<SCRATCH>/ap_ber_20261024; PL=$1; ROOT=$2; TAG=$3
UU=(<GPU_UUID> <GPU_UUID> <GPU_UUID> <GPU_UUID>)
mkdir -p $A/logs/a57
for i in 0 1 2 3; do
  u=${UU[$i]}
  used=$(nvidia-smi --id=$u --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | grep -c "$u")
  if [ "$apps" != 0 ] || [ "$used" -gt 1000 ]; then echo "skip GPU$i $u: in use ($apps apps, $used MiB)"; continue; fi
  ( export MIMO_GPU_UUID=$u
    export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$u
    export XDG_CACHE_HOME="$A/cache/xdg" XDG_CONFIG_HOME="$A/cache/config" XDG_STATE_HOME="$A/cache/state" XDG_DATA_HOME="$A/cache/data"
    export PIP_CACHE_DIR="$A/cache/pip" MPLCONFIGDIR="$A/cache/mpl" CUDA_CACHE_PATH="$A/cache/nv" TRITON_CACHE_DIR="$A/cache/triton"
    export TORCH_HOME="$A/cache/torch" NUMBA_CACHE_DIR="$A/cache/numba" PYTHONPYCACHEPREFIX="$A/cache/python"
    export TMPDIR="$A/tmp" TMP="$A/tmp" TEMP="$A/tmp" HISTFILE=/dev/null PYTHONDONTWRITEBYTECODE=1
    export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMBA_NUM_THREADS=2
    export PYTHONPATH="$A/src:$A/code_mimo/src"
    source "$A/venv/bin/activate"; cd "$A"
    setsid nohup nice -n 10 python -u src/trace_a56.py --plan $PL --root $ROOT --worker ${TAG}$i --threads 2 --mem 0.20 >> $A/logs/a57/worker_${TAG}$i.log 2>&1 & )
  echo "started ${TAG}$i on GPU$i $u"
  sleep 3
done
