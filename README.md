# linux-theater-dsp

> **Part of the [Software Defined Home Theatre](https://github.com/praveenchandrahas/Software-Defined-Home-Theatre) project.** The main repository holds the documentation, build log, results and the installer checks; this is one of its parts. Sibling repositories: [mpv-object-audio](https://github.com/praveenchandrahas/mpv-object-audio) · [seekthumbs](https://github.com/praveenchandrahas/seekthumbs) · [theater-measurement](https://github.com/praveenchandrahas/theater-measurement).

**Stereo and 5.1 upmixer (to 5.1.2, with ceiling channels), PipeWire routing and a CamillaDSP room-correction profile generator** for a Linux software-defined home theatre. Written for one 5.1.2 rig (see "Adapting" below), but the upmixers (`scripts/upmix.py`, `scripts/upmix_engine.py`) are two small numpy-only files you can read and reuse on their own.

- **`eq`** (the `theater-route` command) watches PipeWire and keeps the right audio paths linked into CamillaDSP, and switches the profile by what is playing
  (`eq status`, `eq ensure`, `eq prepare FILE`, `eq source`, `eq engine on|off`, `eq flavour ...`).
- **`set-eq.py`** generates and loads the CamillaDSP configuration (bass EQ, delays, trims, crossovers, height bass management) for each profile: `film` (no upmix), `bed` (5.1 to 5.1.2),
  `stereo` (2.0 to 5.1.2, fixed or adaptive).
- **`upmix.py`** holds the fixed upmix presets as CamillaDSP mixer definitions; **`upmix_engine.py`** is the adaptive ambience engine (a PipeWire filter that steers the ambience and ceiling feeds by how
  correlated the stereo input is; about 4 % CPU and 21 ms by the author's measurement). The router starts and stops it while the adaptive stereo profile is active; without numpy and scipy it falls back to the fixed matrix.

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

| Path | What it is |
|---|---|
| `scripts/theater-route`, `set-eq.py`, `upmix.py`, `upmix_engine.py` | the router / `eq` command, the config generator, the upmixers |
| `scripts/install-autoroute.sh` | installs the above and the systemd units into `~/.local/bin` and `~/.config/systemd/user` (safe to re-run; this is also how you update) |
| `scripts/make-default.sh` | writes and loads the standing profile, installs the router, enables the services |
| `scripts/route-mpv.sh` | manual helper that links an mpv instance by hand |
| `configs/` | an example generated CamillaDSP config and the systemd unit files |
| `tools/upmixtest/` | offline checks that run the real CamillaDSP over synthetic noise (levels, correlations, decorrelator quality); see its README |
| `tests/` | router tests against a simulated PipeWire graph (`tests/fake-pw-link`), config-generation tests and engine tests; no hardware needed |

## Use

Needs Python 3 with PyYAML, numpy and scipy, PipeWire (`pw-link`) and [CamillaDSP](https://github.com/HEnquist/camilladsp).

```bash
git clone https://github.com/praveenchandrahas/linux-theater-dsp && cd linux-theater-dsp
tests/run.sh                    # 149 checks, no hardware
./scripts/make-default.sh       # writes and loads the standing profile, installs the router and `eq`, enables the services
```

## Adapting it to your system

Paths, user names, the PipeWire/ALSA names of the author's 7.1 USB interface (a Vantec), and every delay, trim and EQ value in `scripts/set-eq.py` are **from the author's machine and room**. Change them for yours:
the interface name in `set-eq.py` and the units, and the `ALIGN` / EQ tables after you have measured your own room.

The room numbers (per-speaker delay and trim, the height-speaker tone match and trim, the bass set) can be kept in one JSON file, `room.json`, instead of editing the tables:

```
./scripts/set-eq.py --dump-room > room.json                     # the built-in room (the author's) as a template
$EDITOR room.json                                               # change delays, trims, height tone, bass.base_set, bass.extra_filters
./scripts/set-eq.py --room=room.json --write-config=/tmp/proposed.yml   # build and check a config; nothing else is touched
./scripts/set-eq.py --room=room.json                            # build it and load it (the normal flow, with your numbers)
```

**Profile switches are gapless by default.** After writing the new config, `set-eq.py` sends CamillaDSP a SIGHUP so it re-reads it in place (no websocket, no change to the unit file). It then checks that the same process is still running with all 16 ports and exactly the same links; if anything differs it falls back to a full restart plus relinking, as before. `SETEQ_RELOAD=restart` forces the restart; `SETEQ_RELOAD_WAIT` (default 1.5 s) is how long it waits before checking.

`room.json` is plain JSON, strictly validated (channel names `FL FR FC LFE SL SR RL RR`; delay 0-20 ms, trim -20 to +6 dB, filter freq 20-20000 Hz, gain -24 to +6 dB, Q 0.3-12; unknown keys are rejected) and never executed. Keys you leave out keep the built-in values; a bad file exits with code 2 and changes nothing. `--write-config=PATH` validates with `camilladsp -c` when the binary exists, writes PATH and does nothing else (no copy to `~/.config`, no restart, no relinking). `tests/golden/` holds configs generated before this feature existed; `tests/run.sh` checks the default profile is still byte-identical.

## Licence

[Apache License 2.0](LICENSE) (see also [NOTICE](NOTICE)). Dolby, Dolby Atmos, DTS and DTS:X are trademarks of their owners; this project is not affiliated with or endorsed by them. It contains no media files and no decoder code.

Part of the [software-defined home theatre](https://github.com/praveenchandrahas/Software-Defined-Home-Theatre) project (documentation, measurements and the build log live there).

## Status and control page (theater-ctld)

`eq status --json` prints everything `eq status` knows as one JSON object (schema 1: `eq`, `dsp`, `apps`, `mpv`, `usb_up`); the text output is unchanged
(`tests/test_status.py` holds golden copies for nine situations).

`theater-ctld` is a small local server on `http://127.0.0.1:8765` (this computer only; there is no LAN option) with a dashboard page. Install it with
`./scripts/install-ctld.sh` (run `./scripts/install-autoroute.sh` first); `remove` undoes it. If it stops, audio is not affected.

- **Reads:** `eq status --json` (cached for about a second) plus CamillaDSP's websocket for load, buffer, clipped samples and peaks, and the number of
  "buffer empty" lines in CamillaDSP's journal over the last minute. The websocket needs `-p 1234 -a 127.0.0.1` in the CamillaDSP unit, see the
  runbook; without it the page says so and everything else still works. Only read-only websocket commands can be sent (enforced in code).
- **Actions:** a fixed table: `eq on|off`, `eq mode auto|film|stereo|bed`, `eq flavour stereo|bed NAME`, `eq engine on|off`. Arguments are checked against
  fixed lists and run without a shell. Setting what is already set does nothing. While something is playing, a profile change (about a second of silence)
  and `eq off` (louder) need an explicit confirmation. One action runs at a time. Room corrections are not applied from here; that stays in autocal.
- **Protection:** the page carries a random token (kept in `~/.local/state/theater/ctl-token`, mode 0600) that every action must send. Requests need a
  `Host` of 127.0.0.1 or localhost (DNS rebinding) and a same-origin `Origin`; no CORS headers are sent, so another web page in your browser cannot read
  or drive it. Every action is logged and shown as a desktop notification.
- **Tests:** `tests/test_ctld.py` (fake `eq`, fake CamillaDSP websocket).
- **Not done:** a LAN listener (for the phone), a bass-set control (the router forgets a hand-picked bass set at the next automatic switch), and
  an object count (needs the Omniphony OSC schema).
