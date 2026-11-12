"""ctypes bindings of the cycle-accurate Antiphase engine model (ape_model.cpp) and command-list helpers."""
import ctypes
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, 'libape.so')
OP_LOAD_ROW, OP_LOAD_H, OP_LOAD_TAB, OP_RUN = 1, 2, 3, 4


class Cmd(ctypes.Structure):
    _fields_ = [('op', ctypes.c_int32), ('addr', ctypes.c_int32), ('P', ctypes.c_int32), ('R', ctypes.c_int32),
                ('S', ctypes.c_int32), ('tb', ctypes.c_int32), ('q', ctypes.c_int32), ('tag', ctypes.c_int32),
                ('T', ctypes.c_int32), ('c', ctypes.c_int32), ('inst', ctypes.c_uint32), ('pad', ctypes.c_uint32),
                ('seed', ctypes.c_uint64), ('data_off', ctypes.c_int64)]


class Stats(ctypes.Structure):
    _fields_ = [(n, ctypes.c_longlong) for n in ('cycles', 'n_dop', 'n_fop', 'n_iop', 'n_beats', 'n_rport_busy')]


def build():
    src = os.path.join(HERE, 'ape_model.cpp')
    if not os.path.exists(LIB) or os.path.getmtime(LIB) < os.path.getmtime(src):
        subprocess.check_call(['g++', '-O3', '-march=native', '-std=c++17', '-pthread', '-shared', '-fPIC', '-o', LIB, src])
    lib = ctypes.CDLL(LIB)
    lib.ape_exec.restype = ctypes.c_longlong
    lib.ape_solve_batch.restype = ctypes.c_int
    return lib


_lib = None


class Program:
    """A command list for one engine."""
    def __init__(self, D):
        self.D = D
        self.cmds = []
        self.data = []
        self.ndata = 0

    def _push(self, op, data=None, **kw):
        c = Cmd()
        c.op = op
        for k, v in kw.items():
            setattr(c, k, v)
        if data is not None:
            d = np.asarray(data, dtype=np.int16).reshape(-1)
            assert d.size == self.D
            c.data_off = self.ndata
            self.data.append(d)
            self.ndata += self.D
        self.cmds.append(c)

    def load_G(self, G):
        for i in range(self.D):
            self._push(OP_LOAD_ROW, G[i], addr=i)

    def load_h(self, h):
        self._push(OP_LOAD_H, h)

    def load_tab(self, T, c, base=0):
        for k in range(len(T)):
            self._push(OP_LOAD_TAB, addr=(base + k) % 1024, T=int(T[k]), c=int(c[k]))

    def run(self, P, R, S, q, inst, seed, tag, tb=0):
        self._push(OP_RUN, P=P, R=R, S=S, tb=tb, q=q, inst=inst & 0xFFFFFFFF, seed=seed & 0xFFFFFFFFFFFFFFFF, tag=tag)

    def execute(self, A=4, SEEDL=None, philox=0, max_beats=None):
        global _lib
        if _lib is None:
            _lib = build()
        D = self.D
        SEEDL = SEEDL or max(1, D // 32)
        n = len(self.cmds)
        arr = (Cmd * n)(*self.cmds)
        dbuf = np.concatenate(self.data) if self.data else np.zeros(1, np.int16)
        dbuf = np.ascontiguousarray(dbuf, dtype=np.int16)
        acc = np.zeros(n, np.int64)
        if max_beats is None:
            max_beats = sum(c.R * c.P for c in self.cmds if c.op == OP_RUN)
        mb = max(1, max_beats)
        bc, bt, br, bp = np.zeros(mb, np.int64), np.zeros(mb, np.int32), np.zeros(mb, np.int32), np.zeros(mb, np.int32)
        bd, bb = np.zeros(mb, np.int64), np.zeros(mb * D, np.uint8)
        nb = ctypes.c_int(0)
        st = Stats()
        P_ = lambda a: a.ctypes.data_as(ctypes.c_void_p)
        cyc = _lib.ape_exec(D, A, SEEDL, philox, n, arr, P_(dbuf), P_(acc), mb, ctypes.byref(nb), P_(bc), P_(bt), P_(br),
                            P_(bp), P_(bd), P_(bb), ctypes.byref(st))
        k = nb.value
        assert k <= mb
        return dict(cycles=cyc, acc=acc, beat_cycle=bc[:k], tag=bt[:k], r=br[:k], p=bp[:k], de=bd[:k],
                    bits=bb[:k * D].reshape(k, D), stats={f: getattr(st, f) for f, _ in Stats._fields_})


def collect(res, P_of_tag, D):
    """Beats -> {(tag, r): (spins (P*D,) int8 in copy-major order, Δbest)}."""
    out = {}
    for i in range(len(res['tag'])):
        key = (int(res['tag'][i]), int(res['r'][i]))
        P = P_of_tag[key[0]]
        if key not in out:
            out[key] = [np.zeros(P * D, np.int8), int(res['de'][i]), 0]
        p = int(res['p'][i])
        out[key][0][p * D:(p + 1) * D] = np.where(res['bits'][i] > 0, 1, -1)
        out[key][2] += 1
        assert out[key][1] == int(res['de'][i])
    for key, v in out.items():
        assert v[2] == P_of_tag[key[0]], 'missing beats for %s' % (key,)
    return {k: (v[0], v[1]) for k, v in out.items()}


def solve_batch(G, h, P, R, T, c, q, inst, seed, A=4, SEEDL=None, philox=0, nthreads=16):
    """B independent sub-problems through the cycle model. G (B, D, D), h (B, D) int arrays; inst (B,) uint32.
    Returns spins (B, R, P*D) int8, de (B, R), cycles (B,) and stats (B, 4)."""
    global _lib
    if _lib is None:
        _lib = build()
    G = np.ascontiguousarray(G, dtype=np.int16); h = np.ascontiguousarray(h, dtype=np.int16)
    B, D, _ = G.shape
    SEEDL = SEEDL or max(1, D // 32)
    S = len(T)
    T = np.ascontiguousarray(T, dtype=np.int16); c = np.ascontiguousarray(c, dtype=np.int16)
    inst = np.ascontiguousarray(inst, dtype=np.uint32)
    spins = np.zeros((B, R, P * D), np.int8); de = np.zeros((B, R), np.int64)
    cyc = np.zeros(B, np.int64); st = np.zeros((B, 4), np.int64)
    P_ = lambda a: a.ctypes.data_as(ctypes.c_void_p)
    _lib.ape_solve_batch(D, A, SEEDL, philox, B, P_(G), P_(h), P, R, S, P_(T), P_(c), int(q), P_(inst),
                         ctypes.c_uint64(seed & 0xFFFFFFFFFFFFFFFF), P_(spins), P_(de), P_(cyc), P_(st), nthreads)
    return spins, de, cyc, st
