"""Dev check of apx.sym_hb (dev seed 9300, K = 1 sub-problems around MMSE at 16x16 16-QAM 20 dB): best d-space energy
reached by Antiphase, the synchronous symbol heat-bath (apx.sym_hb) and a sequential one-dimension-at-a-time
heat-bath, against the truth's delta (when inside the box). Not a held-out measurement."""
import torch, apx, mimo
b = apx.draw(9300, 20.0, 0, 400, 16, 16)
z, _, _ = mimo.mmse(b)
lm = mimo.quantize_levels(z / mimo._mu(b, z), 16)
I = mimo.ising_delta_at(b, lm, 1)
D, P = 32, 2
G = -I['J'][:, :D, D:2 * D]; bt = I['h0'][:, :D] / 2
ed = lambda d: (d * torch.einsum('bij,brj->bri', G, d)).sum(-1) - 2 * (bt[:, None, :] * d).sum(-1)
tod = lambda s: s.reshape(s.shape[0], s.shape[1], P, D).sum(2)
td = (b['l'] - lm)[:, None, :]
inb = td.abs().amax(-1)[:, 0] <= 2
eT = ed(td)[:, 0]
g = torch.Generator(device='cuda'); g.manual_seed(1)
ea = ed(tod(mimo.anechoic(I, 8, 256, 0.3, 0.3, 0.4, gen=g, phases=2))).amin(1)
def seq_hb(R, sweeps, T, gen):
    B = G.shape[0]; Gd = torch.diagonal(G, dim1=-2, dim2=-1)
    d = tod(torch.where(torch.rand(B, R, 2 * D, generator=gen, device='cuda') < 0.5, -1.0, 1.0))
    best = ed(d)
    for sw in range(sweeps):
        for m in range(D):
            gm = torch.einsum('bj,brj->br', G[:, m, :], d)
            dEp = 4 * gm + 4 * Gd[:, m:m + 1] - 4 * bt[:, m:m + 1]; dEm = -4 * gm + 4 * Gd[:, m:m + 1] + 4 * bt[:, m:m + 1]
            dEp = torch.where(d[..., m] + 2 > P, torch.inf, dEp); dEm = torch.where(d[..., m] - 2 < -P, torch.inf, dEm)
            pr = torch.softmax(torch.stack([torch.zeros_like(dEp), -dEp / T, -dEm / T], -1), -1)
            u = torch.rand(B, R, generator=gen, device='cuda')
            d[..., m] += torch.where(u < pr[..., 0], 0.0, torch.where(u < pr[..., 0] + pr[..., 1], 2.0, -2.0))
            best = torch.minimum(best, ed(d))
    return best.amin(1)
print('instances', len(inb), 'truth in K=1 box', int(inb.sum()), 'guess==truth', int((td.abs().amax(-1)[:, 0] == 0).sum()))
print('Antiphase: frac best<=truth (in box)', float((ea <= eT + 1e-5)[inb].float().mean()))
for T, q, md in ((0.1, 0, 'prop'), (0.2, 0, 'prop'), (0.4, 0, 'prop'), (0.2, 0.4, 'prop'), (0.4, 0.4, 'prop'), (0.2, 0.4, 'win'), (0.4, 0.8, 'win'), (0.8, 0.8, 'prop')):
    g2 = torch.Generator(device='cuda'); g2.manual_seed(2)
    es = ed(tod(apx.sym_hb(I, 8, 256, T, 1, q=q, mode=md, gen=g2))).amin(1)
    print(md, q, end=' ')
    g3 = torch.Generator(device='cuda'); g3.manual_seed(3)
    eq = seq_hb(8, 32, T, g3)
    print('T %.2f  sync-HB frac<=truth %.3f  seq-HB frac<=truth %.3f  mean(sync-anti) %.3f  mean(seq-anti) %.3f' % (
        T, float((es <= eT + 1e-5)[inb].float().mean()), float((eq <= eT + 1e-5)[inb].float().mean()), float((es - ea).mean()), float((eq - ea).mean())))
