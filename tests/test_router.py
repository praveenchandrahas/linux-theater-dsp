"""Tests for scripts/theater-route against a simulated PipeWire graph (tests/fake-pw-link).
Run:  python3 tests/test_router.py      (no PipeWire needed)
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
os.environ.update(FAKE_PW_STATE=f"{tmp}/s.json", THEATER_PW_LINK=f"{HERE}/fake-pw-link", THEATER_STATE_DIR=f"{tmp}/state")
loader = importlib.machinery.SourceFileLoader("tr", os.path.join(HERE, "..", "scripts", "theater-route"))
spec = importlib.util.spec_from_loader("tr", loader)
T = importlib.util.module_from_spec(spec)
loader.exec_module(T)
P, U = T.PORTS, T.USB


def save(st):
    json.dump(st, open(os.environ["FAKE_PW_STATE"], "w"))


def load():
    return json.load(open(os.environ["FAKE_PW_STATE"]))


def cam_up(st):
    for n in range(1, 9):
        st["out"].append(f"camilladsp-playback:output_{n}")
        st["in"].append(f"camilladsp-capture:input_{n}")


def cam_down(st):
    st["out"] = [x for x in st["out"] if not x.startswith("camilladsp")]
    st["in"] = [x for x in st["in"] if not x.startswith("camilladsp")]
    st["links"] = [l for l in st["links"] if not any(x.startswith("camilladsp") for x in l)]


def mpv_up(st, chans):                    # WirePlumber autoconnects a new stream straight to the sink
    for p in chans:
        st["out"].append(f"mpv:output_{p}")
        st["links"].append([f"mpv:output_{p}", f"{U}:playback_{p}"])


def mpv_down(st):
    st["out"] = [x for x in st["out"] if not x.startswith("mpv")]
    st["links"] = [l for l in st["links"] if not l[0].startswith("mpv")]


def counts():
    L = [tuple(l) for l in load()["links"]]
    return (sum(l[0].startswith("mpv") and l[1].startswith(U) for l in L),
            sum(l[0].startswith("mpv") and l[1].startswith("camilladsp") for l in L),
            sum(l[0].startswith("camilladsp") and l[1].startswith(U) for l in L))


ok = True


def check(name, got, want):
    global ok
    good = got == want
    ok &= good
    print(("PASS" if good else "FAIL"), name, got, "" if good else f"(wanted {want})")


st = {"out": [], "in": [f"{U}:playback_{p}" for p in P], "links": []}
cam_up(st); save(st)
check("idle: CamillaDSP -> USB linked", (T.apply("on"), counts()), ("idle", (0, 0, 8)))
s = load(); mpv_up(s, P); save(s)
check("8ch mpv, EQ on -> via CamillaDSP", (T.apply("on"), counts()), ("mpv 8ch via CamillaDSP", (0, 8, 8)))
T.apply("on"); check("repeat is stable", counts(), (0, 8, 8))
check("EQ off -> direct", (T.apply("off"), counts()), ("mpv 8ch direct (EQ off)", (8, 0, 8)))
check("EQ on again", (T.apply("on"), counts()), ("mpv 8ch via CamillaDSP", (0, 8, 8)))
s = load(); cam_down(s); save(s)
check("CamillaDSP gone -> direct fallback", (T.apply("on"), counts()), ("mpv 8ch direct (CamillaDSP not ready)", (8, 0, 0)))
s = load(); cam_up(s); save(s)
check("CamillaDSP back -> via CamillaDSP", (T.apply("on") is not None, counts()), (True, (0, 8, 8)))
s = load(); mpv_down(s); save(s); T.apply("on")
s = load(); mpv_up(s, ["FL", "FR"]); save(s)
check("stereo mpv -> 2 channels via CamillaDSP", (T.apply("on"), counts()), ("mpv 2ch via CamillaDSP", (0, 2, 8)))
s = load(); mpv_down(s); mpv_up(s, ["FL", "FR", "FC", "LFE", "SL", "SR"]); save(s); T.apply("on")
links = sorted((a.split("_")[1], b.split("_")[1]) for a, b in load()["links"] if "camilla" in b and a.startswith("mpv"))
check("5.1 channel mapping (FC->5, LFE->6, SL->7, SR->8)", links,
      sorted([("FC", "5"), ("FL", "1"), ("FR", "2"), ("LFE", "6"), ("SL", "7"), ("SR", "8")]))
s = load(); mpv_down(s); s["in"].remove("camilladsp-capture:input_8"); mpv_up(s, P); save(s)
check("half-ready CamillaDSP -> stays direct, never silent", (T.apply("on"), counts()[:2]), ("mpv 8ch direct (CamillaDSP not ready)", (8, 0)))
s = load(); s["in"] = [x for x in s["in"] if not x.startswith(U)]; s["links"] = [l for l in s["links"] if not l[1].startswith(U)]; save(s)
check("USB interface missing handled", T.apply("on"), "mpv 8ch: USB interface not found")
T.PW_LINK = "/nonexistent"
check("PipeWire unreachable -> None", T.apply("on"), None)
print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
