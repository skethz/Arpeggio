#!/usr/bin/env python3
"""A5.5 worker. Runs src/runner.py unchanged and adds the method names of arpx55.py.
Each batch's flip counters go into that batch's saved info. GPU memory is capped so
a shared GPU keeps room for other jobs."""
import os, runpy, torch, arpx, arpx55
torch.cuda.set_per_process_memory_fraction(float(os.environ.get('A55_MEM_FRAC', '0.20')), 0)
_orig, _det, _sink = arpx.mdi_solver_for, arpx.detect, {}


def mdi_solver_for(method, shape, gs, ctx):
    r = arpx55.solver_for(method, shape, gs, ctx, _sink)
    return r if r is not None else _orig(method, shape, gs, ctx)


def detect(method, b, shape, gs, ctx, z=None, extra=None):
    _sink.clear()
    lh, dg, info = _det(method, b, shape, gs, ctx, z=z, extra=extra)
    if 'cnt' in _sink:
        info['count'] = {str(k): v for k, v in _sink['cnt'].items()}
    return lh, dg, info


arpx.mdi_solver_for, arpx.detect = mdi_solver_for, detect
if __name__ == '__main__':
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runner.py'), run_name='__main__')
