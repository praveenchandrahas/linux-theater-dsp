"""End to end, offline: engine feeds + CamillaDSP stereo-ad config (real CamillaDSP), next to the fixed stereo config."""
import os, sys, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
import harness as H, metrics as M, upmix_engine as EN
import adaptive_eval as E
n = 48000 * 12
def frame8(L, R):
    F = EN.process_signal(L, R).astype(np.float64)
    x = np.zeros((len(L), 8)); x[:, 0], x[:, 1] = L, R
    x[:, 6], x[:, 7], x[:, 2], x[:, 3] = F[:, 0], F[:, 1], F[:, 2], F[:, 3]     # AUX0..3 -> inputs 7, 8, 3, 4
    return x
def levels(y, ref, label):
    yb = M.band(y[48000:48000 * 11]); lv = [M.rms_db(yb[:, c]) - ref for c in range(8)]
    print(label.ljust(34) + " ".join(f"{M.NAMES[c]}:{lv[c]:6.1f}" for c in range(8))); return yb
a, b, m = M.pink(n, 1), M.pink(n, 2), M.pink(n, 3)
ref = M.rms_db(M.band(a[48000:48000 * 11]))
for fl in ("balanced",):
    print(f"== {fl}   (levels re one input channel, 200 Hz-6 kHz)")
    for kind in ("stereo", "stereo-ad"):
        mk = (lambda L, R: np.c_[L, R]) if kind == "stereo" else frame8
        levels(H.run(mk(m, m), kind, fl, full=False, tag="z"), ref, f"{kind}: mono voice")
        yb = levels(H.run(mk(a, b), kind, fl, full=False, tag="z"), ref, f"{kind}: uncorrelated (diffuse)")
        sp, rv1, rv2 = E.sparse(1)[:n], M.pink(n, 5) * 0.316, M.pink(n, 6) * 0.316
        levels(H.run(mk(sp + rv1, rv2), kind, fl, full=False, tag="z"), ref, f"{kind}: hard-left notes + reverb")
# timing of the added feeds against the front, impulse through the whole chain (front L impulse vs engine feed delay)
imp = np.zeros(48000 * 2); imp[48000] = 1.0
x8 = np.zeros((len(imp), 8)); x8[:, 0] = imp
F = EN.process_signal(np.random.default_rng(4).standard_normal(len(imp)) * 0.1, np.random.default_rng(5).standard_normal(len(imp)) * 0.1)
print("\nengine delay of the ambience feeds vs the fronts: %.1f ms (+ CamillaDSP delays %s ms)" % (EN.LATENCY_SAMPLES / 48000 * 1000, __import__('upmix').AD_DELAYS['balanced']))
