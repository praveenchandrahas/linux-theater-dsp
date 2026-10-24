"""Fixed matrix vs adaptive ambience: instrument leak into the surround feed vs the reverb that should be there."""
import time, numpy as np
from scipy.signal import coherence
import metrics as M, adaptive as A
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
def bandpow(x): return np.mean(M.band(x[FS:]) ** 2)
def db(x): return 10 * np.log10(x + 1e-18)
def report(name, inst, pan_r, rev=0.316, **kw):
    rl, rr = M.pink(n, 2), M.pink(n, 3)
    Lc, Rc = inst + rev * rl, pan_r * inst + rev * rr
    z = np.zeros(n)
    parts = [(inst, pan_r * inst), (rev * rl, z), (z, rev * rr)]
    aL, aR, D, ap = A.ambience(Lc, Rc, apply=parts, **kw)
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
