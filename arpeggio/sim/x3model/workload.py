"""MDI-Antiphase on the engine model: BER and per-detection engine work at a matched-BER point (CPU only).

Draws: mimo.make_batch(B, Nt, Nt, M, snr, torch.Generator('cpu').manual_seed(seed), device='cpu'), one call (the same
draws as the MDI-AHC fork). Wrapper: `mdi_logged`, a copy of mimo.mdi (Singh et al. 2024 Sec. IV-C, Table I settings,
as the study runs it) that also tells the solver which detections, stage and guess a call belongs to; checked equal
to mimo.mdi with --check. Solvers:
  float      the study's PyTorch Anechoic (mimo.anechoic, Sk 128, T 0.3, q 0.4, 2K phases), its own torch generator;
  fx_philox  the engine (ape_model.cpp, cycle model) with Philox streams = the CUDA kernel's arithmetic and RNG;
  fx_xs      the engine with the production xorshift streams.
Engine runs: per sub-problem (instance) LOAD G, LOAD h, RUN; seed per solver call, inst = detection index.
Replay (--replay N): the first N detections' full command sequences (stage by stage, guess by guess, K = 1..R_g queued
back to back, G and h reloaded only when they change) through the cycle model -> cycles per detection.
Usage: workload.py <study_src> <out.json> --nt 16 --M 16 --snr 20 --ns 32 --seed 41 --B 4000 --solver fx_xs [--replay 200]
"""
import sys, os, json, math, time, argparse
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import torch
import mimo, anefx, mdi_solvers
import antiphase_ref as ar
import ape_py

ap = argparse.ArgumentParser()
ap.add_argument('study'); ap.add_argument('out')
ap.add_argument('--nt', type=int); ap.add_argument('--M', type=int); ap.add_argument('--snr', type=float)
ap.add_argument('--ns', type=int); ap.add_argument('--seed', type=int); ap.add_argument('--B', type=int)
ap.add_argument('--solver', default='fx_xs'); ap.add_argument('--replay', type=int, default=0)
ap.add_argument('--A', type=int, default=4); ap.add_argument('--threads', type=int, default=16)
ap.add_argument('--check', action='store_true'); ap.add_argument('--keep', type=int, default=0)
ap.add_argument('--stim', type=int, default=0, help='write stim/expected for the first N detections (with --replay >= N)')
ap.add_argument('--single', type=int, default=0, help='one delta stage around MMSE with this many anneals (milestone D ane_ss)')
args = ap.parse_args()
torch.set_num_threads(args.threads)
MDIANE = mdi_solvers.MDIANE


@torch.no_grad()
def mdi_logged(b, solver, Ns, Rmax, S, guesses=('mmse', 'sic'), heuristic='mean', sic_per='real', na_round='ceil'):
    """mimo.mdi with metadata for the solver (identical arithmetic)."""
    M = b['M']
    B, D = b['H'].shape[0], b['H'].shape[-1]
    dev = b['H'].device
    z_mmse, Ai, _ = mimo.mmse(b)
    cur = {}
    for g in guesses:
        cur[g] = mimo.quantize_levels(z_mmse / mimo._mu(b, z_mmse), M) if g == 'mmse' else mimo.mmse_sic(b, per=sic_per)
    ann = torch.zeros(B, device=dev)
    nst = 0
    for st in range(S):
        R = {g: mimo.mdi_radius(b, cur[g], Rmax, heuristic)[0] for g in guesses}
        tot = sum(R[g] for g in guesses)
        if int(tot.max()) == 0:
            break
        nst += 1
        nxt = {}
        for g in guesses:
            bl, bd = cur[g].clone(), mimo.dist(b, cur[g][:, None, :])[:, 0]
            for K in range(1, Rmax + 1):
                need = R[g] >= K
                if not bool(need.any()):
                    continue
                for t in torch.unique(tot[need]).tolist():
                    idx = torch.nonzero(need & (tot == t)).flatten()
                    na = math.ceil(Ns / t) if na_round == 'ceil' else max(1, Ns // t)
                    sb = mimo.subset(b, idx)
                    I = mimo.ising_delta_at(sb, cur[g][idx], K)
                    Ssp = solver(I, na, K, dict(idx=idx, stage=st, guess=g))
                    Lc = mimo.spins_to_levels_delta(Ssp, I, M)
                    dd = mimo.dist(sb, Lc)
                    dm, im = dd.min(1)
                    better = dm < bd[idx]
                    bd[idx] = torch.where(better, dm, bd[idx])
                    bl[idx] = torch.where(better[:, None], Lc[torch.arange(len(idx), device=dev), im], bl[idx])
                    ann[idx] += na
            nxt[g] = bl
        cur = nxt
    allc = torch.stack([cur[g] for g in guesses], 1)
    d = mimo.dist(b, allc)
    return allc[torch.arange(B, device=dev), d.argmin(1)], ann, nst


cfg = mdi_solvers.MDI[('%dx%d' % (args.nt, args.nt), args.M)]
gen = torch.Generator(device='cpu').manual_seed(args.seed)
b = mimo.make_batch(args.B, args.nt, args.nt, args.M, args.snr, gen, device='cpu')
D = 2 * args.nt
dummy = dict(J=torch.zeros(1, 2, 2), h=torch.zeros(1, 2), h0=torch.zeros(1, 2))
TAB = {}
for K in (1, 2, 3):
    F = anefx.to_fixed(dummy, MDIANE['Sk'] * 2 * K, MDIANE['t0'], MDIANE['t1'], MDIANE['q'], MDIANE['kappa'])
    TAB[K] = (F['T'].numpy().astype(np.int16), F['c'].numpy().astype(np.int16), int(F['q']))
log = []          # per sub-problem instance: det, stage, guess, K, na, cycles, dop, fop, iop, rport, call
keepGH = {}       # (det, call) -> (G, h) for the replay sample
calls = [0]
check_mode = [False]
seed_base = (args.seed * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
fgen = torch.Generator(device='cpu').manual_seed(args.seed + 100000)


def call_seed(ci):
    return (seed_base + ci * 0xD1B54A32D192ED03) & 0xFFFFFFFFFFFFFFFF


def solver(I, na, K, meta):
    ci = calls[0]; calls[0] += 1
    if args.solver == 'float':
        return mimo.anechoic(I, na, MDIANE['Sk'] * 2 * K, MDIANE['t0'], MDIANE['t1'], MDIANE['q'], kappa=MDIANE['kappa'],
                             gen=fgen, phases=2 * K)
    F = anefx.to_fixed(I, MDIANE['Sk'] * 2 * K, MDIANE['t0'], MDIANE['t1'], MDIANE['q'], MDIANE['kappa'])
    G, h = ar.compress(F, K)
    T, c, q = TAB[K]
    idx = meta['idx'].numpy()
    inst = np.zeros_like(idx) if check_mode[0] else idx
    spins, de, cyc, st = ape_py.solve_batch(G.numpy(), h.numpy(), 2 * K, na, T, c, q, inst.astype(np.uint32),
                                            call_seed(ci), A=args.A, philox=1 if args.solver == 'fx_philox' else 0,
                                            nthreads=args.threads)
    gi = {'mmse': 0, 'sic': 1}[meta['guess']]
    for n, det in enumerate(idx.tolist()):
        log.append([det, meta['stage'], gi, K, na, int(cyc[n]), *[int(v) for v in st[n]], ci])
        if det < args.replay:
            keepGH[(det, ci)] = (G[n].numpy().astype(np.int16), h[n].numpy().astype(np.int16))
    return torch.from_numpy(spins).float()


t0 = time.time()
if args.check:   # the logged wrapper equals mimo.mdi with the same deterministic solver
    small = mimo.subset(b, torch.arange(min(64, args.B)))
    check_mode[0] = True; calls[0] = 0
    l1, _, _ = mdi_logged(small, solver, args.ns, cfg['Rmax'], cfg['S'], guesses=tuple(cfg['guesses']))
    calls[0] = 0
    l2 = mimo.mdi(small, lambda I, na, K: solver(I, na, K, dict(idx=torch.arange(I['h'].shape[0]), stage=-1, guess='mmse')),
                  args.ns, cfg['Rmax'], cfg['S'], guesses=tuple(cfg['guesses']))
    print('CHECK mdi_logged == mimo.mdi:', bool((l1 == l2).all()), flush=True)
    log.clear(); keepGH.clear(); calls[0] = 0; check_mode[0] = False
    fgen.manual_seed(args.seed + 100000)
if args.single:   # milestone D's "Antiphase, one stage" (bench_d.py ane_ss): dDI K = 1 around MMSE, R anneals, mimo.select
    z, Ai, _ = mimo.mmse(b)
    lm = mimo.mmse_hard(b, z, Ai)
    Id = mimo.ising_delta(b, z, K=1)
    S_ = solver(Id, args.single, 1, dict(idx=torch.arange(args.B), stage=0, guess='mmse'))
    lh, _, _ = mimo.select(b, mimo.spins_to_levels_delta(S_, Id, args.M), lm)
    ann, nst = torch.full((args.B,), float(args.single)), 1
else:
    lh, ann, nst = mdi_logged(b, solver, args.ns, cfg['Rmax'], cfg['S'], guesses=tuple(cfg['guesses']))
err, nb = mimo.bit_errors(b, lh)
wall = time.time() - t0
res = dict(args=vars(args), ber=err / nb, bit_errors=err, bits=nb, anneals_per_det=float(ann.mean()), stages_max=nst,
           wall_s=wall, calls=calls[0])
if args.solver != 'float':
    L = np.array(log, dtype=np.int64)
    per_det_cyc = np.bincount(L[:, 0], weights=L[:, 5], minlength=args.B)
    res.update(subproblems=len(L), subproblems_per_det=len(L) / args.B,
               standalone_cycles_per_det=float(per_det_cyc.mean()),
               standalone_cycles_p50_p90_p99=[float(np.percentile(per_det_cyc, x)) for x in (50, 90, 99)],
               dops=int(L[:, 6].sum()), fops=int(L[:, 7].sum()), iops=int(L[:, 8].sum()), rport=int(L[:, 9].sum()),
               flips_per_halfstep=float(L[:, 7].sum() / L[:, 6].sum()),
               by_K={int(k): dict(n=int((L[:, 3] == k).sum()), anneals=int(L[L[:, 3] == k, 4].sum()),
                                  flips_per_halfstep=float(L[L[:, 3] == k, 7].sum() / max(1, L[L[:, 3] == k, 6].sum())),
                                  cycles=int(L[L[:, 3] == k, 5].sum())) for k in (1, 2, 3)})
    # per-anneal flip rate distribution (per sub-problem instance: F-ops / D-ops)
    fr = L[:, 7] / np.maximum(1, L[:, 6])
    res['flip_rate_quantiles'] = [float(np.quantile(fr, x)) for x in (0.1, 0.5, 0.9, 0.99)]
    if args.replay:
        from collections import defaultdict
        bydet = defaultdict(list)
        for row in L:
            if row[0] < args.replay:
                bydet[int(row[0])].append(row)
        rep_cyc, nG, nH = [], [], []
        stim_pr = None
        if args.stim:                                       # one program: table, then the first N detections back to back
            stim_pr = ape_py.Program(D); T3s, c3s, _ = TAB[3]; stim_pr.load_tab(T3s, c3s, 0); stim_curG = stim_curH = None
        for det in sorted(bydet):
            rows = bydet[det]
            pr = ape_py.Program(D)
            T3, c3, q = TAB[3]
            pr.load_tab(T3, c3, 0)
            ntab = len(pr.cmds)
            curG = curH = None; ng = nh = 0
            for row in rows:
                ci, K, na = int(row[10]), int(row[3]), int(row[4])
                G, h = keepGH[(det, ci)]
                if curG is None or not np.array_equal(G, curG):
                    pr.load_G(G); curG = G; ng += 1
                if curH is None or not np.array_equal(h, curH):
                    pr.load_h(h); curH = h; nh += 1
                pr.run(2 * K, na, MDIANE['Sk'] * 2 * K, q, det, call_seed(ci), tag=ci & 0xFFFF)
                if stim_pr is not None and det < args.stim:
                    if stim_curG is None or not np.array_equal(G, stim_curG):
                        stim_pr.load_G(G); stim_curG = G
                    if stim_curH is None or not np.array_equal(h, stim_curH):
                        stim_pr.load_h(h); stim_curH = h
                    stim_pr.run(2 * K, na, MDIANE['Sk'] * 2 * K, q, det, call_seed(ci), tag=ci & 0xFFFF)
            out = pr.execute(A=args.A, philox=1 if args.solver == 'fx_philox' else 0)
            start = int(out['acc'][ntab])                  # first non-table command accepted
            rep_cyc.append(int(out['cycles']) - start); nG.append(ng); nH.append(nh)
        if stim_pr is not None:
            import stimio
            sres = stim_pr.execute(A=args.A)
            stimio.write(stim_pr, sres, args.out.replace('.json', '_stim'),
                         dict(stim_detections=args.stim, first_work_cmd=len(TAB[3][0])))
        nrep = min(args.replay, args.B)                      # detections with no sub-problem cost 0 engine cycles
        zeros = nrep - len(rep_cyc)
        rc = rep_cyc + [0] * zeros
        res.update(replay_detections=nrep, replay_detections_with_work=len(rep_cyc), replay_cycles_per_det=float(np.mean(rc)),
                   replay_cycles_p50_p90=[float(np.percentile(rc, 50)), float(np.percentile(rc, 90))],
                   replay_G_loads_per_det=float(np.sum(nG) / nrep), replay_h_loads_per_det=float(np.sum(nH) / nrep),
                   standalone_cycles_per_det_sample=float(np.sum([sum(int(r[5]) for r in bydet[d]) for d in sorted(bydet)]) / nrep))
    if args.keep:
        np.save(args.out.replace('.json', '_log.npy'), L)
json.dump(res, open(args.out, 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ('by_K',)}), flush=True)
