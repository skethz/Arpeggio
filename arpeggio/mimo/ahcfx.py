"""Princeton's AHC-CIM (Singh et al. 2024, Eqs. 9-10; mimo.ahc) with every floating-point operation in a fixed order,
so that a CUDA kernel (ahc_kernel.cu) can reproduce it bit for bit (milestone C, DESIGN.md):
- fp32 throughout, each product and sum rounded separately (no fused multiply-add);
- the mat-vec sum_j Jt_ij x_j accumulated in j order 0..N (the auxiliary spin last), starting from the j = 0 product;
- f(t, x, e): fx = ((p - 1) x - (x x) x) + ((gamma t) e) jx, fe = ((-beta) (x x - a)) e, with the scalars rounded to
  fp32 from their double values as PyTorch does for Python scalars;
- RK4 exactly as mimo.ahc: x + (dt/2) k1, ..., x + (dt/6) (((k1 + 2 k2) + 2 k3) + k4);
- spins s_i = sign(x_i x_aux) (>= 0 -> +1); the energy of the candidate E = -sum_i s_i (h0_i + sum_j J_ij s_j) with the
  inner sum in j order, the outer sum per lane over slots t (row i = 32 t + lane) and then a warp xor tree (16, 8, 4,
  2, 1), the order the kernel uses;
- the start state x0, e0 is an input (generated exactly as mimo.ahc does: randn * sd and |randn * sd|).
Per anneal the lowest-energy state over the 512 steps is kept (first minimum). The settings are mimo.ahc's (published)."""
import math
import ctypes

import torch

import anefx

DEF = dict(steps=512, dt=0.005, p=0.98, a=2.0, beta=1.0, eps_max=1000.0, x0_var=0.001)


def build_jt(I):
    h, J = I['h'], I['J']
    B, N = h.shape
    Jt = torch.zeros(B, N + 1, N + 1, device=h.device)
    Jt[:, :N, :N] = J
    Jt[:, :N, N] = h / 2
    Jt[:, N, :N] = h / 2
    return Jt.contiguous()


def start_state(B, R, Np, gen, dev, x0_var=DEF['x0_var']):
    sd = math.sqrt(x0_var)
    x = torch.randn(B, R, Np, generator=gen, device=dev) * sd
    e = (torch.randn(B, R, Np, generator=gen, device=dev) * sd).abs()
    return x.contiguous(), e.contiguous()


def stage_scalars(steps=DEF['steps'], dt=DEF['dt'], eps_max=DEF['eps_max']):
    gamma = eps_max / (steps * dt)
    g = []
    for k in range(steps):
        t = k * dt
        g.append([gamma * t, gamma * (t + dt / 2), gamma * (t + dt / 2), gamma * (t + dt)])
    return torch.tensor(g, dtype=torch.float32)                           # (steps, 4), rounded from double


@torch.no_grad()
def ahc_od(I, x0, e0, steps=DEF['steps'], dt=DEF['dt'], p=DEF['p'], a=DEF['a'], beta=DEF['beta']):
    """Order-defined reference. Returns the best spins (B, R, N) as float +-1 and their energies (B, R)."""
    J, h0 = I['J'], I['h0']
    B, N = h0.shape
    Np = N + 1
    Jt = build_jt(I)
    gts = stage_scalars(steps, dt).tolist()
    x, e = x0.clone(), e0.clone()
    R = x.shape[1]

    def mv(M, v, n):
        acc = M[:, None, :, 0] * v[:, :, 0:1]
        for j in range(1, n):
            acc = acc + M[:, None, :, j] * v[:, :, j:j + 1]
        return acc

    def f(gt, x, e):
        jx = mv(Jt, x, Np)
        fx = (float(p - 1) * x - (x * x) * x) + (float(gt) * e) * jx
        fe = (float(-beta) * (x * x - a)) * e
        return fx, fe

    m = N // 32
    lane = torch.arange(32, device=x.device)
    best_e = torch.full((B, R), float('inf'), device=x.device)
    best_s = None
    for k in range(steps):
        g1, g2, g3, g4 = gts[k]
        k1x, k1e = f(g1, x, e)
        k2x, k2e = f(g2, x + (dt / 2) * k1x, e + (dt / 2) * k1e)
        k3x, k3e = f(g3, x + (dt / 2) * k2x, e + (dt / 2) * k2e)
        k4x, k4e = f(g4, x + dt * k3x, e + dt * k3e)
        x = x + (dt / 6) * (((k1x + 2 * k2x) + 2 * k3x) + k4x)
        e = e + (dt / 6) * (((k1e + 2 * k2e) + 2 * k3e) + k4e)
        s = torch.where(x[..., :N] * x[..., N:N + 1] >= 0, 1.0, -1.0)
        Js = mv(J, s, N)
        term = s * (h0[:, None, :] + Js)                                   # (B, R, N)
        T = term.reshape(B, R, m, 32)
        v = torch.zeros(B, R, 32, device=x.device)
        for t in range(m):
            v = v + T[:, :, t, :]
        for o in (16, 8, 4, 2, 1):
            v = v + v[..., lane ^ o]
        en = -v[..., 0]
        better = en < best_e
        best_e = torch.where(better, en, best_e)
        best_s = s.clone() if best_s is None else torch.where(better[..., None], s, best_s)
    return best_s, best_e


class AhcKernel(anefx.Kernel):
    """Launcher of ahc_kernel.cu (same driver-API loader as anefx.py)."""
    MPLS = (1, 2, 3, 4, 5, 6)                                             # N / 32 (energy slots); state slots N/32 + 1

    def ahc(self, I, x0, e0, warps=8):
        J, h0 = I['J'], I['h0']
        B, N = h0.shape
        Np = N + 1
        R = x0.shape[1]
        m = N // 32
        assert N % 32 == 0 and m in self.MPLS, 'unsupported spin count %d' % N
        Jt = build_jt(I)
        gts = stage_scalars().to(h0.device).contiguous()
        W = max(1, min(warps, R))
        smem = 4 * (Np * Np + N + 2 * W * Np)
        out_s = torch.empty(B, R, N, dtype=torch.int8, device=h0.device)
        out_e = torch.empty(B, R, dtype=torch.float32, device=h0.device)
        d = DEF
        self.launch('ahc_m%d' % m, B, 32 * W, smem,
                    [Jt, h0.contiguous(), x0, e0, gts, N, R, d['steps'], ('f32', d['p'] - 1), ('f32', d['a']),
                     ('f32', -d['beta']), ('f32', d['dt'] / 2), ('f32', d['dt']), ('f32', d['dt'] / 6), out_s, out_e])
        return out_s, out_e
