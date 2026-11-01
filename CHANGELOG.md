# Changelog

## [0.1.0] - 2026-11-01

First packaged pre-release. Experimental. The code on main at the time of tagging is packaged as it is.

- Debian package `linux-theater-dsp` (Architecture: all): the `eq` router, `set-eq.py`, the upmixers and the speaker-layout module, installed under /usr/lib/linux-theater-dsp with commands in /usr/bin and user systemd units in /usr/lib/systemd/user.
- `theater-setup` enables or disables the router for one user, with `--dry-run`, `uninstall` and a check for hand-installed copies in ~/.local/bin that would hide the packaged commands.
- The package scripts never enable or start a service, never write into a home folder and never touch CamillaDSP or PipeWire configuration.
- Configurable speaker layouts (layout.py, docs in the Roomtone repository) are in the code that was on main at tagging; they were written in the same week and have been tested in simulation only.
