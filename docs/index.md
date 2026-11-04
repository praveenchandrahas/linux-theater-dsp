# linux-theater-dsp

**Stereo and 5.1 upmixer (to 5.1.2, with ceiling channels), PipeWire routing and a CamillaDSP room-correction profile generator** for a Linux software-defined home theatre. It was written for one 5.1.2 rig (see [Configuration](configuration.md)), but the upmixers themselves (`scripts/upmix.py`, `scripts/upmix_engine.py`) are two small numpy-only files you can read and reuse on their own.

This repository is part of the [Software Defined Home Theatre](https://github.com/praveenchandrahas/Software-Defined-Home-Theatre) project. The main repository holds the documentation, build log, results and the installer checks; this repository is one of its parts. Sibling repositories:

- [mpv-object-audio](https://github.com/praveenchandrahas/mpv-object-audio) — player and Atmos wrapper
- [Roomtone](https://github.com/praveenchandrahas/Roomtone) — measurement, autocal, status page, mpv overlay
- [seekthumbs](https://github.com/praveenchandrahas/seekthumbs) — seek-bar thumbnails
- [mpv-shelf](https://github.com/praveenchandrahas/mpv-shelf) — film browser for mpv

## What's here

- **`eq`** (the `theater-route` command) watches PipeWire and keeps the right audio paths linked into CamillaDSP, and switches the profile by what is playing.
- **`set-eq.py`** generates and loads the CamillaDSP configuration (bass EQ, delays, trims, crossovers, height bass management) for each profile: `film` (no upmix), `bed` (5.1 to 5.1.2), `stereo` (2.0 to 5.1.2, fixed or adaptive).
- **`upmix.py`** holds the fixed upmix presets as CamillaDSP mixer definitions; **`upmix_engine.py`** is the adaptive ambience engine that steers the ambience and ceiling feeds by how correlated the stereo input is.

Start with [Install](install.md) to get the package on your machine, then [Usage](usage.md) for the day-to-day `eq` commands. If you want to run this on a different speaker layout or room than the author's, see [Configuration](configuration.md). [Design notes](design-notes.md) explains how this differs from EasyEffects, PipeWire's own upmix, and similar tools, and why it's built this way.

## Status

Pre-release and experimental. Written with an AI assistant; checked against simulated rooms and REW exports; used and checked by the author in his own room (one room, one author). No external or second-person validation yet. See [Install](install.md) for what exactly has and hasn't been tested.
