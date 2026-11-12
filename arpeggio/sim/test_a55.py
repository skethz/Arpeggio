#!/usr/bin/env python3
"""A5.5 development checks (PROTOCOL_A55.md section 12). Dev seeds 9600 and 1000 (batch index 50), never held-out."""
import json, torch, apx, apx55, runner_a55  # noqa: F401
mimo = apx.mimo
ok = True


def chk(name, c):
    global ok
    ok = ok and bool(c)
    print(('PASS ' if c else 'FAIL ') + name, flush=True)


def gen(n=12345):
    g = torch.Generator(device='cuda'); g.manual_seed(n)
    return g


def inst(shape, snr, K, B=40, seed=9600):
    s = apx.SHAPES[shape]
    b = apx.draw(seed, snr, 0, B, s['nt'], s['M'])
    z, _, _ = mimo.mmse(b)
    lm = mimo.quantize_levels(z / mimo._mu(b, z), s['M'])
    return b, mimo.ising_delta_at(b, lm, K)


@torch.no_grad()
def seq_r2(I, R, S, T0, T1, K, q, gen):
    """Explicit per-lane loop of rule (2), the sequential reference for fa_seq(rule='r'); the same random numbers and order."""
    h, J, h0 = I['h'], I['J'], I['h0']
    B, N = h.shape
    D = N // (2 * K)
    s = torch.where(torch.rand(B, R, N, generator=gen, device=h.device) < 0.5, -1.0, 1.0)
    u = h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s)
    E = mimo.energy0(s, h0, J)
    best_s, best_e = s.clone(), E.clone()
    Ts = mimo.geom(T0, T1, S, h.device).tolist()
    Jt = J.transpose(1, 2).contiguous()
    nfl = 0
    for sw in range(S):
        T = Ts[sw]
        rnd = torch.rand(B, R, N, generator=gen, device=h.device)
        for i in range(N):
            si = s[..., i]
            dE = 2 * si * u[..., i]
            acc = (si * u[..., i] + q) < ((rnd[..., i] - 0.5) * 4 * T)
            nfl += int(acc.sum())
            delta = torch.where(acc, -2 * si, torch.zeros_like(si))
            u += 2 * delta[..., None] * Jt[:, None, i, :]
            s[..., i] = si + delta
            E += torch.where(acc, dE, torch.zeros_like(dE))
            if (i + 1) % D == 0:
                better = E < best_e
                best_e = torch.where(better, E, best_e)
                best_s = torch.where(better[..., None], s, best_s)
    return best_s, nfl


PTS = (('x16', 20.0, (1, 2, 3)), ('x32', 22.0, (1, 2, 3)), ('q32', 14.0, (1,)))
for shape, snr, Ks in PTS:
    for K in Ks:
        b, I = inst(shape, snr, K)
        for S in (1, 2, 3, 8):
            for T0, T1 in ((2.4, 0.05), (0.3, 0.3)):
                c0, c1 = {}, {}
                x0 = apx.sa_seq(I, 4, S, T0, T1, K, gen=gen(), count=c0)
                x1 = apx55.fa_seq(I, 4, S, T0, T1, K, rule='m', start='rand', gen=gen(), count=c1)
                x2 = apx55.fa_seq(I, 4, S, T0, T1, K, rule='m', start='rand', gen=gen())
                A = I['h'].shape[0] * 4; P = 2 * K
                chk('%s K%d S%d T%g-%g Metropolis fa = sa_seq, flips equal, counter inert, tests formula' % (shape, K, S, T0, T1),
                    torch.equal(x0, x1) and c0[K]['flips'] == c1[K]['flips'] and torch.equal(x1, x2)
                    and c1[K]['tests'] == S * P * A + c1[K]['flips'] - c1[K]['last'] and c1[K]['decisions'] == c0[K]['decisions'])
            x3, n3 = seq_r2(I, 4, S, 0.6, 0.1, K, 0.2, gen())
            c3 = {}
            x4 = apx55.fa_seq(I, 4, S, 0.6, 0.1, K, rule='r', q=0.2, start='rand', gen=gen(), count=c3)
            chk('%s K%d S%d rule (2) fa = explicit per-lane loop, flips equal' % (shape, K, S), torch.equal(x3, x4) and c3[K]['flips'] == n3)
        x5 = apx.snowball_par(I, 4, 30, 0.6, 0.05, gen=gen())
        x6 = apx55.pt_k(I, 4, 30, 0.6, 0.05, 2 * K, start='rand', gen=gen())
        chk('%s K%d pt_k rand = snowball_par' % (shape, K), torch.equal(x5, x6))
        N = I['h'].shape[1]; P = 2 * K; D = N // P
        s0 = apx55.start_spins(I['h'].shape[0], 8, N, P, 'bal', gen(), I['h'].device)
        chk('%s K%d bal: d = 0, spins +-1' % (shape, K), bool((s0.reshape(-1, P, D).sum(1) == 0).all()) and bool((s0.abs() == 1).all()))
        lv = mimo.spins_to_levels_delta(s0, I, b['M'])
        chk('%s K%d bal: first candidate is the guess' % (shape, K), torch.equal(lv, I['xq'][:, None, :].expand_as(lv)))
        for arm in ('m', 'r'):
            xb = apx55.fa_seq(I, 4, 4, 0.6, 0.1, K, rule=arm, q=0.2, start='bal', gen=gen())
            chk('%s K%d bal fa rule %s returns spins' % (shape, K, arm), bool((xb.abs() == 1).all()))
        c7 = {}
        s1 = apx55.ape_k(I, 4, 32 * P, 0.3, 0.3, 0.4, P, start='rand', gen=gen(), count=c7)
        s2 = mimo.anechoic(I, 4, 32 * P, 0.3, 0.3, 0.4, kappa=0.0, gen=gen(), phases=P)
        chk('%s K%d ape_k rand = mimo.anechoic, counter present' % (shape, K), torch.equal(s1, s2) and c7[K]['anneals'] == I['h'].shape[0] * 4)

# the marginal of a copy in 'bal' is uniform
_, I = inst('x16', 20.0, 2)
sb = apx55.start_spins(I['h'].shape[0], 2000, I['h'].shape[1], 4, 'bal', gen(), I['h'].device)
m1 = float(sb.mean(1).abs().max()); print('bal marginal: max |mean over 2000 anneals| %.4f over %d copies, grand mean %.5f' % (m1, sb.mean(1).numel(), float(sb.mean())), flush=True)
chk('bal: every copy +1 with probability 1/2 (max |mean| < 5 sigma = 0.112; a balanced draw has grand mean 0)', m1 < 0.112 and abs(float(sb.mean())) == 0)

# method names through detect, the runner's route, and the count in info
tuned = json.load(open('<SCRATCH>/ap_ber_20261024/results/tuned_a52.json'))
ctx = apx.Ctx(tuned)
for shape, snr, Ns, B in (('x16', 20.0, 32, 200), ('x32', 22.0, 8, 100), ('q32', 14.0, 8, 400)):
    s = apx.SHAPES[shape]
    b = apx.draw(1000, snr, 50, B, s['nt'], s['M'])
    z, _, _ = mimo.mmse(b)
    g = gen(); lh0, _, _ = apx.detect('mdiane%d' % Ns, b, shape, g, ctx, z=z)
    g = gen(); lh1, _, i1 = apx.detect('abl_ape_0.3_0.3_0.4_rand_%d' % Ns, b, shape, g, ctx, z=z)
    chk('%s abl_ape frozen rand = mdiane%d' % (shape, Ns), torch.equal(lh0, lh1) and 'count' in i1)
    g = gen(); lhs, _, _ = apx.detect('abl_sat_0.6_0.05_%d' % Ns, b, shape, g, ctx, z=z)
    g = gen(); lhf, _, i2 = apx.detect('abl_fam_128_0.6_0.05_rand_%d' % Ns, b, shape, g, ctx, z=z)
    chk('%s abl_fam S128 = abl_sat (128 sweeps)' % shape, torch.equal(lhs, lhf) and 'count' in i2)
    for m in ('abl_fam_4_0.6_0.05_bal_%d', 'abl_far_4_0.3_0.3_0.2_bal_%d', 'abl_far_8_1.2_0.1_0.4_rand_%d', 'abl_ape_0.3_0.3_0.4_bal_%d', 'abl_ptb_cyc_0.3_0.05_%d', 'abl_ptb_fl_0.3_0.05_%d'):
        g = gen(); lh, _, i = apx.detect(m % Ns, b, shape, g, ctx, z=z)
        lvl = set(float(x) for x in mimo.PAM[s['M']]['levels'])
        chk('%s %s returns constellation levels, JSON-safe info' % (shape, m % Ns), set(lh.unique().tolist()) <= lvl and bool(json.dumps(i)))
print('ALL PASS' if ok else 'FAIL', flush=True)
