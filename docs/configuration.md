# Configuration: adapting it to your system

Paths, user names, the PipeWire/ALSA names of the author's 7.1 USB interface (a Vantec), and every delay, trim and EQ value in `scripts/set-eq.py` are **from the author's own machine and room**. You'll need to change them for yours: the interface name in `set-eq.py` and the units, and the `ALIGN` / EQ tables after you have measured your own room.

## Room numbers (`room.json`)

The room numbers (per-speaker delay and trim, the height-speaker tone match and trim, the bass set) can be kept in one JSON file, `room.json`, instead of editing the tables directly:

```bash
./scripts/set-eq.py --dump-room > room.json                            # the built-in room (the author's) as a template
$EDITOR room.json                                                       # change delays, trims, height tone, bass.base_set, bass.extra_filters
./scripts/set-eq.py --room=room.json --write-config=/tmp/proposed.yml   # build and check a config; nothing else is touched
./scripts/set-eq.py --room=room.json                                    # build it and load it (the normal flow, with your numbers)
```

`room.json` is plain JSON, strictly validated (channel names `FL FR FC LFE SL SR RL RR`; delay 0-20 ms, trim -20 to +6 dB, filter freq 20-20000 Hz, gain -24 to +6 dB, Q 0.3-12; unknown keys are rejected) and never executed. Keys you leave out keep the built-in values; a bad file exits with code 2 and changes nothing.

`--write-config=PATH` validates with `camilladsp -c` when the binary exists, writes `PATH`, and does nothing else (no copy to `~/.config`, no restart, no relinking). `tests/golden/` holds configs generated before this feature existed; `tests/run.sh` checks that the default profile is still byte-identical.

## Your speaker layout

The router, `set-eq.py` and the upmixers all read one layout file (`~/.config/roomtone/layout.yml`, or `$ROOMTONE_LAYOUT`): which speakers exist, which interface port each is on, the sink name, and whether your amplifier does its own bass management. With no file, the built-in layout is the author's 5.1.2, and the generated CamillaDSP configs, router links and upmix filters are byte-identical to before (golden tests in `tests/golden/layout/`).

```bash
scripts/layout.py --detect                           # what PipeWire shows, and the preset it would propose (plays nothing)
scripts/layout.py --detect --device <sink> --write   # write that proposal
scripts/layout.py --init 7.1                          # or a plain preset: 2.0 2.1 5.1 5.1.2 7.1 7.1.2 7.1.4
scripts/layout.py --validate                          # say what is wrong with the file
scripts/set-eq.py --layout=FILE --write-config=/tmp/x.yml   # build a config for any layout without touching anything
```

`install-autoroute.sh` installs the layout module and a `roomtone-layout` command. The stereo and 5.1 upmixes are offered only for layouts with `FL FR FC LFE SL SR` plus exactly two height speakers (5.1.2, 7.1.2); otherwise `eq` says why. Every preset except 5.1.2 starts with neutral room numbers (zero delays and trims, no tone filters, flat bass set) until you measure.

The [Roomtone](https://github.com/praveenchandrahas/Roomtone) repository has the Layout page (identify each speaker with a quiet tone, preview, save with backup) and the full layout reference: [docs/layouts.md](https://github.com/praveenchandrahas/Roomtone/blob/main/docs/layouts.md).

**Tested how:** written with an AI assistant; checked against simulated rooms and REW exports; used and checked by the author in his own room (one room, one author). No external or second-person validation yet. Only the author's 5.1.2 layout has run on real hardware. Other layouts are tested by generating configs and router link sets and checking them (and `camilladsp -c` where it exists), not by listening.
