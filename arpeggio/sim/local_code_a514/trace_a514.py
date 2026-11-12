#!/usr/bin/env python3
"""A5.14-A5.16 worker (PROTOCOL_A514.md, PROTOCOL_A515.md, PROTOCOL_A516.md). trace_a56.py unchanged, run as __main__ after two
registrations: apx.SHAPES['x64'] exactly as trace_x64.py (A5.8), and apx514.install() so abl_faw_* names reach apx514.fa_seq_w.
Every other method resolves as in trace_a56.py. Jobs may fix first_batch and n_batches (chunks) and may name a saved directory that
the batches must reproduce bit for bit. Same arguments as trace_a56.py."""
import os
import runpy

import apx
import apx514
import mdi_solvers

c = mdi_solvers.MDI[('64x64', 16)]
apx.SHAPES.setdefault('x64', dict(nt=64, M=16, mdi=dict(Rmax=int(c['Rmax']), S=int(c['S']), guesses=tuple(c['guesses'])), Ns_pub=None))
apx514.install()
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trace_a56.py'), run_name='__main__')
