"""Adaptive ambience/direct separation for the upmix (offline prototype of the real-time engine).

Per time-frequency tile of a stereo signal: a smoothed 2x2 covariance gives the principal (direct) direction and a directness
D = (l1 - l2) / (l1 + l2). The direct part is the principal component weighted by D; what is left is the ambience.
The surrounds and heights are fed from the ambience only, so a hard-panned instrument no longer leaks to the rear the way the
fixed side-signal matrix does. The engine adds latency (about one STFT window), which is absorbed by the Haas delays of the
surrounds and heights; the fronts and the centre never go through it.
"""
import numpy as np
from scipy.signal import stft, istft, lfilter

FS = 48000


def _smooth(x, alpha, fbins):
    x = lfilter([1 - alpha], [1, -alpha], x, axis=1)             # time
    k = np.ones(fbins) / fbins
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 0, x)   # frequency


def ambience(L, R, n=1024, hop=256, alpha=0.85, fbins=5, q=0.4, f_lo=150.0, apply=()):
    """Returns (aL, aR, D): ambient parts of L and R (time domain, zero delay offline) and the directness map.
    apply: optional list of (L_i, R_i) signals that are run through the SAME mask (derived from L, R); their aL, aR are
    appended to the result as a list. That splits the output exactly into what each source contributes (for evaluation)."""
    f, t, XL = stft(L, FS, nperseg=n, noverlap=n - hop)
    _, _, XR = stft(R, FS, nperseg=n, noverlap=n - hop)
    a = _smooth(np.abs(XL) ** 2, alpha, fbins).real
    d = _smooth(np.abs(XR) ** 2, alpha, fbins).real
    b = _smooth(XL * np.conj(XR), alpha, fbins)
    disc = np.sqrt(((a - d) / 2) ** 2 + np.abs(b) ** 2)
    l1, l2 = (a + d) / 2 + disc, (a + d) / 2 - disc
    D = np.clip((l1 - l2) / (l1 + l2 + 1e-18), 0, 1)
    th = 0.5 * np.arctan2(2 * np.abs(b), a - d)
    ph = np.exp(-1j * np.angle(b))
    v1, v2 = np.cos(th), np.sin(th) * ph
    w = D ** q
    keep = (f >= f_lo)[:, None]
    cLL, cLR = (1 - w * v1 * v1) * keep, (-w * v1 * np.conj(v2)) * keep      # r_L = cLL XL + cLR XR
    cRL, cRR = (-w * v2 * v1) * keep, (1 - w * v2 * np.conj(v2)) * keep      # r_R = cRL XL + cRR XR
    def run(xl, xr):
        _, yl = istft(cLL * xl + cLR * xr, FS, nperseg=n, noverlap=n - hop)
        _, yr = istft(cRL * xl + cRR * xr, FS, nperseg=n, noverlap=n - hop)
        return yl, yr
    parts = []
    for pl, pr in apply:
        _, _, xl = stft(pl, FS, nperseg=n, noverlap=n - hop)
        _, _, xr = stft(pr, FS, nperseg=n, noverlap=n - hop)
        yl, yr = run(xl, xr)
        parts.append((yl[:len(L)], yr[:len(L)]))
    aL, aR = run(XL, XR)
    m = len(L)
    return (aL[:m], aR[:m], D) if not apply else (aL[:m], aR[:m], D, parts)
