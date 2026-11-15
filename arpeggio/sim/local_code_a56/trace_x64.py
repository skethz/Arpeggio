#!/usr/bin/env python3
"""A5.6: trace_a56.py with the 64x64 16-QAM shape of Table IV's row "D128 X64" registered, the MDI configuration of
mdi_solvers.MDI[('64x64', 16)] (Rmax 3, S 8, guesses mmse and sic, as x16 and x32). This wraps trace_a56.py without modifying it: it only adds
arpx.SHAPES['x64'] and then runs it as __main__. Same arguments as trace_a56.py."""
import os
import runpy

import arpx
import mdi_solvers

c = mdi_solvers.MDI[('64x64', 16)]
arpx.SHAPES.setdefault('x64', dict(nt=64, M=16, mdi=dict(Rmax=int(c['Rmax']), S=int(c['S']), guesses=tuple(c['guesses'])), Ns_pub=None))
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trace_a56.py'), run_name='__main__')
