#!/usr/bin/env python3
"""A5.6 amendment 5 (STATUS.md): trace_a56.py with the 64x64 16-QAM shape of Table IV's row "D128 X64" registered, the MDI configuration of
mdi_solvers.MDI[('64x64', 16)] (Rmax 3, S 8, guesses mmse and sic, as x16 and x32). trace_a56.py itself is unchanged: this only adds
apx.SHAPES['x64'] and then runs it as __main__. Same arguments as trace_a56.py."""
import os
import runpy

import apx
import mdi_solvers

c = mdi_solvers.MDI[('64x64', 16)]
apx.SHAPES.setdefault('x64', dict(nt=64, M=16, mdi=dict(Rmax=int(c['Rmax']), S=int(c['S']), guesses=tuple(c['guesses'])), Ns_pub=None))
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trace_a56.py'), run_name='__main__')
