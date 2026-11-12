"""Soft-output detectors shared by soft.py (coded BLER) and calib.py (LLR calibration on the tuning set).
detect_llr returns raw (uncalibrated, unclipped except for numerical guards) LLRs, positive = bit 1, dim-major with
the MSB first within each real dimension, and the hard decision. Methods:
  mmse      Gaussian max-log (no calibration: its LLRs are already calibrated, results/... calibration check)
  kbestK    K-best list + MMSE + single-bit-flip neighbours of the best (mimo.list_llr)
  aneNA     Anechoic (hard schedule) anneals' best states + MMSE + bit-flip neighbours (mimo.list_llr)
  saneNA    Anechoic's rule as an explorer, max-log over all visited states (mimo.anechoic_soft / trajectory_llr)
  cimNA / ahcNA  Princeton's solvers' anneals' best states + MMSE + bit-flip neighbours (mimo.list_llr)
  anedNA / ahcdNA / cimdNA  the same on Princeton's delta formulation (mimo.ising_delta, K = 1; Anechoic with phases)"""
import numpy as np
import torch

import mimo
import tree

BIG = 1e4


def detect_llr(b, method, gs, cfg):
    M = b['M']
    D = b['H'].shape[-1]
    z, Ai, el2 = mimo.mmse(b)
    lm = mimo.mmse_hard(b, z, Ai)
    if method == 'mmse':
        llr = mimo.mmse_soft_llr(b, z, Ai, el2)
        return llr, lm
    if method.startswith('kbest'):
        K = int(method[5:])
        lst, _ = tree.kbest(b['H'].double().cpu().numpy(), b['y'].double().cpu().numpy(),
                            np.array(mimo.PAM[M]['levels'], np.float64), K)
        cand = torch.tensor(lst, device=b['H'].device, dtype=torch.float32)
        l_hat, allc, d = mimo.select(b, cand, lm)
        return mimo.list_llr(b, allc, d, l_hat, clip=BIG), l_hat
    if method[3:4] == 'd':                                                 # delta formulation: aned / ahcd / cimd
        Id = mimo.ising_delta(b, z, K=1)
        na = int(method[4:])
        if method.startswith('aned'):
            an = cfg['aned']
            S_ = mimo.anechoic(Id, na, an['S'], an['t0'], an['t1'], an['q'], kappa=an.get('kappa', 0.0), lam=an.get('lam', 0.0),
                               gen=gs, phases=an.get('phases', 2))
        elif method.startswith('ahcd'):
            S_ = mimo.ahc(Id, na, gen=gs)
        else:
            S_ = mimo.cim(Id, na, As=cfg['cim_as'], pump=cfg['cim_pump'], gen=gs)
        l_hat, allc, d = mimo.select(b, mimo.spins_to_levels_delta(S_, Id, M), lm)
        return mimo.list_llr(b, allc, d, l_hat, clip=BIG), l_hat
    I = mimo.ising(b, z)
    if method.startswith('sane'):
        sa = cfg['sane']
        bl, bd, m0, m1 = mimo.anechoic_soft(I, b, int(method[4:]), sa['S'], sa.get('tmult', 1.0), sa['q'], gen=gs,
                                            t_abs=sa.get('t_abs'), reg=sa.get('reg', False), warm=sa.get('warm', False))
        l_hat, llr = mimo.trajectory_llr(b, bl, bd, m0, m1, lm, clip=BIG)
        return llr, l_hat
    na = int(method[3:])
    if method.startswith('ane'):
        an = cfg['ane']
        S_ = mimo.anechoic(I, na, an['S'], an['t0'], an['t1'], an['q'], kappa=an.get('kappa', 0.0), lam=an.get('lam', 0.0), gen=gs)
    elif method.startswith('cim'):
        S_ = mimo.cim(I, na, As=cfg['cim_as'], pump=cfg['cim_pump'], gen=gs)
    elif method.startswith('ahc'):
        S_ = mimo.ahc(I, na, gen=gs)
    else:
        raise SystemExit('unknown method ' + method)
    l_hat, allc, d = mimo.select(b, mimo.spins_to_levels(S_, M, D), lm)
    return mimo.list_llr(b, allc, d, l_hat, clip=BIG), l_hat


def fit_alpha(llr, bits, grid=None):
    """Scale alpha minimising the bit cross-entropy sum log(1 + exp(-(2b - 1) alpha L)) (logistic calibration without
    intercept), by a grid search followed by a local refinement."""
    sgn = (2 * bits.float() - 1)
    x = (sgn * llr).flatten().double()
    def bce(a):
        return float(torch.nn.functional.softplus(-a * x).mean())
    grid = grid or [0.01 * 1.2 ** k for k in range(40)]
    best = min(grid, key=bce)
    lo, hi = best / 1.2, best * 1.2
    for _ in range(30):                                                    # golden-section refinement
        m1, m2 = lo + (hi - lo) * 0.382, lo + (hi - lo) * 0.618
        if bce(m1) < bce(m2):
            hi = m2
        else:
            lo = m1
    a = (lo + hi) / 2
    return a, bce(a), bce(1.0)
