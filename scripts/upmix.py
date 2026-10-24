"""Upmix presets for the CamillaDSP chain (used by set-eq.py --upmix=...). Pure static DSP: mixers, filters, delays, FIR.

Two jobs, both written so that every later stage of the standing profile (bass EQ, alignment, heights bass management,
tone match) works on the result exactly as it does on Atmos from mpv:

  stereo   2.0 in (FL FR), 5.1.2 out. For YouTube in Chrome and other stereo sources.
             centre    the phantom centre above 150 Hz (M = (L+R)/2) is shared between a real centre speaker and L/R, so
                       speech sits on the screen. Bass stays in L/R untouched (the Z906 sends it to the sub).
             surrounds the side signal S = (L-R)/2, band-limited (200 Hz - 9 kHz), decorrelated by an all-pass FIR, delayed
                       12-17 ms (Haas / precedence effect: fused with the front image, no echo)
             heights   the same side signal (plus an optional bit of M), high-passed at 300 Hz, decorrelated, delayed 20-30 ms
             Mono material (a voice) has S = 0, so nothing is thrown to the rear or the ceiling.
  bed      5.1 in (FL FR FC LFE SL SR, heights empty), 5.1.2 out, for DTS-HD MA / TrueHD / FLAC 5.1 films.
             heights   decorrelated, delayed ambience made from SL/SR and the front side signal. Dialogue (FC) never goes up.

CamillaDSP cannot steer adaptively (it has no signal-dependent matrix), so this is a fixed matrix. That is its limit:
a hard-panned instrument leaks into the surrounds at the S level, and nothing detects a transient and moves it.
The levels are therefore deliberately conservative, in three flavours per job, so you can A/B them by ear.
"""
import os
import numpy as np

FS = 48000
IR_TAPS = 2048

# c      share of the phantom centre moved to the real centre speaker (0 = none, 1 = all)
# cg     centre gain relative to M. 2*c keeps the coherent sum of the three speakers equal to the original for mono material
# sur_db surround level for a fully uncorrelated stereo signal, relative to each front channel (dB)
# sur_d  delays of SL, SR (ms) before the standing profile's own alignment
# h_db   height level, same definition; hm = extra mono (M) share in the heights, relative to the side signal
# h_d    delays of the heights (ms)
STEREO = {
    "voice":    dict(c=0.65, sur_db=-12.0, sur_d=(10.0, 14.0), h_db=-16.0, h_d=(18.0, 22.0), hm=0.0),
    "balanced": dict(c=0.40, sur_db=-6.0,  sur_d=(12.0, 17.0), h_db=-10.0, h_d=(20.0, 25.0), hm=0.0),
    "wide":     dict(c=0.25, sur_db=-3.0,  sur_d=(14.0, 19.0), h_db=-6.0,  h_d=(24.0, 30.0), hm=0.35),
}
# h_db   height level relative to the surround it is made from (dB); fm = share of the front side signal (L-R) added
BED = {
    "subtle":   dict(h_db=-12.0, fm=0.35, h_d=(18.0, 22.0)),
    "balanced": dict(h_db=-9.0,  fm=0.50, h_d=(20.0, 25.0)),
    "wide":     dict(h_db=-6.0,  fm=0.70, h_d=(22.0, 28.0)),
}
DEFAULT_FLAVOUR = {"stereo": "balanced", "stereo-ad": "balanced", "bed": "balanced"}

# stereo-ad: same flavours as stereo, but the surround and height feeds are the ambience made by scripts/upmix_engine.py
# (an external process, linked in by the router). The engine adds ~21 ms plus buffers, so the Haas delays here are only the remainder.
# AD_MAKEUP_DB compensates the ambience the mask removes (measured -2..-7 dB on music, tools/upmixtest/README.md).
AD_MAKEUP_DB = 4.0
AD_DELAYS = {"voice": ((0.0, 2.0), (2.0, 5.0)), "balanced": ((0.0, 3.0), (2.0, 6.0)), "wide": ((1.0, 5.0), (4.0, 9.0))}
KINDS = ("stereo", "stereo-ad", "bed")

CENTRE_HP = 150.0
SUR_HP, SUR_LP = 200.0, 9000.0
HEIGHT_HP = 300.0


def lin(db):
    return 10 ** (db / 20.0)


def decorrelator(seed, taps=IR_TAPS, tau_ms=20.0, corr_hz=60.0):
    """Flat-magnitude FIR (all-pass) whose group delay wanders randomly between 0 and tau_ms.
    Phase is the integral of a smooth random group-delay curve, so magnitude is exactly flat and the energy is
    spread over roughly 0.6*tau_ms. Measured: against its own source the correlation is ~0.1 (a plain delay is 1.0),
    and the chosen seed pairs are 0.2-0.3 correlated with each other (see tools/upmixtest)."""
    rng = np.random.default_rng(seed)
    N = 4 * taps
    f = np.fft.rfftfreq(N, 1 / FS)
    g = rng.standard_normal(len(f))
    k = max(3, int(corr_hz / f[1]))
    g = np.convolve(g, np.hanning(k) / np.hanning(k).sum(), mode="same")
    g = (g - g.min()) / (g.max() - g.min()) * (tau_ms / 1000.0)
    H = np.exp(-2j * np.pi * np.cumsum(g) * f[1])
    H[0] = 1
    H[-1] = 1
    h = np.fft.irfft(H)[:taps]
    return h * np.hanning(2 * taps)[taps:] ** 0.25


# (seed, tau_ms); pairs picked by searching 24 seeds for the lowest inter-channel correlation
IR_SEEDS = {"tl": (100, 30.0), "tr": (101, 30.0), "sl": (100, 20.0), "sr": (120, 20.0)}


def write_irs(irdir):
    """Writes the four decorrelators as raw float32 files (deterministic). Returns {name: path}."""
    os.makedirs(irdir, exist_ok=True)
    paths = {}
    for name, (seed, tau) in IR_SEEDS.items():
        p = os.path.join(irdir, f"decor_{name}.f32")
        decorrelator(seed, tau_ms=tau).astype("<f4").tofile(p)
        paths[name] = p
    return paths


def _mixer(name, nin, nout, mapping):
    """mapping: {dest: [(src, linear coefficient), ...]}; a destination with no sources is silence."""
    y = f"  {name}:\n    channels: {{in: {nin}, out: {nout}}}\n    mapping:\n"
    for d in range(nout):
        src = [(s, c) for s, c in mapping.get(d, []) if abs(c) > 1e-9]
        y += f"      - dest: {d}\n"
        if not src:
            y += "        sources: []\n"
            continue
        y += "        sources:\n"
        for s, c in src:
            y += f"          - {{channel: {s}, gain: {c:.6f}, scale: linear}}\n"
    return y


def _filter(name, type_, **params):
    p = ", ".join(f"{k}: {v}" for k, v in params.items())
    return f"  {name}:\n    type: {type_}\n    parameters: {{{p}}}\n"


def _step(channels, names):
    return f"  - type: Filter\n    channels: {channels}\n    names:\n" + "".join(f"      - {n}\n" for n in names)


def _bw(name, kind, freq, order=2):
    return _filter(name, "BiquadCombo", type=f"Butterworth{kind}", freq=freq, order=order)


def _conv(name, path):
    return f"  {name}:\n    type: Conv\n    parameters: {{type: Raw, filename: \"{path}\", format: F32_LE}}\n"


def _delay(name, ms):
    return _filter(name, "Delay", delay=ms, unit="ms", subsample="false")


def blocks(kind, flavour, irdir):
    """Returns (filters_yaml, mixers_yaml, steps_yaml) for the upmix stage, to be placed first in the pipeline."""
    table = BED if kind == "bed" else STEREO
    if flavour is None:
        flavour = DEFAULT_FLAVOUR[kind]
    if flavour not in table:
        raise ValueError(f"unknown {kind} flavour '{flavour}' (choose from {', '.join(table)})")
    P = table[flavour]
    ir = write_irs(irdir)
    f, m, s = "", "", ""
    if kind in ("stereo", "stereo-ad"):
        c, cg = P["c"], 2 * P["c"]
        gs = 2 ** 0.5 * lin(P["sur_db"])           # surround = gs * S, S = (L-R)/2
        hg = 2 ** 0.5 * lin(P["h_db"])
        hm = P["hm"]
        if kind == "stereo-ad":
            gsa, hga = lin(P["sur_db"] + AD_MAKEUP_DB), lin(P["h_db"] + AD_MAKEUP_DB)
            m += _mixer("up_in", 8, 8, {
                0: [(0, 1.0)], 1: [(1, 1.0)], 4: [(0, 0.5), (1, 0.5)],
                6: [(6, gsa)], 7: [(7, gsa)],                          # engine feeds AUX0/AUX1 (ambience of L, R) arrive on inputs 7, 8
                2: [(2, hga)], 3: [(3, hga)],                          # AUX2/AUX3 (ceiling feeds) arrive on inputs 3, 4
            })
            P = dict(P, sur_d=AD_DELAYS[flavour][0], h_d=AD_DELAYS[flavour][1])
        else:
            m += _mixer("up_in", 8, 8, {
                0: [(0, 1.0)], 1: [(1, 1.0)],
                2: [(0, hg / 2 * (1 + hm)), (1, hg / 2 * (-1 + hm))],      # TL source = hg*(S + hm*M)
                3: [(0, hg / 2 * (-1 + hm)), (1, hg / 2 * (1 + hm))],      # TR source = hg*(-S + hm*M)
                4: [(0, 0.5), (1, 0.5)],                                   # M
                6: [(0, gs / 2), (1, -gs / 2)],                            # SL source = gs*S
                7: [(0, -gs / 2), (1, gs / 2)],                            # SR source = -gs*S
            })
        m += _mixer("up_out", 8, 8, {
            0: [(0, 1.0), (4, -c)], 1: [(1, 1.0), (4, -c)],
            2: [(2, 1.0)], 3: [(3, 1.0)], 4: [(4, cg)], 5: [], 6: [(6, 1.0)], 7: [(7, 1.0)],
        })
        f += _bw("up_hp_m", "Highpass", CENTRE_HP)
        f += _bw("up_s_hp", "Highpass", SUR_HP) + _bw("up_s_lp", "Lowpass", SUR_LP)
        f += _bw("up_h_hp", "Highpass", HEIGHT_HP)
        f += _conv("up_dec_sl", ir["sl"]) + _conv("up_dec_sr", ir["sr"]) + _conv("up_dec_tl", ir["tl"]) + _conv("up_dec_tr", ir["tr"])
        f += _delay("up_dly_sl", P["sur_d"][0]) + _delay("up_dly_sr", P["sur_d"][1])
        f += _delay("up_dly_tl", P["h_d"][0]) + _delay("up_dly_tr", P["h_d"][1])
        s += "  - type: Mixer\n    name: up_in\n"
        s += _step([4], ["up_hp_m"])
        s += _step([6], ["up_s_hp", "up_s_lp", "up_dec_sl", "up_dly_sl"])
        s += _step([7], ["up_s_hp", "up_s_lp", "up_dec_sr", "up_dly_sr"])
        s += _step([2], ["up_h_hp", "up_dec_tl", "up_dly_tl"])
        s += _step([3], ["up_h_hp", "up_dec_tr", "up_dly_tr"])
        s += "  - type: Mixer\n    name: up_out\n"
    else:
        a = lin(P["h_db"])
        b = a * P["fm"] * 2 ** -0.5                  # (L-R)/sqrt2 has the power of one front channel for uncorrelated signals
        keep = {0: [(0, 1.0)], 1: [(1, 1.0)], 4: [(4, 1.0)], 5: [(5, 1.0)], 6: [(6, 1.0)], 7: [(7, 1.0)]}
        keep[2] = [(6, a), (0, b), (1, -b)]          # TL source = a*SL + b*(L-R)
        keep[3] = [(7, a), (1, b), (0, -b)]          # TR source = a*SR + b*(R-L)
        m += _mixer("up_in", 8, 8, keep)
        f += _bw("up_h_hp", "Highpass", HEIGHT_HP)
        f += _conv("up_dec_tl", ir["tl"]) + _conv("up_dec_tr", ir["tr"])
        f += _delay("up_dly_tl", P["h_d"][0]) + _delay("up_dly_tr", P["h_d"][1])
        s += "  - type: Mixer\n    name: up_in\n"
        s += _step([2], ["up_h_hp", "up_dec_tl", "up_dly_tl"])
        s += _step([3], ["up_h_hp", "up_dec_tr", "up_dly_tr"])
    return f, m, s


def describe(kind, flavour):
    flavour = flavour or DEFAULT_FLAVOUR[kind]
    P = (BED if kind == "bed" else STEREO)[flavour]
    if kind == "stereo-ad":
        return (f"Upmix stereo -> 5.1.2, adaptive ({flavour}): centre takes {P['c']:.0%} of the phantom centre above {CENTRE_HP:g} Hz; surrounds and "
                f"heights carry only the ambience made by upmix_engine.py (about 21 ms engine latency), {P['sur_db']:+.0f} / {P['h_db']:+.0f} dB, decorrelated")
    if kind == "stereo":
        return (f"Upmix stereo -> 5.1.2 ({flavour}): centre takes {P['c']:.0%} of the phantom centre above {CENTRE_HP:g} Hz; "
                f"surrounds {P['sur_db']:+.0f} dB (delays {P['sur_d'][0]:g}/{P['sur_d'][1]:g} ms), heights {P['h_db']:+.0f} dB "
                f"(delays {P['h_d'][0]:g}/{P['h_d'][1]:g} ms); decorrelated")
    return (f"Upmix 5.1 -> 5.1.2 ({flavour}): heights from SL/SR {P['h_db']:+.0f} dB plus {P['fm']:.0%} front side signal, decorrelated, "
            f"delays {P['h_d'][0]:g}/{P['h_d'][1]:g} ms; dialogue stays in front")
