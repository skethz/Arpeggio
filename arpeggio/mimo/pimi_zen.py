"""Read the authors' DI-MIMO instances, true and MMSE symbols, and solved states directly from their Zenodo archives
(16x16_MIMO_results.zip, 8x8_MIMO_results.zip; record 18318271), without extracting them. Text formats as written by
src/def_MIMO.py (np.savetxt): DI_MIMO_J_Quad_k (N+1)^2 floats, [:-1, :-1] = J, [-1, :-1] = h; DI_MIMO_sol_k and
DI_MIMO_mmse_sol_k complex symbols (Nt); solved DI_MIMO_sol_k spins (N). Parsed batches are cached as .npz.
Usage (cache): pimi_zen.py ZIPDIR CACHEDIR nt M snr[,snr...] [n]"""
import io
import multiprocessing as mp
import os
import sys
import zipfile

import numpy as np

ROOT = {16: ('16x16_MIMO_results.zip', 'data16x6'), 8: ('8x8_MIMO_results.zip', 'data8x8')}


def _paths(nt, M, snr):
    top = ROOT[nt][1]
    it = 'Nt%d_Nr%d_%dQAM/%d/' % (nt, nt, M, snr)
    return (top + '/instances/' + it, top + '/ideal_solutions/' + it, top + '/solved_solutions/' + it)


def _complex(txt):
    return np.loadtxt(io.StringIO(txt), dtype=np.complex128)


def _levels(xc):
    return np.concatenate([xc.real, xc.imag], -1)


_Z = {}


def _zip(zp):
    """The archive's central directory (about 1 GB, 5.7-6.2 M members) is parsed once in the parent; forked workers
    reuse the parsed table with their own file handle."""
    if zp not in _Z:
        _Z[zp] = zipfile.ZipFile(zp)
    return _Z[zp]


def _init(zp):
    _Z[zp].fp = open(zp, 'rb')


def _work(args):
    zp, nt, M, snr, ks, subdirs = args
    z = _zip(zp)
    pi, ps, pv = _paths(nt, M, snr)
    J, h, xt, xm = [], [], [], []
    sol = {d: [] for d in subdirs}
    for k in ks:
        a = np.array(z.read(pi + 'DI_MIMO_J_Quad_%d.txt' % k).split(), dtype=np.float64)
        n1 = int(round(np.sqrt(a.size)))
        a = a.reshape(n1, n1)
        J.append(a[:-1, :-1]); h.append(a[-1, :-1])
        xt.append(_levels(_complex(z.read(ps + 'DI_MIMO_sol_%d.txt' % k).decode())))
        xm.append(_levels(_complex(z.read(ps + 'DI_MIMO_mmse_sol_%d.txt' % k).decode())))
        for d in subdirs:
            sol[d].append(np.array(z.read(pv + d + '/DI_MIMO_sol_%d.txt' % k).split(), dtype=np.float64))
    return np.stack(J), np.stack(h), np.stack(xt), np.stack(xm), {d: np.stack(v) for d, v in sol.items()}


def load(zipdir, nt, M, snr, ks, subdirs=(), procs=16):
    zp = os.path.join(zipdir, ROOT[nt][0])
    chunks = [list(ks[i::procs]) for i in range(procs) if len(ks[i::procs])]
    _zip(zp)
    if procs == 1:
        parts = [_work((zp, nt, M, snr, chunks[0], tuple(subdirs)))]
        return _merge(parts, chunks, subdirs)
    with mp.get_context('fork').Pool(len(chunks), initializer=_init, initargs=(zp,)) as pool:
        parts = pool.map(_work, [(zp, nt, M, snr, c, tuple(subdirs)) for c in chunks])
    return _merge(parts, chunks, subdirs)


def _merge(parts, chunks, subdirs):
    order = np.concatenate([np.array(c) for c in chunks])
    inv = np.argsort(order)
    J = np.concatenate([p[0] for p in parts])[inv]
    h = np.concatenate([p[1] for p in parts])[inv]
    xt = np.concatenate([p[2] for p in parts])[inv]
    xm = np.concatenate([p[3] for p in parts])[inv]
    sol = {d: np.concatenate([p[4][d] for p in parts])[inv] for d in subdirs}
    return J, h, xt, xm, sol


def subdirs(nt, M):
    """Solved-state folders of the Fig. 6 settings (16-bit, 4-level LUT, 32 trials) present in the archives."""
    steps = {(8, 4): (16, 64), (8, 16): (32, 128), (8, 64): (64, 256), (16, 4): (32, 128), (16, 16): (64, 256),
             (16, 64): (64, 256)}[(nt, M)]
    return ['tanh_lut_4/16_precision/%d_steps_32_anneals' % s for s in steps]


if __name__ == '__main__':
    zipdir, cache, nt, M = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    n = int(sys.argv[6]) if len(sys.argv) > 6 else 10000
    os.makedirs(cache, exist_ok=True)
    for snr in [int(x) for x in sys.argv[5].split(',')]:
        out = os.path.join(cache, 'nt%d_M%d_snr%d.npz' % (nt, M, snr))
        if os.path.exists(out):
            continue
        sd = subdirs(nt, M)
        J, h, xt, xm, sol = load(zipdir, nt, M, snr, list(range(n)), sd)
        Jq = np.clip(np.trunc(J * 4096), -32768, 32767).astype(np.int16)
        hq = np.clip(np.trunc(h * 4096), -32768, 32767).astype(np.int16)
        np.savez(out, Jq=Jq, hq=hq, xt=xt.astype(np.int8), xm=xm.astype(np.int8),
                 **{'sol_' + d.split('/')[-1]: v.astype(np.int8) for d, v in sol.items()})
        print('cached', out, Jq.shape, flush=True)
