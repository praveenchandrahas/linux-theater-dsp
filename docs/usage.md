# Usage

Once installed (see [Install](install.md)), the day-to-day interface is the **`eq`** command (the `theater-route` script). It watches PipeWire and keeps mpv (and other apps) routed through CamillaDSP, switching profile based on what's playing.

## The `eq` command

- `eq status` / `eq status --json` — show what is happening right now (`--json` prints the same facts as one JSON object — schema 1: `eq`, `dsp`, `apps`, `mpv`, `usb_up` — for scripts and the status page; the text output is unchanged).
- `eq ensure` — start `camilladsp.service` and `theater-router.service` if they are not running (`mpv-atmos` calls this).
- `eq on` / `eq off` / `eq toggle` — EQ on means mpv -> CamillaDSP -> USB interface (bass EQ, delays, trims); EQ off means mpv -> USB interface directly, nothing from CamillaDSP at all.
- `eq mode [auto|film|stereo|bed]` — which CamillaDSP profile is used. `auto` (the default) picks it from what is playing: Chrome (or another app matching `THEATER_STEREO_APPS`) switches to the stereo upmix, patched into CamillaDSP; mpv with Atmos or DTS:X uses `film` (no upmix); mpv with a 5.1 track uses the `bed` upmix; mpv with a stereo track uses the `stereo` upmix; idle for a while goes back to `film`, so the next film starts clean.
- `eq flavour stereo|bed NAME` — flavour of the upmix. Stereo flavours: `voice`, `balanced`, `wide`. Bed flavours: `subtle`, `balanced`, `wide` (`stereo-ad` shares the stereo flavour).
- `eq engine [on|off]` — use the stereo upmix with the adaptive ambience engine (`scripts/upmix_engine.py`, on by default) or the fixed matrix instead. If the adaptive engine doesn't come up, the router falls back to the fixed matrix on its own.
- `eq source` — show what mpv is playing and how it is classified (useful for checking detection).
- `eq prepare FILE` — classify `FILE` with `ffprobe` and switch profile right away (`mpv-atmos` calls this before starting mpv).

The daemon (`theater-route daemon`, run by the systemd user service) checks PipeWire twice a second. Whenever mpv (or `mpv-atmos`) shows up, it links its channels to CamillaDSP and removes the direct route — "make before break" — so there's never a silent gap. If CamillaDSP is missing or half-ready, it leaves (or puts) mpv on the direct route instead. It also keeps CamillaDSP's outputs linked to the USB interface, since those links are lost every time CamillaDSP restarts.

## Profile switching

**Profile switches are gapless by default.** After writing a new config, `set-eq.py` sends CamillaDSP a `SIGHUP` so it re-reads the config in place (no websocket, no change to the unit file). It then checks that the same process is still running with all 16 ports and exactly the same links; if anything differs it falls back to a full restart plus relinking, as before. Set `SETEQ_RELOAD=restart` to force the restart, and `SETEQ_RELOAD_WAIT` (default 1.5 s) to change how long it waits before checking.

## Status and control page

`eq status --json` is meant to be read by other tools. A local control page (`theater-ctld`) and an mpv overlay that read this status and drive `eq` live in the [Roomtone](https://github.com/praveenchandrahas/Roomtone) repository (`gui/`, `overlay/`). Install `./scripts/install-autoroute.sh` here first so that `eq status --json` exists, then install those from the Roomtone repository.

For adapting the upmixers and room correction to your own speakers and room, see [Configuration](configuration.md).
