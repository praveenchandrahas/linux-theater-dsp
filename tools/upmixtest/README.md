# upmixtest: offline checks of the upmix presets

Runs the *real* CamillaDSP (WavFile in, raw File out; the release binary has no PipeWire backend, so the head is replaced)
over synthetic pink noise and prints the level and correlation of every output channel. Needs `camilladsp` on PATH
(or `CAMILLADSP=/path`), numpy, scipy. Run from this directory, scratch files are written here.

    python3 run_levels.py     # levels relative to one input channel, 200 Hz-6 kHz; correlations
    python3 decor_eval.py     # how far the decorrelators really decorrelate (band-wise cross-correlation, +-1 ms)

Findings that shaped the presets (2026-10-24):
- A decorrelator made by Gerchberg-Saxton iteration was 0.95-0.99 correlated with its source below 2 kHz, i.e. a plain delay.
  Magnitude-squared coherence cannot show this (two LTI copies of one source are always coherent); use the cross-correlation.
- The group-delay construction in upmix.py gives ~0.1 against the source and 0.2-0.3 between channel pairs.
- Centre extraction from M = (L+R)/2 makes uncorrelated L/R anti-correlated (about -0.4 at c = 0.40) and pulls hard-panned
  sources into the centre. That is inherent to a fixed matrix, so the centre share is kept modest.

## Adaptive ambience (prototype, not yet in the signal path)
`adaptive.py` separates direct sound from ambience per time-frequency tile (smoothed 2x2 covariance, principal direction, directness D).
`adaptive_eval.py` / `adaptive_scan.py` compare it with the fixed side-signal matrix by running the mixture-derived mask separately over the
instrument and the reverb, so leak and retained ambience are exact. Results (2026-10-24, q=0.4, alpha=0.85):

| Stimulus | Fixed S=(L-R)/2: instrument leak / ambience | Adaptive |
|----------|------------------------------------------|----------|
| harmonic notes, hard left | -6.0 / -2.4 dB (ratio +3.6) | -28 / -7 dB (ratio +21) |
| harmonic notes, 70% left | -10.9 / -2.4 (+8.5) | about -29 / -7 (+22) |
| harmonic notes, centre | cancelled exactly | -29 / -2 (+27) |
| dense noise, hard left (worst case) | -6.0 / -2.4 (+3.6) | -18 / -14 (+4.0), no gain |

Adaptive wins where the instrument is spectrally sparse (real music and speech) and gains nothing on noise-like sources; it also gives up the exact
cancellation of a centred source. It costs about 4-5 dB of ambience level (make-up gain) and about one STFT window of latency (~21 ms at n=1024), which is
acceptable only on the surround/height feeds (Haas delay absorbs it), never on the fronts or centre.
