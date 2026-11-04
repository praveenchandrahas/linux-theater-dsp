# linux-theater-dsp

[![CI](https://github.com/praveenchandrahas/linux-theater-dsp/actions/workflows/ci.yml/badge.svg)](https://github.com/praveenchandrahas/linux-theater-dsp/actions/workflows/ci.yml) *(CI = unit tests, lint, and a package install/remove test in a clean Ubuntu 24.04 container. A green badge does not show the software works on a real rig.)*

> **Part of the [Software Defined Home Theatre](https://github.com/praveenchandrahas/Software-Defined-Home-Theatre) project.** The main repository holds the documentation, build log, results and the installer checks; this is one of its parts. Sibling repositories: [mpv-object-audio](https://github.com/praveenchandrahas/mpv-object-audio) (player and Atmos wrapper) · [Roomtone](https://github.com/praveenchandrahas/Roomtone) (measurement, autocal, status page, mpv overlay) · [seekthumbs](https://github.com/praveenchandrahas/seekthumbs) (seek-bar thumbnails) · [mpv-shelf](https://github.com/praveenchandrahas/mpv-shelf) (film browser for mpv).

**Full docs:** https://praveenchandrahas.github.io/linux-theater-dsp/ — install, usage, configuration (room.json/layout.py), and design notes vs. EasyEffects and PipeWire's upmix.

**Stereo and 5.1 upmixer (to 5.1.2, with ceiling channels), PipeWire routing and a CamillaDSP room-correction profile generator** for a Linux software-defined home theatre. Written for one 5.1.2 rig (see "Adapting" below), but the upmixers (`scripts/upmix.py`, `scripts/upmix_engine.py`) are two small numpy-only files you can read and reuse on their own.

- **`eq`** (the `theater-route` command) watches PipeWire and keeps the right audio paths linked into CamillaDSP, and switches the profile by what is playing
  (`eq status`, `eq ensure`, `eq prepare FILE`, `eq source`, `eq engine on|off`, `eq flavour ...`).
- **`set-eq.py`** generates and loads the CamillaDSP configuration (bass EQ, delays, trims, crossovers, height bass management) for each profile: `film` (no upmix), `bed` (5.1 to 5.1.2),
  `stereo` (2.0 to 5.1.2, fixed or adaptive).
- **`upmix.py`** holds the fixed upmix presets as CamillaDSP mixer definitions; **`upmix_engine.py`** is the adaptive ambience engine (a PipeWire filter that steers the ambience and ceiling feeds by how
  correlated the stereo input is; about 4 % CPU and 21 ms by the author's measurement). The router starts and stops it while the adaptive stereo profile is active; without numpy and scipy it falls back to the fixed matrix.

## Install (pre-release, experimental)

Releases are marked **pre-release** on the [releases page](https://github.com/praveenchandrahas/linux-theater-dsp/releases). Download the `.deb` and `SHA256SUMS` from one release, check, then install:

```sh
sha256sum -c --ignore-missing SHA256SUMS
sudo apt install ./linux-theater-dsp_0.1.0_all.deb
theater-setup --dry-run   # then: theater-setup install
```

Full install steps, what was checked, and running from a clone instead of the `.deb`: see [docs/install.md](https://praveenchandrahas.github.io/linux-theater-dsp/install/).

## How this differs from EasyEffects and other generic upmixers, and why this route

**What the common tools do, as far as I know.**
- **EasyEffects** is a PipeWire effects chain (equaliser, compressor, reverb, and so on). It is built around processing the stereo (or an existing multichannel) stream; it does not make a surround layout out of a stereo one, and it has no notion of ceiling speakers.
- **PipeWire's own upmix** (`channelmix.upmix`, with a `simple` or `psd` method and settings such as `lfe-cutoff` and `rear-delay`) can spread stereo into 5.1 or 7.1. It is a general-purpose, fixed mix for a standard layout, applied inside the sound server before any of your own processing.
- Player and hardware options (ffmpeg's `surround` filter, a receiver's Dolby Surround or DTS Neural:X) are either also fixed matrices for standard layouts or closed.

**What is different here, and why.**
1. **The target is not a standard layout.** The rig is 5.1 plus two ceiling speakers (5.1.2) behind a Z906, with different speakers at the front, the sides and the ceiling. Generic upmixers stop at 5.1 or 7.1. `upmix.py` produces 5.1.2: it shares the phantom centre with a real centre speaker, sends only the *side* signal (L minus R, band-limited, decorrelated, delayed 12 to 17 ms) to the surrounds, and feeds the heights from the same ambience, high-passed and delayed more. Mono material (a voice) gives no side signal, so nothing is thrown behind or above you.
2. **It sits in front of the room correction, not instead of it.** The upmix is written as CamillaDSP blocks, so everything after it (per-speaker delays measured with a mic, level trims, bass EQ, bass management for the heights, tone match) works on the result exactly as on a native Atmos feed. A generic upmixer in the sound server cannot know about those, and a room-corrected 8-channel chain cannot be bolted onto an effects plugin without redoing the routing.
3. **It is measurable.** The harness in `tools/upmixtest` scores an upmixer on synthetic signals where the right answer is known (an instrument panned into a mix with reverb): ambience kept in the surrounds minus instrument leaking into them, in dB. That is how the fixed and adaptive versions were compared, rather than by a general sense of "wider".
4. **An adaptive mode exists.** `upmix_engine.py` steers the ambience and ceiling feeds by how correlated the input is, which a fixed matrix (the only thing CamillaDSP can do on its own) cannot. If numpy or scipy is missing, it falls back to the fixed matrix.

**What it does not do, plainly.**
- It is a single-rig, single-seat design. It is not a plugin you drop in, and it has been tuned and measured in one room.
- Its evidence is synthetic signals plus listening, not a blind test on music; the "better than the fixed matrix" result is for the test items and says nothing yet about music in general.
- It does not replace object audio. Real Atmos and DTS:X go through the Omniphony player (`mpv-object-audio`); this is for stereo and 5.1 sources.
- If you have a plain 5.1 or 7.1 system, PipeWire's built-in upmix or a hardware decoder is simpler and probably enough.

Repository layout (what each script and folder is): [docs/install.md](https://praveenchandrahas.github.io/linux-theater-dsp/install/#repository-layout).

## Use

Needs Python 3 with PyYAML, numpy and scipy, PipeWire (`pw-link`) and [CamillaDSP](https://github.com/HEnquist/camilladsp).

```bash
git clone https://github.com/praveenchandrahas/linux-theater-dsp && cd linux-theater-dsp
tests/run.sh                    # 149 checks, no hardware
./scripts/make-default.sh       # writes and loads the standing profile, installs the router and `eq`, enables the services
```

The `eq` commands for day-to-day use (profiles, flavours, the adaptive engine, status) are documented in [docs/usage.md](https://praveenchandrahas.github.io/linux-theater-dsp/usage/).

## Adapting it to your system

Paths, user names, the PipeWire/ALSA names of the author's 7.1 USB interface (a Vantec), every delay/trim/EQ value in `scripts/set-eq.py`, and the speaker layout are **from the author's own machine and room**. Changing them for yours — the `room.json` room-correction file and the speaker-layout file — is covered in [docs/configuration.md](https://praveenchandrahas.github.io/linux-theater-dsp/configuration/).

## Licence

[Apache License 2.0](LICENSE) (see also [NOTICE](NOTICE)). Dolby, Dolby Atmos, DTS and DTS:X are trademarks of their owners; this project is not affiliated with or endorsed by them. It contains no media files and no decoder code.

Part of the [software-defined home theatre](https://github.com/praveenchandrahas/Software-Defined-Home-Theatre) project (documentation, measurements and the build log live there).

## Your layout

The router, `set-eq.py` and the upmixers read one layout file (`~/.config/roomtone/layout.yml`, or `$ROOMTONE_LAYOUT`) describing your speakers and interface; with no file the built-in layout is the author's 5.1.2. `scripts/layout.py --detect`, `--init`, and `--validate` help you build one. Full details: [docs/configuration.md](https://praveenchandrahas.github.io/linux-theater-dsp/configuration/).

## Status and control page

`eq status --json` prints everything `eq status` knows as one JSON object, for scripts and the status page. The local page (`theater-ctld`) and the mpv overlay that read it and drive `eq` now live in
[Roomtone](https://github.com/praveenchandrahas/Roomtone) (`gui/`, `overlay/`); install them from there (run `./scripts/install-autoroute.sh` here first, so `eq status --json` exists). See [docs/usage.md](https://praveenchandrahas.github.io/linux-theater-dsp/usage/) for the rest of the `eq` commands.
