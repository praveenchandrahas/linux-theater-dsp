#!/usr/bin/env python3
"""Real-time adaptive ambience engine for the stereo upmix (the signal-dependent part CamillaDSP cannot do).

What it does: per time-frequency tile of a stereo signal it separates direct sound (a source with a stable inter-channel
relationship: a voice, an instrument) from ambience (reverb, applause, room, anything uncorrelated between L and R), and outputs only
the ambience. CamillaDSP feeds it into the surrounds and heights (high-pass, decorrelation, Haas delay, bass management, EQ),
so a panned instrument no longer leaks to the rear and the ceiling gets a real diffuse field. Measured against the fixed side-signal
matrix: tools/upmixtest/README.md.

Streams (PipeWire, via pw-cat; this process only does DSP and pipes):
    input   node "theater-upmix-in"   2 channels  FL FR            <- the app / mpv, linked by the router
    output  node "theater-upmix-out"  4 channels  AUX0..AUX3       -> camilladsp-capture inputs 7, 8, 3, 4 (SL, SR, TL, TR)
            AUX0 = ambience of L, AUX1 = ambience of R, AUX2 = (AUX0 + AUX1)/sqrt2, AUX3 = (AUX0 - AUX1)/sqrt2 (ceiling feeds)

Latency: one STFT window (default 1024 samples, 21.3 ms) plus the pw-cat buffers. It applies only to these four feeds, which are meant to
arrive late anyway (Haas / precedence); the fronts and the centre never go through here, so lip-sync is untouched.

    upmix_engine.py run            run as a service (spawns pw-cat both ways)
    upmix_engine.py stdio          raw float32 stereo on stdin -> raw float32 4-channel on stdout (tests, offline use)
    upmix_engine.py bench          cost per hop against the real-time budget
"""
import os
import subprocess
import sys
import time

import numpy as np
from scipy.ndimage import uniform_filter1d

FS = 48000
N = int(os.environ.get("THEATER_ENGINE_N", "1024"))             # STFT window
HOP = N // 4
ALPHA = float(os.environ.get("THEATER_ENGINE_ALPHA", "0.85"))   # time smoothing of the covariance (per hop)
FBINS = 5                                                         # frequency smoothing (bins)
Q = float(os.environ.get("THEATER_ENGINE_Q", "0.4"))            # exponent on directness: lower subtracts more of the direct part
F_LO = 150.0                                                      # below this nothing is passed on (bass stays in the front channels)
LATENCY_SAMPLES = N                                               # algorithmic latency of the engine


class StereoAmbience:
    """Streaming STFT ambience extractor. Feed HOP samples of L and R at a time; get HOP samples of four feeds back,
    delayed by N samples."""

    def __init__(self, n=N, alpha=ALPHA, fbins=FBINS, q=Q, f_lo=F_LO, fs=FS):
        self.n, self.hop, self.alpha, self.fbins, self.q = n, n // 4, alpha, fbins, q
        k = np.arange(n)
        self.win = np.sqrt(0.5 * (1 - np.cos(2 * np.pi * k / n)))      # sqrt-hann: analysis x synthesis = hann, 75 % overlap sums to 2
        self.keep = (np.fft.rfftfreq(n, 1 / fs) >= f_lo).astype(np.float64)
        nb = n // 2 + 1
        self.buf = np.zeros((2, n))
        self.acc = np.zeros((2, n))
        self.cov = np.zeros((4, nb))                                     # smoothed |L|^2, |R|^2, Re(L R*), Im(L R*)
        self.nb = nb

    def coefficients(self, XL, XR):
        """Mask coefficients (cLL, cLR, cRL, cRR) with r_L = cLL XL + cLR XR, r_R = cRL XL + cRR XR; updates the smoothing state."""
        prod = XL * np.conj(XR)
        inst = np.stack([XL.real ** 2 + XL.imag ** 2, XR.real ** 2 + XR.imag ** 2, prod.real, prod.imag])
        inst = uniform_filter1d(inst, self.fbins, axis=1, mode="nearest")
        self.cov += (1 - self.alpha) * (inst - self.cov)
        a, d, br, bi = self.cov
        b = br + 1j * bi
        ab = np.abs(b)
        disc = np.sqrt(((a - d) / 2) ** 2 + ab ** 2)
        D = np.clip(disc * 2 / (a + d + 1e-18), 0, 1)                   # (l1 - l2) / (l1 + l2)
        th = 0.5 * np.arctan2(2 * ab, a - d)
        ph = np.exp(-1j * np.angle(b))
        v1, v2 = np.cos(th), np.sin(th) * ph
        w = D ** self.q
        keep = self.keep
        return ((1 - w * v1 * v1) * keep, (-w * v1 * np.conj(v2)) * keep,
                (-w * v2 * v1) * keep, (1 - w * v2 * np.conj(v2)) * keep)

    def process_hop(self, xl, xr):
        """xl, xr: HOP new samples. Returns (aL, aR): HOP completed samples of the ambience, delayed N samples."""
        n, hop = self.n, self.hop
        self.buf[:, :-hop] = self.buf[:, hop:]
        self.buf[0, -hop:], self.buf[1, -hop:] = xl, xr
        XL, XR = np.fft.rfft(self.buf[0] * self.win), np.fft.rfft(self.buf[1] * self.win)
        cLL, cLR, cRL, cRR = self.coefficients(XL, XR)
        self.acc[:, :-hop] = self.acc[:, hop:]
        self.acc[:, -hop:] = 0
        self.acc[0] += np.fft.irfft(cLL * XL + cLR * XR, n) * self.win * 0.5
        self.acc[1] += np.fft.irfft(cRL * XL + cRR * XR, n) * self.win * 0.5
        return self.acc[0, :hop].copy(), self.acc[1, :hop].copy()


def feeds(aL, aR):
    """The four output feeds from the ambience of L and R."""
    r = 2 ** -0.5
    return np.stack([aL, aR, (aL + aR) * r, (aL - aR) * r], axis=1).astype("<f4")


def process_signal(L, R, engine=None):
    """Offline: run whole signals through the streaming engine hop by hop. Returns an (n, 4) array of feeds that is DELAYED by
    N samples relative to the input (exactly as the real-time engine delivers it). Pads the tail so nothing is lost."""
    eng = engine or StereoAmbience()
    hop = eng.hop
    m = len(L)
    pad = (-m) % hop + eng.n
    L = np.concatenate([L, np.zeros(pad)])
    R = np.concatenate([R, np.zeros(pad)])
    out = np.zeros((len(L), 2))
    for i in range(0, len(L), hop):
        aL, aR = eng.process_hop(L[i:i + hop], R[i:i + hop])
        out[i:i + hop, 0], out[i:i + hop, 1] = aL, aR
    # a block completed after reading input up to T holds the ambience of [T - n, T - n + hop) and is written into the slot [T - hop, T):
    # delay n - hop. The real-time loop adds one hop of prefill, so the stream is delayed by n; do the same here.
    out = np.vstack([np.zeros((hop, 2)), out])[:m]
    return feeds(out[:, 0], out[:, 1])


def bench(seconds=20):
    eng = StereoAmbience()
    rng = np.random.default_rng(1)
    x = rng.standard_normal((2, int(FS * seconds))) * 0.1
    hop = eng.hop
    ts = []
    for i in range(0, x.shape[1] - hop, hop):
        t = time.perf_counter()
        feeds(*eng.process_hop(x[0, i:i + hop], x[1, i:i + hop]))
        ts.append(time.perf_counter() - t)
    ts = np.array(ts) * 1000
    budget = hop / FS * 1000
    print(f"hop {hop} samples = {budget:.2f} ms budget; per hop: mean {ts.mean():.3f} ms, p99 {np.percentile(ts, 99):.3f} ms, max {ts.max():.3f} ms"
          f"  -> {ts.mean() / budget * 100:.1f} % of one core on average, worst hop {ts.max() / budget * 100:.0f} % of the budget")


def stdio_loop(rd, wr, engine=None):
    eng = engine or StereoAmbience()
    hop = eng.hop
    nbytes = hop * 2 * 4
    buf = bytearray(nbytes)
    view = memoryview(buf)
    wr.write(np.zeros((hop, 4), "<f4").tobytes())                      # prefill one hop: a cushion so the playback side never starves (sets latency to exactly N)
    wr.flush()
    while True:
        got = 0
        while got < nbytes:
            r = rd.readinto(view[got:])
            if not r:
                return
            got += r
        x = np.frombuffer(buf, dtype="<f4").reshape(hop, 2).astype(np.float64)
        wr.write(feeds(*eng.process_hop(x[:, 0], x[:, 1])).tobytes())
        wr.flush()


def pw_cat_commands(latency="10ms"):
    base = ["pw-cat", "--raw", "--rate", str(FS), "--format", "f32", "--latency", latency]
    rec = base[:1] + ["--record"] + base[1:] + ["--channels", "2", "--channel-map", "FL,FR",
          "-P", "{ node.name = theater-upmix-in node.autoconnect = false node.dont-reconnect = true media.role = DSP }", "-"]
    play = base[:1] + ["--playback"] + base[1:] + ["--channels", "4", "--channel-map", "AUX0,AUX1,AUX2,AUX3",
          "-P", "{ node.name = theater-upmix-out node.autoconnect = false node.dont-reconnect = true media.role = DSP }", "-"]
    return rec, play


def run():
    try:                                                                # best effort: realtime priority, then a better nice value
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(20))
    except (OSError, AttributeError, PermissionError):
        try:
            os.nice(-10)
        except OSError:
            pass
    rec_cmd, play_cmd = pw_cat_commands(os.environ.get("THEATER_ENGINE_LATENCY", "10ms"))
    rec = subprocess.Popen(rec_cmd, stdout=subprocess.PIPE, bufsize=0)
    play = subprocess.Popen(play_cmd, stdin=subprocess.PIPE, bufsize=0)
    print("theater-upmix running", flush=True)
    try:
        stdio_loop(rec.stdout, play.stdin)
    finally:
        for p in (rec, play):
            try:
                p.terminate()
            except OSError:
                pass
    sys.exit(1 if rec.poll() not in (None, 0) else 0)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        run()
    elif cmd == "stdio":
        stdio_loop(sys.stdin.buffer, sys.stdout.buffer)
    elif cmd == "bench":
        bench()
    else:
        print(__doc__)
        sys.exit(1)
