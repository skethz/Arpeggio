#!/usr/bin/env python3
"""A5.5 worker (exploratory; PROTOCOL_A55.md). Runs the frozen src/runner.py unchanged and adds the method names of apx55.py.
Each batch's flip counters go into that batch's saved info. apx.py, runner.py and mimo.py are not edited. GPU memory is capped so
a shared GPU keeps room for its other user."""
import os, runpy, torch, apx, apx55
torch.cuda.set_per_process_memory_fraction(float(os.environ.get('A55_MEM_FRAC', '0.20')), 0)
_orig, _det, _sink = apx.mdi_solver_for, apx.detect, {}


def mdi_solver_for(method, shape, gs, ctx):
    r = apx55.solver_for(method, shape, gs, ctx, _sink)
    return r if r is not None else _orig(method, shape, gs, ctx)


def detect(method, b, shape, gs, ctx, z=None, extra=None):
    _sink.clear()
    lh, dg, info = _det(method, b, shape, gs, ctx, z=z, extra=extra)
    if 'cnt' in _sink:
        info['count'] = {str(k): v for k, v in _sink['cnt'].items()}
    return lh, dg, info


apx.mdi_solver_for, apx.detect = mdi_solver_for, detect
if __name__ == '__main__':
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runner.py'), run_name='__main__')
