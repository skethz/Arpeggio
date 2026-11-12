"""Prints SHA-256 of CPU draws (device-independence check of apx.draw across hosts; PROTOCOL.md 2, E0)."""
import hashlib, torch, apx
H = lambda t: hashlib.sha256(t.cpu().contiguous().numpy().tobytes()).hexdigest()[:16]
for (seed, snr, bi, B, nt, M) in ((9100, 20.0, 0, 2000, 16, 16), (9100, 22.0, 3, 1000, 32, 16), (9100, 12.0, 1, 4000, 32, 4), (9100, 12.0, 0, 4000, 16, 4)):
    b = apx.draw(seed, snr, bi, B, nt, M, dev='cpu')
    print(seed, snr, bi, B, nt, M, H(b['H']), H(b['y']), H(b['l']))
