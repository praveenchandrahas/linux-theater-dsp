"""Layouts other than the author's, through set-eq.py, upmix.py and theater-route: structure of the generated CamillaDSP configs (PyYAML), the router's
links on a simulated graph, and the refusals. SIMULATION ONLY: none of these layouts has been heard on real hardware.
Run: python3 tests/test_layouts_dsp.py   (needs PyYAML, numpy, scipy)"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import layout as L

ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(("PASS" if cond else "FAIL"), name, detail)


def seteq():
    sp = importlib.util.spec_from_file_location("seteq_l", os.path.join(HERE, "..", "scripts", "set-eq.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def build(lay, set_name=None, upmix=None, **kw):
    S = seteq()
    S.configure(lay)
    sname = set_name or S.DEFAULT_BASE_SET
    chosen = [(n, f, g, q) for n, f, g, q in S.FILTER_SETS[sname]]
    heights = {"hp": lay.crossover_hz, "lfe_gain": 0.0, "tone": True, "invert": False}
    return S, S.build_config(chosen, align="all", heights=heights, upmix=upmix, layout=lay, **kw)


def refs_ok(doc):
    f = doc.get("filters") or {}
    return (all(set(st["names"]) <= set(f) for st in doc["pipeline"] if st["type"] == "Filter")
            and all(st["name"] in (doc.get("mixers") or {}) for st in doc["pipeline"] if st["type"] == "Mixer"))


def chain_ok(doc, n):
    """Channel counts line up through the pipeline: devices n; every mixer's in = the width before it."""
    width = n
    for st in doc["pipeline"]:
        if st["type"] == "Mixer":
            ch = doc["mixers"][st["name"]]["channels"]
            if ch["in"] != width:
                return False
            width = ch["out"]
        else:
            if any(c >= width for c in st["channels"]):
                return False
    return width == n


for name in L.PRESET_ORDER:
    lay = L.preset(name)
    S, text = build(lay)
    doc = yaml.safe_load(text)
    check(f"{name}: devices carry {lay.n} channels", doc["devices"]["capture"]["channels"] == lay.n == doc["devices"]["playback"]["channels"])
    check(f"{name}: every filter and mixer a step uses is defined, and widths line up", refs_ok(doc) and chain_ok(doc, lay.n))
    if lay.room_defaults == "neutral":
        check(f"{name}: neutral room starts with no delays, trims, bass or tone filters", not (doc.get("filters") or {}) or set(doc["filters"]) <= {k for k in doc["filters"] if k.startswith(("h_hp_", "h_lp_"))})
    tops = [S.ALIGN[lay.port(h)] for h in lay.heights]
    sub_steps = [st for st in doc["pipeline"] if st["type"] == "Mixer" and st["name"] == "heights_out"]
    if lay.bass_to_sub:
        m = doc["mixers"]["heights_out"]["mapping"]
        into = [d for d in m if d["dest"] == lay.port("LFE")][0]["sources"]
        check(f"{name}: bass of {', '.join(lay.bass_to_sub)} is high-passed and the low-passed sum joins the sub on port {lay.port('LFE')}",
              len(into) == 2 and into[1]["channel"] == lay.n and all(f"h_hp_{lay.port(c)}" in doc["filters"] for c in lay.bass_to_sub))
    else:
        check(f"{name}: nothing is sent to a sub", not sub_steps and "heights_in" not in (doc.get("mixers") or {}))
    eq_ch = sorted(lay.port(c) for c in lay.bass_eq_channels)
    S2, text2 = build(lay, set_name="drone2")
    d2 = yaml.safe_load(text2)
    first_eq = [st for st in d2["pipeline"] if st["type"] == "Filter" and "q20_1" in st["names"]]
    check(f"{name}: the bass EQ goes on {eq_ch} (speakers that reproduce bass, and the sub)", first_eq and first_eq[0]["channels"] == eq_ch, str(first_eq[:1]))

# the bass-to-sub management and tone-match are independent
lay = L.preset("7.1.4")
S, text = build(lay)
doc = yaml.safe_load(text)
check("7.1.4: four tops share one bus and one high-pass each", [k for k in doc["filters"] if k.startswith("h_hp_")] == [f"h_hp_{p}" for p in (8, 9, 10, 11)]
      and doc["mixers"]["heights_in"]["channels"] == {"in": 12, "out": 13})
d = L.preset("7.1.2").to_dict()
d["channels"][8]["bass"] = d["channels"][9]["bass"] = "full"
S, text = build(L.from_dict(d))
check("heights set to bass: full get no crossover and no bus (still no tone for a neutral room)", "heights_in" not in (yaml.safe_load(text).get("mixers") or {}))
d = L.preset("5.1").to_dict()
d["amp_bass_management"] = False
for c in d["channels"]:
    if c["name"] in ("SL", "SR"):
        c["bass"] = "sub"
S, text = build(L.from_dict(d))
doc = yaml.safe_load(text)
check("5.1 with amp_bass_management: false and surrounds set to bass: sub -> Roomtone high-passes SL/SR (ports 2, 3) into the LFE (port 5)",
      "h_hp_2" in doc["filters"] and "h_hp_3" in doc["filters"] and refs_ok(doc) and chain_ok(doc, 6))

# neutral room with a room.json: names of the layout are the keys
S = seteq()
lay71 = L.preset("7.1")
S.configure(lay71)
room = {"version": 1, "align": {"BL": {"delay_ms": 3.5, "trim_db": -2.0}}}
S.apply_room(S.validate_room(room))
doc = yaml.safe_load(S.build_config([], align="all", layout=lay71))
check("room.json keys are the layout's channel names (BL on port 2 gets 3.5 ms and -2 dB)", doc["filters"]["al_delay_2"]["parameters"]["delay"] == 3.5 and doc["filters"]["al_gain_2"]["parameters"]["gain"] == -2.0)
try:
    S.validate_room({"version": 1, "align": {"RL": {"delay_ms": 1.0}}})
    check("a room.json for another layout's names is refused", False)
except S.RoomError as e:
    check("a room.json for another layout's names is refused with the allowed names listed", "unknown key(s) 'RL'" in str(e) and "BL" in str(e), str(e)[:90])
S = seteq()
S.configure(L.preset("7.1"))
check("--dump-room on a neutral layout is neutral", all(v == {"delay_ms": 0.0, "trim_db": 0.0} for v in S.room_dump()["align"].values()) and S.room_dump()["height_tone"]["filters"] == [])

# ---- upmix on layouts that fit and that do not
lay = L.preset("7.1.2")
with tempfile.TemporaryDirectory() as td:
    S, text = build(lay, upmix=("stereo", "balanced", td))
    doc = yaml.safe_load(text)
    up = doc["mixers"]["up_out"]["mapping"]
    check("7.1.2 stereo upmix: 10-wide mixers; centre on port 4, tops (ports 8, 9) fed, rears (2, 3) pass through silent",
          doc["mixers"]["up_in"]["channels"] == {"in": 10, "out": 10} and chain_ok(doc, 10) and refs_ok(doc)
          and any(m["dest"] == 4 and m["sources"][0]["channel"] == 4 for m in up)
          and [s["channel"] for m in doc["mixers"]["up_in"]["mapping"] if m["dest"] == 8 for s in m["sources"]] == [0, 1]
          and [s["channel"] for m in doc["mixers"]["up_in"]["mapping"] if m["dest"] == 2 for s in m["sources"]] == [2])
    S, text = build(lay, upmix=("bed", "balanced", td))
    doc = yaml.safe_load(text)
    check("7.1.2 bed upmix: tops take the side signals (SL port 6 -> port 8, SR port 7 -> port 9)", chain_ok(doc, 10)
          and 6 in [s["channel"] for m in doc["mixers"]["up_in"]["mapping"] if m["dest"] == 8 for s in m["sources"]]
          and 7 in [s["channel"] for m in doc["mixers"]["up_in"]["mapping"] if m["dest"] == 9 for s in m["sources"]])
for name in ("2.0", "2.1", "5.1", "7.1", "7.1.4"):
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "l.yml")
        L.save(L.preset(name), f)
        r = subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts", "set-eq.py"), f"--layout={f}", "--upmix=bed", "--dry"],
                           capture_output=True, text=True, env={**os.environ, "HOME": td})
        check(f"{name}: --upmix is refused with the reason, exit 1", r.returncode == 1 and "No upmix is offered" in r.stdout, r.stdout.strip().splitlines()[-1][:110])

# ---- set-eq refuses a broken layout and changes nothing
with tempfile.TemporaryDirectory() as td:
    f = os.path.join(td, "bad.yml")
    open(f, "w").write("version: 1\noutput: {channels: 2}\nchannels: [{name: FL, role: bed, port: 7}]\n")
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts", "set-eq.py"), f"--layout={f}", "--dry"], capture_output=True, text=True, env={**os.environ, "HOME": td})
    check("a broken layout: exit 2, message names the field", r.returncode == 2 and "channels[0].port" in r.stderr, r.stderr.strip()[:100])
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts", "set-eq.py"), "--layout=/nonexistent.yml", "--dry"], capture_output=True, text=True, env={**os.environ, "HOME": td})
    check("--layout=FILE that does not exist is an error (no silent fallback)", r.returncode == 2 and "no such file" in r.stderr)

# ---- the router on a simulated graph, per layout
PWL = os.path.join(HERE, "fake-pw-link")


def router(lay_file):
    tmp = tempfile.mkdtemp()
    env = {"FAKE_PW_STATE": f"{tmp}/s.json", "THEATER_PW_LINK": PWL, "THEATER_STATE_DIR": f"{tmp}/state", "ROOMTONE_LAYOUT": lay_file}
    os.environ.update(env)
    ld = importlib.machinery.SourceFileLoader("tr_l", os.path.join(HERE, "..", "scripts", "theater-route"))
    T = importlib.util.module_from_spec(importlib.util.spec_from_loader("tr_l", ld))
    ld.exec_module(T)
    return T, env["FAKE_PW_STATE"]


for name in L.PRESET_ORDER:
    with tempfile.TemporaryDirectory() as td:
        d = L.PRESETS[name]
        dd = json.loads(json.dumps(d))
        dd["output"]["device"] = "alsa_output.test.multichannel"
        lay = L.from_dict(dd)
        f = os.path.join(td, "layout.yml")
        L.save(lay, f)
        T, state = router(f)
        U, P, N = T.USB, T.PORTS, lay.n
        check(f"{name}: router reads {N} ports and the device name from the layout", T.N == N and U == "alsa_output.test.multichannel" and P == lay.port_names)
        st = {"out": [], "in": [f"{U}:playback_{p}" for p in P], "links": []}
        for n in range(1, N + 1):
            st["out"].append(f"camilladsp-playback:output_{n}")
            st["in"].append(f"camilladsp-capture:input_{n}")
        for p in P:
            st["out"].append(f"mpv:output_{p}")
            st["links"].append([f"mpv:output_{p}", f"{U}:playback_{p}"])
        json.dump(st, open(state, "w"))
        msg = T.apply("on")
        links = [tuple(x) for x in json.load(open(state))["links"]]
        via = sorted(l for l in links if l[0].startswith("mpv"))
        to_usb = sorted(l for l in links if l[0].startswith("camilladsp-playback"))
        check(f"{name}: {N}-channel mpv goes through CamillaDSP port for port, CamillaDSP -> sink for every port, no direct links left",
              msg == f"mpv {N}ch via CamillaDSP" and via == sorted((f"mpv:output_{p}", f"camilladsp-capture:input_{i + 1}") for i, p in enumerate(P))
              and to_usb == sorted((f"camilladsp-playback:output_{i + 1}", f"{U}:playback_{p}") for i, p in enumerate(P)), msg)
        info = T.collect_status()["layout"]
        check(f"{name}: eq status --json carries the layout (names, ports, azimuth, upmix verdict)",
              [c["name"] for c in info["channels"]] == lay.result_order and info["ports"] == N and info["upmix"]["fits"] == lay.upmix_support()[0]["stereo"])
        want = T.want_profile("auto", False, None, True, T.read_flavours())
        check(f"{name}: a stereo app gets {'the stereo upmix' if lay.upmix_support()[0]['stereo'] else 'the film profile (no upmix fits this layout)'}",
              want.startswith("stereo") == lay.upmix_support()[0]["stereo"], str(want))

# broken layout file: the router keeps the built-in layout and reports why
with tempfile.TemporaryDirectory() as td:
    f = os.path.join(td, "layout.yml")
    open(f, "w").write("version: 1\nchannels: nonsense\n")
    T, state = router(f)
    check("router with a broken layout file: keeps the sound path (built-in 5.1.2) and reports the error in status", T.N == 8 and T.LAYOUT_ERROR and "layout.yml" in T.collect_status()["layout"]["error"])
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
