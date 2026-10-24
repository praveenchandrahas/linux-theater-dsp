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
