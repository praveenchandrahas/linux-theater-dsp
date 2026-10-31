"""Tests for scripts/layout.py: presets, validation messages, YAML/JSON round trips (with and without PyYAML), save with backup, interface detection.
Run: python3 tests/test_layout.py     (no hardware; PyYAML optional)"""
import copy
import datetime
import hashlib
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import layout as L

ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(("PASS" if cond else "FAIL"), name, detail)


def bad(name, mutate, fragment, base="7.1.2"):
    d = copy.deepcopy(L.PRESETS[base])
    mutate(d)
    try:
        L.validate(d)
        check(name, False, "(accepted)")
    except L.LayoutError as e:
        check(name, fragment in str(e), f"-> {e}")


# ---- the presets
check("all seven presets exist and validate", [n for n in L.PRESET_ORDER if L.preset(n)] == ["2.0", "2.1", "5.1", "5.1.2", "7.1", "7.1.2", "7.1.4"])
want = {"2.0": 2, "2.1": 3, "5.1": 6, "5.1.2": 8, "7.1": 8, "7.1.2": 10, "7.1.4": 12}
check("speaker counts match the preset names", {n: len(L.preset(n).channels) for n in want} == want)
A = L.preset("5.1.2")
check("5.1.2 is the author's table: hardware order, results order, heights, bass-to-sub",
      A.hw_order == ["FL", "FR", "RL", "RR", "FC", "LFE", "SL", "SR"] and A.result_order == ["FL", "FR", "FC", "LFE", "SL", "SR", "RL", "RR"]
      and A.heights == ["RL", "RR"] and A.beds == ["FL", "FR", "FC", "SL", "SR"] and A.sub == "LFE" and A.bass_to_sub == ["RL", "RR"]
      and A.bass_eq_channels == ["FL", "FR", "FC", "LFE", "SL", "SR"] and A.port_names == ["FL", "FR", "RL", "RR", "FC", "LFE", "SL", "SR"]
      and A.device == L.AUTHOR_DEVICE and A.amp_bass_management and A.room_defaults == "author" and A.is_author_512())
check("only 5.1.2 carries the author's room numbers", [n for n in L.PRESET_ORDER if L.preset(n).room_defaults == "author"] == ["5.1.2"])
check("no preset other than 5.1.2 is the author's", [n for n in L.PRESET_ORDER if L.preset(n).is_author_512()] == ["5.1.2"])
for n in L.PRESET_ORDER:
    p = L.preset(n)
    check(f"{n}: ports unique, inside the interface, port names unique", len({c['port'] for c in p.channels}) == len(p.channels)
          and max(c['port'] for c in p.channels) < p.n and len(set(p.port_names)) == p.n)
fit = {n: L.preset(n).upmix_support()[0]["stereo"] for n in L.PRESET_ORDER}
check("upmixers fit exactly 5.1.2 and 7.1.2", fit == {"2.0": False, "2.1": False, "5.1": False, "5.1.2": True, "7.1": False, "7.1.2": True, "7.1.4": False}, str(fit))
check("a layout the upmixers do not fit says why", "no FC" in " ".join(L.preset("2.0").upmix_support()[1]) and "exactly two height" in " ".join(L.preset("7.1.4").upmix_support()[1]))
check("upmix slots of 5.1.2 are the old indexes (FL0 FR1 TL2 TR3 FC4 LFE5 SL6 SR7)", A.upmix_slots() == {"FL": 0, "FR": 1, "TL": 2, "TR": 3, "FC": 4, "LFE": 5, "SL": 6, "SR": 7})
check("7.1.2 slots put the tops on ports 8, 9", L.preset("7.1.2").upmix_slots()["TL"] == 8 and L.preset("7.1.2").upmix_slots()["TR"] == 9)
check("no file -> built-in 5.1.2 (nothing changes for existing installs)", L.load("/nonexistent/layout.yml").is_author_512())

# ---- validation: every message names the field
bad("unknown top-level key", lambda d: d.update(colour="red"), "unknown key(s) 'colour'")
bad("wrong version", lambda d: d.update(version=2), "layout.version")
bad("name with a space", lambda d: d["channels"][0].update(name="F L"), "channels[0].name")
bad("duplicate name", lambda d: d["channels"][1].update(name="FL"), "used twice")
bad("duplicate port", lambda d: d["channels"][1].update(port=0), "already used by 'FL'")
bad("port outside the interface", lambda d: d["channels"][1].update(port=10), "channels[1].port")
bad("bad role", lambda d: d["channels"][0].update(role="tweeter"), "channels[0].role")
bad("two subs", lambda d: d["channels"][4].update(role="sub"), "at most one speaker may have role sub")
bad("height too low", lambda d: [c.update(elevation=0) for c in d["channels"] if c["name"] == "TFL"], "elevation of at least 10")
bad("bass: sub without a sub", lambda d: d["channels"].__delitem__(3), "has no speaker with role sub")
bad("azimuth out of range", lambda d: d["channels"][0].update(azimuth=400), "channels[0].azimuth")
bad("port_names wrong length", lambda d: d["output"].update(port_names=["FL"]), "output.port_names")
bad("port_names repeated", lambda d: d["output"].update(port_names=["FL"] * 10), "must be different")
bad("device with a shell character", lambda d: d["output"].update(device="x; rm -rf /"), "output.device")
bad("nothing but a sub", lambda d: d.update(channels=[c for c in d["channels"] if c["role"] == "sub"]), "at least one speaker must have role bed")
bad("amp manages bass but a bed speaker is set to sub", lambda d: (d.update(amp_bass_management=True), d["channels"][0].update(bass="sub")), "already manages bass", base="5.1")
bad("not a mapping", lambda d: d.update(channels=["FL"]), "channels[0]: expected a mapping")
check("integers given as 3.0 are accepted for ports", L.validate({**copy.deepcopy(L.PRESETS["2.0"]), "channels": [{"name": "FL", "role": "bed", "port": 0.0}, {"name": "FR", "role": "bed", "port": 1}]})["channels"][0]["port"] == 0)

# ---- text round trips
import yaml
for n in L.PRESET_ORDER:
    t = L.preset(n).to_yaml()
    a, b = L.validate(L._simple_yaml(t)), L.validate(yaml.safe_load(t))
    j = L.validate(json.loads(json.dumps(L.preset(n).d)))
    check(f"{n}: dump -> PyYAML, dump -> built-in parser and JSON all read back the same", a == b == j == L.preset(n).d)
try:
    L.parse_file_text("version: 1\nchannels: [oops\n")
    check("broken YAML is an error", False)
except L.LayoutError:
    check("broken YAML is an error, not a crash", True)
try:
    L.parse_text('{"version": 1, "version": 1}')
    check("duplicate JSON keys refused", False)
except L.LayoutError:
    check("duplicate JSON keys refused", True)
try:
    L.parse_file_text("version: 1\nname: !!python/object/apply:os.system ['echo gotcha']\noutput: {channels: 2}\nchannels: []\n")
    check("python tag refused", False)
except L.LayoutError:
    check("python tag in the file is refused, nothing runs", True)

# ---- load/save with backup
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "cfg", "layout.yml")
    path, bak = L.save(L.preset("7.1"), p)
    check("first save: file written, no backup", os.path.isfile(p) and bak is None and L.load(p).result_order[-2:] == ["BL", "BR"])
    first = open(p).read()
    path, bak = L.save(L.preset("5.1"), p, now=datetime.datetime(2026, 1, 2, 3, 4, 5))
    check("second save backs up the previous file byte for byte", bak.endswith("layout.yml.bak-20260102-030405") and open(bak).read() == first and L.load(p).name == "5.1")
    for i in range(15):
        L.save(L.preset("2.0"), p, now=datetime.datetime(2026, 2, 1, 0, 0, i))
    baks = [f for f in os.listdir(os.path.dirname(p)) if ".bak-" in f]
    check("only the newest 10 backups are kept", len(baks) == L.BACKUPS_KEPT, str(len(baks)))
    try:
        L.save({"version": 1, "output": {"channels": 2}, "channels": []}, p)
        check("an invalid layout is not written", False)
    except L.LayoutError:
        check("an invalid layout is refused before anything is written", L.load(p).name == "2.0")
    open(p, "w").write("version: 1\nchannels: nonsense\noutput: {channels: 2}\n")
    try:
        L.load(p)
        check("a broken file raises, it does not fall back silently", False)
    except L.LayoutError as e:
        check("a broken file raises with the path in the message (no silent fallback to 5.1.2)", p in str(e), str(e))
    os.environ[L.ENV_PATH] = os.path.join(td, "other.yml")
    check("$ROOMTONE_LAYOUT selects the file", L.path_for() == os.path.join(td, "other.yml") and L.load().is_author_512())
    del os.environ[L.ENV_PATH]

# ---- interface detection (parsing only; pw-link itself is not run)
PWL = """alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71:playback_FL
alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71:playback_FR
alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71:playback_RL
alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71:playback_RR
alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71:playback_FC
alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71:playback_LFE
alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71:playback_SL
alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71:playback_SR
alsa_output.pci-0000_00_1f.3.analog-stereo:playback_FL
alsa_output.pci-0000_00_1f.3.analog-stereo:playback_FR
camilladsp-capture:input_1
mpv:output_FL
"""
f = L.parse_sink_ports(PWL)
check("parse_sink_ports finds both sinks and ignores CamillaDSP/mpv", sorted((k, len(v)) for k, v in f.items()) ==
      [("alsa_output.pci-0000_00_1f.3.analog-stereo", 2), ("alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71", 8)])
check("suggest_preset by port count (never the author's 5.1.2)", [L.suggest_preset(n) for n in (2, 4, 6, 8, 10, 12, 16)] == ["2.0", "2.0", "5.1", "7.1", "7.1.2", "7.1.4", "7.1.4"])
d = L.propose("alsa_output.usb-x.analog-surround-71", f["alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71"])
v = L.validate(d)
check("a proposal for an 8-port interface is the 7.1 preset on that device, neutral room", v["output"]["device"] == "alsa_output.usb-x.analog-surround-71" and v["room_defaults"] == "neutral" and len(v["channels"]) == 8)
try:
    L.propose("dev", ["FL", "FR"], "7.1")
    check("a preset the interface cannot drive is refused", False)
except L.LayoutError as e:
    check("a preset the interface cannot drive is refused", "needs 8 output ports" in str(e))
check("std_port_names for 10 outputs ends AUX8 AUX9", L.std_port_names(10)[-2:] == ["AUX8", "AUX9"])

# ---- CLI
import contextlib
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "l.yml")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        c1 = L._cli(["--file", p, "--init", "7.1"])
        c2 = L._cli(["--file", p, "--validate"])
        c3 = L._cli(["--file", p, "--init", "nonsense"])
    check("CLI --init, --validate, unknown preset", (c1, c2, c3) == (0, 0, 2) and "OK:" in buf.getvalue() and "unknown preset" in buf.getvalue())
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
