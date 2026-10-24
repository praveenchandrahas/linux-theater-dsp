"""Fixed matrix vs adaptive ambience: instrument leak into the surround feed vs the reverb that should be there."""
import time, numpy as np
from scipy.signal import coherence
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
import metrics as M, adaptive as A, upmix_engine as EN
FS = 48000
n = FS * 20
t = np.arange(n) / FS
def dense(seed):                            # worst case: noise-like, fills every bin
    return M.pink(n, seed) * (0.3 + 0.7 * np.abs(np.sin(2 * np.pi * 1.5 * t)))
def sparse(seed):                           # realistic: harmonic notes (12 partials, vibrato), a new pitch every 0.4 s
    rng = np.random.default_rng(seed); x = np.zeros(n)
    f0s = 110 * 2 ** (rng.integers(0, 18, size=int(20 / 0.4)) / 12.0)
    for i, f0 in enumerate(f0s):
        s = slice(int(i * 0.4 * FS), int((i + 1) * 0.4 * FS)); tt = t[s] - t[s][0]
        ph = 2 * np.pi * np.cumsum(f0 * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * tt))) / FS
        x[s] = sum(np.sin(k * ph) / k for k in range(1, 13)) * np.exp(-2.5 * tt)
    return x / np.sqrt(np.mean(x ** 2)) * 0.1
def split_run(L, R, parts):
    """Streaming engine over the mixture L, R; the mask it derives is applied (with its own OLA) to each (l, r) in parts.
    Returns the aL of the mixture and of every part, aligned to the input (engine latency removed)."""
    eng = EN.StereoAmbience(); hop, nn = eng.hop, eng.n
    sig = [(L, R)] + list(parts)
    m = len(L); pad = (-m) % hop + nn
    z = np.zeros(pad)
    sig = [(np.concatenate([a, z]), np.concatenate([b, z])) for a, b in sig]
    bufs = [np.zeros((2, nn)) for _ in sig]; accs = [np.zeros((2, nn)) for _ in sig]
    outs = [np.zeros(len(sig[0][0])) for _ in sig]
    for i in range(0, len(sig[0][0]), hop):
        X = []
        for k, (a, b) in enumerate(sig):
            bufs[k][:, :-hop] = bufs[k][:, hop:]
            bufs[k][0, -hop:], bufs[k][1, -hop:] = a[i:i + hop], b[i:i + hop]
            X.append((np.fft.rfft(bufs[k][0] * eng.win), np.fft.rfft(bufs[k][1] * eng.win)))
        cLL, cLR, cRL, cRR = eng.coefficients(*X[0])
        for k, (XL, XR) in enumerate(X):
            accs[k][:, :-hop] = accs[k][:, hop:]; accs[k][:, -hop:] = 0
            accs[k][0] += np.fft.irfft(cLL * XL + cLR * XR, nn) * eng.win * 0.5
            accs[k][1] += np.fft.irfft(cRL * XL + cRR * XR, nn) * eng.win * 0.5
            outs[k][i:i + hop] = accs[k][0, :hop]
    return [o[:m] for o in outs]
def bandpow(x): return np.mean(M.band(x[FS:]) ** 2)
def db(x): return 10 * np.log10(x + 1e-18)
def report(name, inst, pan_r, rev=0.316, **kw):
    rl, rr = M.pink(n, 2), M.pink(n, 3)
    Lc, Rc = inst + rev * rl, pan_r * inst + rev * rr
    z = np.zeros(n)
    parts = [(inst, pan_r * inst), (rev * rl, z), (z, rev * rr)]
    res = split_run(Lc, Rc, parts); ap = [(r, None) for r in res[1:]]
    P_inst_L, P_rev_L = bandpow(inst), bandpow(rev * rl)
    # fixed matrix: S = (L-R)/2 applied to each part exactly
    fx = [(pl - pr) / 2 for pl, pr in parts]
    fl, fr = db(bandpow(fx[0]) / P_inst_L), db((bandpow(fx[1]) + bandpow(fx[2])) / P_rev_L)
    al, ar = db(bandpow(ap[0][0]) / P_inst_L), db((bandpow(ap[1][0]) + bandpow(ap[2][0])) / P_rev_L)
    print(f"{name:40s} fixed: leak {fl:6.1f}  ambience {fr:6.1f}  ratio {fr-fl:+5.1f} dB | adaptive: leak {al:6.1f}  ambience {ar:6.1f}  ratio {ar-al:+5.1f} dB")
print("dB re the instrument (leak) and re the reverb (ambience) in the front L channel. ratio = wanted ambience minus unwanted instrument in the feed (higher is better).")
for label, mk in (("dense noise", dense), ("harmonic notes", sparse)):
    report(f"{label}: hard-left instrument", mk(1), 0.0)
    report(f"{label}: instrument panned 70% left", mk(4), 0.43)
    report(f"{label}: centre instrument", mk(7), 1.0)
t0 = time.time(); A.ambience(M.pink(FS*10, 1), M.pink(FS*10, 2)); print(f"cost: {time.time()-t0:.1f} s of numpy for 10 s of stereo")
