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
print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
