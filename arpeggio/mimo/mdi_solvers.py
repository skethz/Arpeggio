"""MDI-MIMO solvers for milestone C, all behind the same interface solver(I, na, K) -> candidate spins (n, na, 2K D),
and a timing/capture wrapper. Implementations:
- 'ahc_torch': Princeton's AHC-CIM in PyTorch (mimo.ahc, published settings);
- 'ane_torch': Anechoic-dDI in PyTorch (mimo.anechoic, tuned schedule, 2K phases);
- 'ahc_kernel': the AHC-CIM CUDA kernel (ahc_kernel.cu; bit-exact with ahcfx.ahc_od), start states drawn exactly
  as mimo.ahc draws them;
- 'ane_kernel': the Anechoic CUDA kernel (ane_kernel.cu; bit-exact with anefx.anechoic_fx), Philox seeds per call.
Timed(solver): every call synchronised before and after; accumulates the solver wall time; optionally keeps the
calls' inputs (I, na, K) for a solver-only replay."""
import time

import torch

import ahcfx
import anefx
import mimo

MDIANE = dict(Sk=128, t0=0.3, t1=0.3, q=0.4, kappa=0.0)                  # tuned on the tuning set (milestone B)
MDI = {('16x16', 16): dict(Rmax=3, S=8, guesses=('mmse', 'sic')),         # Singh et al. 2024 Table I
       ('32x32', 16): dict(Rmax=3, S=8, guesses=('mmse', 'sic')),
       ('64x64', 16): dict(Rmax=3, S=8, guesses=('mmse', 'sic')),
       ('32x32', 4): dict(Rmax=1, S=1, guesses=('mmse',))}                 # QPSK: DI-MIMO, one stage, MMSE guess


def make_solver(impl, gen, kern_ane=None, kern_ahc=None, seed0=0):
    calls = [0]
    if impl == 'ahc_torch':
        return lambda I, na, K: mimo.ahc(I, na, gen=gen)
    if impl == 'ane_torch':
        return lambda I, na, K: mimo.anechoic(I, na, MDIANE['Sk'] * 2 * K, MDIANE['t0'], MDIANE['t1'], MDIANE['q'],
                                              kappa=MDIANE['kappa'], gen=gen, phases=2 * K)
    if impl == 'ahc_kernel':
        def f(I, na, K):
            B, N = I['h0'].shape
            x0, e0 = ahcfx.start_state(B, na, N + 1, gen, I['h0'].device)
            return kern_ahc.ahc(I, x0, e0)[0].float()
        return f
    if impl == 'ane_kernel':
        def f(I, na, K):
            calls[0] += 1
            F = anefx.to_fixed(I, MDIANE['Sk'] * 2 * K, MDIANE['t0'], MDIANE['t1'], MDIANE['q'], MDIANE['kappa'])
            return kern_ane.anechoic(F, na, seed0 + 1000 * calls[0], P=2 * K, mode='chains')[0].float()
        return f
    raise ValueError(impl)


class Timed:
    def __init__(self, solver, capture=False):
        self.solver, self.capture, self.t, self.calls, self.kept = solver, capture, 0.0, 0, []

    def __call__(self, I, na, K):
        torch.cuda.synchronize(); t0 = time.time()
        out = self.solver(I, na, K)
        torch.cuda.synchronize(); self.t += time.time() - t0
        self.calls += 1
        if self.capture:
            self.kept.append(({k: v for k, v in I.items()}, na, K))
        return out


def detect(b, impl, Ns, cfg, solver, z=None):
    """MDI-MIMO with the given solver; cfg from MDI. Returns the decided levels and the anneal statistics."""
    st = {}
    lh = mimo.mdi(b, solver, Ns, cfg['Rmax'], cfg['S'], guesses=tuple(cfg['guesses']), z_mmse=z, stats=st)
    return lh, st
