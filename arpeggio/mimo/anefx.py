"""Fixed-point Anechoic with a counter-based RNG (DESIGN.md B3): the PyTorch reference `anechoic_fx` and the launcher
of the custom CUDA kernel (`ane_kernel.cu`), which must agree bit for bit.

Arithmetic: h, h0, J (already scaled into [-1, 1] by mimo.ising / ising_delta[_at]) times Q = 2^12, rounded; J is
symmetrised before rounding so that J_int is exactly symmetric. T_k, q and the Onsager-kT term c_k = kappa T_{k-1}
rho_k likewise. The field u = h + 2 J s and the energy 2 E0 = sum_i s_i (h_i - 2 h0_i - u_i) are integers.
Decision (Anechoic's rule): z = s u + q - c_k (s s'), flip iff z < r with r uniform in [-2T, 2T), i.e. iff
U > (z + 2T) / (4T) with U = x / 2^32, evaluated exactly as x * 4T > (z + 2T) * 2^32.
RNG: Philox4x32-10 (Salmon et al., SC 2011), key = (seed mod 2^32, seed >> 32); the n-th update of spin i in anneal r
of instance m uses output n mod 4 of the block at counter (n // 4, i, r, m); the start state uses counter
(2^32 - 1, i, r, m), output 0, spin +1 iff x >= 2^31.
Phases P (dDI copies): at step k only the spins of copy k mod P (spins [p N/P, (p+1) N/P)) may flip; n = k // P.
Per anneal the lowest-energy state after each step is kept (first minimum); mode 'best' keeps the anneal with the
lowest energy per instance (first minimum)."""
import ctypes
import math
import os

import torch

import mimo

QSCALE = 4096
MASK = 0xFFFFFFFF
M0, M1, W0, W1 = 0xD2511F53, 0xCD9E8D57, 0x9E3779B9, 0xBB67AE85


# ---------------------------------------------------------------- Philox4x32-10 on int64 tensors
def _mulhilo(a, m):
    a_lo, a_hi = a & 0xFFFF, a >> 16
    m_lo, m_hi = m & 0xFFFF, m >> 16
    p0 = a_lo * m_lo
    p1 = a_hi * m_lo + a_lo * m_hi
    p2 = a_hi * m_hi
    lo_full = p0 + ((p1 & 0xFFFF) << 16)
    return (p2 + (p1 >> 16) + (lo_full >> 32)) & MASK, lo_full & MASK


def philox(c0, c1, c2, c3, k0, k1):
    """Philox4x32-10 on broadcastable int64 tensors holding uint32 values; returns the 4 output words."""
    c0, c1, c2, c3 = torch.broadcast_tensors(c0, c1, c2, c3)
    for i in range(10):
        if i:
            k0 = (k0 + W0) & MASK
            k1 = (k1 + W1) & MASK
        hi0, lo0 = _mulhilo(c0, M0)
        hi1, lo1 = _mulhilo(c2, M1)
        c0, c1, c2, c3 = hi1 ^ c1 ^ k0, lo1, hi0 ^ c3 ^ k1, lo0
    return c0, c1, c2, c3


# Random123 known-answer vectors (kat_vectors, philox4x32 10): counter (4 words), key (2 words) -> output (4 words)
KAT = [((0, 0, 0, 0), (0, 0), (0x6627e8d5, 0xe169c58d, 0xbc57ac4c, 0x9b00dbd8)),
       ((MASK, MASK, MASK, MASK), (MASK, MASK), (0x408f276d, 0x41c83b0e, 0xa20bc7c6, 0x6d5451fd)),
       ((0x243f6a88, 0x85a308d3, 0x13198a2e, 0x03707344), (0xa4093822, 0x299f31d0),
        (0xd16cfe09, 0x94fdcceb, 0x5001e420, 0x24126ea1))]


# ---------------------------------------------------------------- fixed-point problem and schedule
def to_fixed(I, S, t0, t1, q, kappa=0.0, ramp=True, Q=QSCALE):
    """Integer inputs shared by the reference and the kernel. I: dict from mimo.ising / ising_delta[_at]."""
    J = (I['J'] + I['J'].transpose(1, 2)) / 2
    Ji = torch.round(J * Q).to(torch.int16)
    hi = torch.round(I['h'] * Q).to(torch.int32)
    h0i = torch.round(I['h0'] * Q).to(torch.int32)
    T = mimo.geom(t0, t1, S, 'cpu').double()
    rho = torch.ones(S, dtype=torch.float64)
    if ramp:
        t = torch.arange(S, dtype=torch.float64)
        rho = torch.where(t >= 0.7 * S, (S - 1 - t) / max(1.0, S - 1 - 0.7 * S), torch.ones_like(t))
    c = torch.zeros(S, dtype=torch.float64)
    c[1:] = kappa * T[:-1] * rho[1:]
    dev = I['h'].device
    return dict(J=Ji.contiguous(), h=hi.contiguous(), h0=h0i.contiguous(),
                T=torch.round(T * Q).to(torch.int32).to(dev), c=torch.round(c * Q).to(torch.int32).to(dev),
                q=int(round(q * Q)), S=S, Q=Q)


# ---------------------------------------------------------------- reference (PyTorch)
@torch.no_grad()
def anechoic_fx(F, R, seed, P=1, inst0=0, mode='chains'):
    """Bit-exact definition of the kernel. Returns (best spins int8 (B, R, N) or (B, N), best 2*E0 int64)."""
    J = F['J'].double()
    h, h0 = F['h'].long(), F['h0'].long()
    B, N = h.shape
    dev = h.device
    S, q = F['S'], F['q']
    T, c = F['T'].long().tolist(), F['c'].long().tolist()
    k0, k1 = seed & MASK, (seed >> 32) & MASK
    i = torch.arange(N, device=dev, dtype=torch.int64)[None, None, :]
    r = torch.arange(R, device=dev, dtype=torch.int64)[None, :, None]
    m = (inst0 + torch.arange(B, device=dev, dtype=torch.int64))[:, None, None]
    x = philox(torch.full_like(i, MASK), i, r, m, k0, k1)[0]
    s = torch.where(x >= 2 ** 31, 1, -1).to(torch.int64)
    field = lambda s_: h[:, None, :] + 2 * torch.einsum('bij,brj->bri', J, s_.double()).round().long()
    u = field(s)
    hc = (h - 2 * h0)[:, None, :]
    copy = (torch.arange(N, device=dev) // (N // P))[None, None, :]
    prevflip = torch.zeros(B, R, N, dtype=torch.bool, device=dev)
    best_e = torch.full((B, R), 2 ** 62, dtype=torch.int64, device=dev)
    best_s = s.clone()
    for k in range(S):
        p, n = k % P, k // P
        xr = philox(torch.full_like(i, n // 4), i, r, m, k0, k1)[n % 4]
        z = s * u + q - c[k] * torch.where(prevflip, -1, 1)
        flip = (xr * (4 * T[k]) > (z + 2 * T[k]) * 4294967296) & (copy == p)
        prevflip = flip
        s = torch.where(flip, -s, s)
        u = field(s)
        e = (s * (hc - u)).sum(-1)
        better = e < best_e
        best_e = torch.where(better, e, best_e)
        best_s = torch.where(better[..., None], s, best_s)
    if mode == 'best':
        im = best_e.argmin(1)
        ar = torch.arange(B, device=dev)
        return best_s[ar, im].to(torch.int8), best_e[ar, im]
    return best_s.to(torch.int8), best_e


# ---------------------------------------------------------------- CUDA kernel (driver API via ctypes)
_cu = None


def _check(r, what):
    if r != 0:
        raise RuntimeError('CUDA driver error %d in %s' % (r, what))


class Kernel:
    MPLS = (1, 2, 3, 4, 6, 8)

    def __init__(self, cubin):
        global _cu
        if _cu is None:
            _cu = ctypes.CDLL('libcuda.so.1')
            _cu.cuLaunchKernel.argtypes = [ctypes.c_void_p] + [ctypes.c_uint] * 7 + [ctypes.c_void_p] * 3
            _cu.cuModuleGetFunction.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
            _cu.cuFuncSetAttribute.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            _cu.cuModuleLoadData.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        torch.zeros(1, device='cuda')
        torch.cuda.synchronize()
        ctx = ctypes.c_void_p()
        _check(_cu.cuCtxGetCurrent(ctypes.byref(ctx)), 'cuCtxGetCurrent')
        assert ctx.value, 'no current CUDA context'
        self._img = ctypes.create_string_buffer(open(cubin, 'rb').read())
        self.mod = ctypes.c_void_p()
        _check(_cu.cuModuleLoadData(ctypes.byref(self.mod), self._img), 'cuModuleLoadData')
        self.fn = {}
        self.smem_set = {}

    def func(self, name):
        if name not in self.fn:
            f = ctypes.c_void_p()
            _check(_cu.cuModuleGetFunction(ctypes.byref(f), self.mod, name.encode()), 'cuModuleGetFunction ' + name)
            self.fn[name] = f
        return self.fn[name]

    def launch(self, name, grid, block, smem, args):
        f = self.func(name)
        if smem > 48 * 1024 and self.smem_set.get(name, 0) < smem:
            _check(_cu.cuFuncSetAttribute(f, 8, smem), 'cuFuncSetAttribute')   # MAX_DYNAMIC_SHARED_SIZE_BYTES
            self.smem_set[name] = smem
        vals = []
        for a_ in args:
            if isinstance(a_, torch.Tensor):
                vals.append(ctypes.c_void_p(a_.data_ptr()))
            elif isinstance(a_, tuple) and a_[0] == 'u32':
                vals.append(ctypes.c_uint32(a_[1]))
            elif isinstance(a_, tuple) and a_[0] == 'ptr':
                vals.append(ctypes.c_void_p(a_[1]))
            elif isinstance(a_, tuple) and a_[0] == 'f32':
                vals.append(ctypes.c_float(a_[1]))
            else:
                vals.append(ctypes.c_int(int(a_)))
        arr = (ctypes.c_void_p * len(vals))(*[ctypes.cast(ctypes.pointer(v), ctypes.c_void_p) for v in vals])
        stream = torch.cuda.current_stream().cuda_stream
        _check(_cu.cuLaunchKernel(f, grid, 1, 1, block, 1, 1, smem, ctypes.c_void_p(stream), arr, None), 'launch ' + name)

    def philox_kat(self, words):
        """words: (n, 6) uint32 (counter, key) -> (n, 4) outputs from the device Philox."""
        n = words.shape[0]
        inp = words.to(torch.int64).to(torch.int32).cuda().contiguous()      # bit pattern of uint32
        out = torch.zeros(n, 4, dtype=torch.int32, device='cuda')
        self.launch('philox_kat', (n + 127) // 128, 128, 0, [inp, out, n])
        torch.cuda.synchronize()
        return out.to(torch.int64) & MASK

    def anechoic(self, F, R, seed, P=1, inst0=0, mode='chains', warps=8, stats=None):
        """Kernel run with the same contract as anechoic_fx."""
        B, N = F['h'].shape
        assert N % 32 == 0 and (N // P) % 32 == 0, 'spins per copy must be a multiple of 32'
        mpl = N // 32
        assert mpl in self.MPLS, 'unsupported spin count %d' % N
        W = max(1, min(warps, R))
        smem = ((N * N * 2 + 15) // 16) * 16 + 4 * (2 * N + 64)
        if mode == 'best':
            out_e = torch.empty(B, dtype=torch.int32, device='cuda')
            out_s = torch.empty(B, N, dtype=torch.int8, device='cuda')
        else:
            out_e = torch.empty(B, R, dtype=torch.int32, device='cuda')
            out_s = torch.empty(B, R, N, dtype=torch.int8, device='cuda')
        st = stats if stats is not None else None
        self.launch('ane_m%d' % mpl, B, 32 * W, smem,
                    [F['J'], F['h'], F['h0'], F['T'], F['c'], F['q'], F['S'], P, R, N,
                     ('u32', seed & MASK), ('u32', (seed >> 32) & MASK), inst0, 1 if mode == 'best' else 0,
                     out_e, out_s, ('ptr', st.data_ptr() if st is not None else 0)])
        return out_s, out_e.to(torch.int64)


def spins_float(s8):
    return s8.to(torch.float32)


HERE = os.path.dirname(os.path.abspath(__file__))
