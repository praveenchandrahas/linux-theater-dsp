# Install

Releases are marked **pre-release** on the [releases page](https://github.com/praveenchandrahas/linux-theater-dsp/releases). Download the `.deb` and `SHA256SUMS` from one release, check, then install:

```sh
sha256sum -c --ignore-missing SHA256SUMS
sudo apt install ./linux-theater-dsp_0.1.0_all.deb
theater-setup --dry-run   # then: theater-setup install
```

Needs PipeWire and Python 3; CamillaDSP itself is not packaged (the main repository's `install.sh` fetches the real release and checks its checksum).

The package puts files under `/usr` only. Its install and remove scripts do not enable or start services, do not write into any home folder, and do not touch CamillaDSP or PipeWire configuration; the `theater-setup` command above does the per-user part, and `--dry-run` shows what it would do first. Details, the other repositories' packages, and the one-command installer are in the main repository's [packaging notes](https://github.com/praveenchandrahas/Software-Defined-Home-Theatre/blob/main/docs/packaging.md).

## What was checked

Written with an AI assistant; checked against simulated rooms and REW exports; used and checked by the author in his own room (one room, one author). No external or second-person validation yet. The packages are unsigned. CI installs and removes them in a clean Ubuntu 24.04 container; the packaging itself has not been run on the author's own rig.

## Running from a clone instead

You don't need the `.deb` to try it out or to run the test suite. Needs Python 3 with PyYAML, numpy and scipy, PipeWire (`pw-link`) and [CamillaDSP](https://github.com/HEnquist/camilladsp).

```bash
git clone https://github.com/praveenchandrahas/linux-theater-dsp && cd linux-theater-dsp
tests/run.sh                    # 149 checks, no hardware
./scripts/make-default.sh       # writes and loads the standing profile, installs the router and `eq`, enables the services
```

## Repository layout

| Path | What it is |
|---|---|
| `scripts/theater-route`, `set-eq.py`, `upmix.py`, `upmix_engine.py` | the router / `eq` command, the config generator, the upmixers |
| `scripts/install-autoroute.sh` | installs the above and the systemd units into `~/.local/bin` and `~/.config/systemd/user` (safe to re-run; this is also how you update) |
| `scripts/make-default.sh` | writes and loads the standing profile, installs the router, enables the services |
| `scripts/route-mpv.sh` | manual helper that links an mpv instance by hand |
| `configs/` | an example generated CamillaDSP config and the systemd unit files |
| `tools/upmixtest/` | offline checks that run the real CamillaDSP over synthetic noise (levels, correlations, decorrelator quality); see its README |
| `tests/` | router tests against a simulated PipeWire graph (`tests/fake-pw-link`), config-generation tests and engine tests; no hardware needed |

Next: [Usage](usage.md) for the `eq` commands, or [Configuration](configuration.md) if your speakers or room aren't the author's 5.1.2 setup.
