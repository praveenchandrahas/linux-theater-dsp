"""Tests for scripts/upmix_engine.py (the adaptive ambience engine). Run: python3 tests/test_engine.py   (needs numpy, scipy)"""
import io
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import upmix_engine as E

ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(("PASS" if cond else "FAIL"), name, detail)


FS = E.FS
rng = np.random.default_rng(7)
n = FS * 4
L, R = rng.standard_normal(n) * 0.1, rng.standard_normal(n) * 0.1


def db(x):
    return 10 * np.log10(np.mean(x ** 2) + 1e-20)


F = E.process_signal(L, R)
x = np.correlate(F[:20000, 0].astype(float), L[:20000], "full")
lag = int(np.argmax(np.abs(x))) - 19999
check("engine latency is exactly one STFT window", lag == E.LATENCY_SAMPLES, f"({lag} samples, {lag / FS * 1000:.1f} ms)")
check("feeds are 4 channels float32", F.shape == (n, 4) and F.dtype == np.dtype("<f4"))

s = rng.standard_normal(n) * 0.1
Fm = E.process_signal(s, s)
check("mono signal (a centred voice) gives no ambience feed", db(Fm[FS:, :2]) < db(s) - 40, f"({db(Fm[FS:, :2]) - db(s):.0f} dB re input)")
check("uncorrelated L/R (diffuse) passes at close to full level above the cut-off",
      db(F[FS:, 0]) > db(L) - 8, f"({db(F[FS:, 0]) - db(L):.1f} dB re input, includes the 150 Hz high-pass)")
check("the two ceiling feeds are the sum and difference of the ambience", np.allclose(F[:, 2], (F[:, 0] + F[:, 1]) * 2 ** -0.5, atol=1e-6)
      and np.allclose(F[:, 3], (F[:, 0] - F[:, 1]) * 2 ** -0.5, atol=1e-6))

# bass is not passed on (it stays in the front channels)
b = np.sin(2 * np.pi * 60 * np.arange(n) / FS) * 0.3
Fb = E.process_signal(b, -b)
check("a 60 Hz out-of-phase tone is not sent to the ambience feeds", db(Fb[FS:, 0]) < db(b) - 40, f"({db(Fb[FS:, 0]) - db(b):.0f} dB)")

# stdio pipeline equals the offline path (what the service does with pw-cat's pipes)
m = FS // 2
inp = np.stack([L[:m], R[:m]], axis=1).astype("<f4")
inp = inp[: (len(inp) // E.HOP) * E.HOP]
rd, wr = io.BytesIO(inp.tobytes()), io.BytesIO()
E.stdio_loop(rd, wr)
got = np.frombuffer(wr.getvalue(), dtype="<f4").reshape(-1, 4)
ref = E.process_signal(inp[:, 0].astype(float), inp[:, 1].astype(float))
lead = E.HOP                                                 # the loop writes one hop of prefill first, process_signal does the same shift
k = min(len(got), len(ref))
check("stdio loop output equals the offline engine (same latency, same samples)",
      np.allclose(got[lead:k], ref[lead:k], atol=2e-5) and len(got) == len(inp) + E.HOP, f"({len(got)} frames out for {len(inp)} in)")

# real-time budget
import time
eng = E.StereoAmbience()
x2 = rng.standard_normal((2, FS * 3)) * 0.1
ts = []
for i in range(0, x2.shape[1] - E.HOP, E.HOP):
    t = time.perf_counter(); E.feeds(*eng.process_hop(x2[0, i:i + E.HOP], x2[1, i:i + E.HOP])); ts.append(time.perf_counter() - t)
budget = E.HOP / FS
check("average cost per hop is below 25 % of the real-time budget", np.mean(ts) < 0.25 * budget, f"({np.mean(ts) / budget * 100:.1f} %, worst {max(ts) / budget * 100:.0f} %)")

mode = E.rt_setup()
check("rt_setup returns a description and never raises", isinstance(mode, str) and mode, f"({mode})")
pw_rec, pw_play = E.pw_cat_commands()
check("pw-cat commands: 2-channel FL,FR capture and 4-channel AUX0-3 playback with fixed node names",
      "FL,FR" in pw_rec and "AUX0,AUX1,AUX2,AUX3" in pw_play and any("theater-upmix-in" in a for a in pw_rec) and any("theater-upmix-out" in a for a in pw_play))
print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
