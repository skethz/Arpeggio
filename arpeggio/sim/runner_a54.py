#!/usr/bin/env python3
"""A5.4 worker. Runs src/runner.py unchanged and adds one method name:
abl_anel_<Sk>_<Ns> = mdichord<Ns> with L = Sk * 2K rounds (same call, T 0.3, q 0.4; Sk = 128 is Chord (i)).
GPU memory is capped so a shared GPU keeps room for its other user."""
import os, runpy, torch, arpx
torch.cuda.set_per_process_memory_fraction(float(os.environ.get('A54_MEM_FRAC', '0.30')), 0)
_orig = arpx.mdi_solver_for


def mdi_solver_for(method, shape, gs, ctx):
    if method.startswith('abl_anel_'):
        Sk, Ns = (int(x) for x in method.split('_')[2:])
        MA = arpx.MA
        return (lambda I, na, K: arpx.mimo.chord(I, na, Sk * 2 * K, MA['t0'], MA['t1'], MA['q'], kappa=0.0, gen=gs,
                                                   phases=2 * K)), None, Ns
    return _orig(method, shape, gs, ctx)


arpx.mdi_solver_for = mdi_solver_for
if __name__ == '__main__':
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runner.py'), run_name='__main__')
