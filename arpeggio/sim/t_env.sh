#!/usr/bin/env bash
source <SCRATCH>/ap_ber_20261024/env_ap.sh
python -c "import torch; print(torch.cuda.device_count(), torch.cuda.get_device_name(0)); import mimo, anefx, ahcfx, pimi, tree, mdi_solvers; print('ok')"
nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv | grep 0f7cbc13 || echo none_on_gpu7
