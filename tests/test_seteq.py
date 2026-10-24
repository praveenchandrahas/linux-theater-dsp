"""Tests for scripts/set-eq.py config generation (no CamillaDSP needed).
Run:  python3 tests/test_seteq.py        (needs PyYAML)
"""
import importlib.util
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("seteq", os.path.join(HERE, "..", "scripts", "set-eq.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
ok = True


def check(name, cond):
    global ok
    ok &= bool(cond)
    print(("PASS" if cond else "FAIL"), name)


def used_names(doc):
    return [n for step in doc["pipeline"] for n in step.get("names", [])]


for key, fset in S.FILTER_SETS.items():
    doc = yaml.safe_load(S.build_config([(n, f, g, q) for n, f, g, q in fset]))
    defined = set(doc["filters"])
    check(f"{key}: every used filter is defined, all are cuts", set(used_names(doc)) <= defined
          and all(v["parameters"]["gain"] <= 0 for v in doc["filters"].values()))

drone2 = [(n, f, g, q) for n, f, g, q in S.FILTER_SETS["drone2"]]
plain = yaml.safe_load(S.build_config(drone2))
check("EQ step covers FL FR FC LFE SL SR only (heights 2,3 untouched)", plain["pipeline"][0]["channels"] == [0, 1, 4, 5, 6, 7])
check("devices: 8-channel PipeWire capture/playback named camilladsp-*",
      plain["devices"]["capture"]["node_name"] == "camilladsp-capture" and plain["devices"]["playback"]["channels"] == 8)

bed = yaml.safe_load(S.build_config(drone2, align="bed"))
delay_ch = sorted(int(k.split("_")[-1]) for k, v in bed["filters"].items() if v["type"] == "Delay")
gain_ch = sorted(int(k.split("_")[-1]) for k, v in bed["filters"].items() if k.startswith("al_gain"))
check("--align=bed: delays on FL FC LFE SL SR, none on FR (reference) or heights", delay_ch == [0, 4, 5, 6, 7])
check("--align=bed: trims on FR FC SL SR", gain_ch == [1, 4, 6, 7])
full = yaml.safe_load(S.build_config(drone2, align="all"))
check("--align: heights get delays too", {2, 3} <= {int(k.split("_")[-1]) for k, v in full["filters"].items() if v["type"] == "Delay"})
inv = yaml.safe_load(S.build_config(drone2, invert=["FC"]))
check("--invert=FC: one inverted gain on channel 4", inv["filters"]["inv_4"]["parameters"]["inverted"] is True)
check("no flags: output identical to a plain EQ config (no align filters)", not any(k.startswith("al_") for k in plain["filters"]))

# standing profile: no-argument default and the heights bass management
h = yaml.safe_load(S.build_config(drone2, align="all", heights={"hp": 140, "lfe_gain": 0.0, "tone": True}))
check("heights profile: every pipeline filter/mixer reference is defined",
      all(set(st["names"]) <= set(h["filters"]) for st in h["pipeline"] if st["type"] == "Filter")
      and all(st["name"] in h["mixers"] for st in h["pipeline"] if st["type"] == "Mixer"))
check("heights profile: mixer in (8->9) comes first, mixer out (9->8) before the bass EQ",
      [st["type"] for st in h["pipeline"][:5]] == ["Mixer", "Filter", "Filter", "Filter", "Mixer"]
      and h["mixers"]["heights_in"]["channels"] == {"in": 8, "out": 9} and h["mixers"]["heights_out"]["channels"] == {"in": 9, "out": 8})
check("heights profile: height bass joins LFE (dest 5) from the bus channel 8",
      any(src["channel"] == 8 for m in h["mixers"]["heights_out"]["mapping"] if m["dest"] == 5 for src in m["sources"]))
check("DEFAULT_ARGS is the standing profile", S.DEFAULT_ARGS == ["--set=drone2", "--align", "--heights", "--heights-tone"])

# upmix presets (scripts/upmix.py)
import tempfile
import numpy as np
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import upmix as UP
hp = {"hp": 140, "lfe_gain": 0.0, "tone": True}
with tempfile.TemporaryDirectory() as td:
    for kind, flavours in (("stereo", UP.STEREO), ("bed", UP.BED)):
        for fl in flavours:
            u = yaml.safe_load(S.build_config(drone2, align="all", heights=hp, upmix=(kind, fl, td)))
            check(f"upmix {kind}/{fl}: all referenced filters and mixers are defined",
                  all(set(st["names"]) <= set(u["filters"]) for st in u["pipeline"] if st["type"] == "Filter")
                  and all(st["name"] in u["mixers"] for st in u["pipeline"] if st["type"] == "Mixer"))
            check(f"upmix {kind}/{fl}: upmix mixer is the first pipeline step", u["pipeline"][0] == {"type": "Mixer", "name": "up_in"})
            front = [n for st in u["pipeline"] if st["type"] == "Filter" and set(st["channels"]) & {0, 1, 4}
                     for n in st["names"] if n.startswith("up_")]
            check(f"upmix {kind}/{fl}: no upmix filter on FL/FR/FC (lip-sync untouched)", not front or front == ["up_hp_m"])
            check(f"upmix {kind}/{fl}: decorrelator files written (raw float32, 2048 taps)",
                  all(os.path.getsize(os.path.join(td, f"decor_{n}.f32")) == 4 * UP.IR_TAPS for n in UP.IR_SEEDS))
    bm = yaml.safe_load(S.build_config(drone2, upmix=("bed", None, td)))["mixers"]["up_in"]["mapping"]
    heights_src = {src["channel"] for m in bm if m["dest"] in (2, 3) for src in m["sources"]}
    check("bed upmix: heights are fed from FL FR SL SR only, never the centre (dialogue stays in front)", heights_src == {0, 1, 6, 7})
    st = yaml.safe_load(S.build_config(drone2, upmix=("stereo", "balanced", td)))["mixers"]["up_out"]["mapping"]
    cen = {src["channel"]: src["gain"] for m in st if m["dest"] == 4 for src in m["sources"]}
    check("stereo upmix: centre gets 2c of the high-passed mid (coherent sum preserved), LFE left empty",
          abs(cen[4] - 2 * UP.STEREO["balanced"]["c"]) < 1e-5 and not [m for m in st if m["dest"] == 5 and m["sources"]])
    for n, (seed, tau) in UP.IR_SEEDS.items():
        P = np.abs(np.fft.rfft(UP.decorrelator(seed, tau_ms=tau), 8192)) ** 2
        f = np.fft.rfftfreq(8192, 1 / UP.FS)
        third = [10 * np.log10(P[(f > fc / 2 ** (1 / 6)) & (f < fc * 2 ** (1 / 6))].mean()) for fc in 315 * 2 ** (np.arange(0, 5.2, 1 / 3))]
        check(f"decorrelator {n}: third-octave magnitude within 1.5 dB of flat, no bin dips below -8 dB",
              abs(np.array(third)).max() < 1.5 and 10 * np.log10(P[(f > 300) & (f < 12000)].min()) > -8)
try:
    UP.blocks("stereo", "nonsense", tempfile.gettempdir())
    check("unknown flavour is rejected", False)
except ValueError:
    check("unknown flavour is rejected", True)
print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
