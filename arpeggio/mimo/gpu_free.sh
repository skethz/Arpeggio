#!/usr/bin/env bash
# Exit 0 iff the GPU with this UUID has no compute process (checked right before use; the user's rule of 16 Oct).
[ -z "$(nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader | grep "$1")" ]
