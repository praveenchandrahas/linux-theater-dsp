# theater-router

The routing, DSP-profile and upmix layer of a Linux software-defined home theatre.

- **`eq`** (the `theater-route` command) watches PipeWire and keeps the right audio paths linked into CamillaDSP, and switches the profile by what is playing
  (`eq status`, `eq ensure`, `eq prepare FILE`, `eq source`, `eq engine on|off`, `eq flavour ...`).
- **`set-eq.py`** generates and loads the CamillaDSP configuration (bass EQ, delays, trims, crossovers, height bass management) for each profile: `film` (no upmix), `bed` (5.1 to 5.1.2),
  `stereo` (2.0 to 5.1.2, fixed or adaptive).
- **`upmix.py`** holds the fixed upmix presets as CamillaDSP mixer definitions; **`upmix_engine.py`** is the adaptive ambience engine (a PipeWire filter that steers the ambience and ceiling feeds by how
  correlated the stereo input is; about 4 % CPU and 21 ms by the author's measurement). The router starts and stops it while the adaptive stereo profile is active; without numpy and scipy it falls back to the fixed matrix.

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
git clone https://github.com/praveenchandrahas/theater-router && cd theater-router
tests/run.sh                    # 149 checks, no hardware
./scripts/make-default.sh       # writes and loads the standing profile, installs the router and `eq`, enables the services
```

## Adapting it to your system

Paths, user names, the PipeWire/ALSA names of the author's 7.1 USB interface (a Vantec), and every delay, trim and EQ value in `scripts/set-eq.py` are **from the author's machine and room**. Change them for yours:
the interface name in `set-eq.py` and the units, and the `ALIGN` / EQ tables after you have measured your own room.

## Licence

[Apache License 2.0](LICENSE) (see also [NOTICE](NOTICE)). Dolby, Dolby Atmos, DTS and DTS:X are trademarks of their owners; this project is not affiliated with or endorsed by them. It contains no media files and no decoder code.

Part of the [software-defined home theatre](https://github.com/praveenchandrahas/sdht) project (documentation, measurements and the build log live there).
