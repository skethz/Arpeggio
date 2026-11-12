#!/usr/bin/env bash
# Cache the authors' Fig. 6 instances and solved states (all panels and Eb/N0 points) from their Zenodo archives.
R=<SCRATCH>/mimo_ising_20261016; source $R/env.sh > /dev/null 2>&1; cd $R/src
Z=$R/baselines/pimi_zenodo/download_20261016_large; C=$R/results/pimi_their_instances
export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1
python pimi_zen.py $Z $C 16 16 0,5,10,15,20,25,30,35,40
python pimi_zen.py $Z $C 8 16 0,5,10,15,20,25,27,29,30,31,33,35,40
python pimi_zen.py $Z $C 16 4 0,5,6,8,10,12,14,15,16,18,20,25,30,35,40
python pimi_zen.py $Z $C 8 4 0,5,10,12,14,15,16,18,20,25,30,35,40
python pimi_zen.py $Z $C 16 64 0,5,10,15,20,25,30,35,40
python pimi_zen.py $Z $C 8 64 0,5,10,15,20,25,30,35,40
echo CACHE_DONE $(date '+%H:%M:%S %Z')
