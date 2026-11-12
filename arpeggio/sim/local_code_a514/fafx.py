"""A5.13 (PROTOCOL_A513.md): host side of fa_fx.cu. The cubin is loaded with anefx.Kernel (driver API), as the project's other kernels."""
import os

import numpy as np
import torch

import anefx

HERE = os.path.dirname(os.path.abspath(__file__))
CUBIN = os.environ.get('FAFX_CUBIN', os.path.join(HERE, '..', 'build', 'fa_fx.cubin'))
M32 = 0xFFFFFFFF
_k = None


def kernel():
    global _k
    if _k is None:
        _k = anefx.Kernel(CUBIN)
    return _k


@torch.no_grad()
def solve(G, h, P, R, T, q, inst, key, start):
    """G (B, D, D), h (B, D): integers from antiphase_ref.compress; P copies; R anneals per sub-problem; T: L integers, one per pass
    (pass k tests copy k % P); q integer; inst (B,) integers below 2^32; key: 64-bit Philox key (k0 = low word, k1 = high word);
    start 'rand' or 'bal'. Returns best spins (B, R, P*D) int8 (copy-major, as ape_py.solve_batch), best energy change (B, R) int64,
    and (B, R, 2) int64 flips and comparator passes (tests) per anneal."""
    G = torch.as_tensor(G)
    h = torch.as_tensor(h)
    B, D, _ = G.shape
    assert D <= 128 and P in (2, 4, 6) and len(T) >= 1
    Gt = G.transpose(1, 2).contiguous().to(torch.int32).cuda()
    hh = h.to(torch.int32).contiguous().cuda()
    Tt = torch.tensor([int(x) for x in T], dtype=torch.int32, device='cuda')
    it = torch.as_tensor(np.asarray(inst, dtype=np.int64) & M32).to(torch.int32).cuda()   # uint32 bit pattern
    out_s = torch.empty(B, R, P * D, dtype=torch.int8, device='cuda')
    out_de = torch.empty(B, R, dtype=torch.int64, device='cuda')
    out_st = torch.empty(B, R, 2, dtype=torch.int64, device='cuda')
    n = B * R
    kernel().launch('fa_fx', (n + 127) // 128, 128, 0,
                    [Gt, hh, Tt, len(T), int(q), P, R, D, B, it, ('u32', key & M32), ('u32', (key >> 32) & M32),
                     0 if start == 'rand' else 1, out_s, out_de, out_st])
    torch.cuda.synchronize()
    return out_s.cpu().numpy(), out_de.cpu().numpy(), out_st.cpu().numpy()
