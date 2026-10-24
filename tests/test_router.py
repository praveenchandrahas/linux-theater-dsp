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

# ------------------------------------------------------------------ Chrome patching and profile selection
import socket, stat, threading
T.PW_LINK = f"{HERE}/fake-pw-link"
CH = "Google Chrome"


def chrome_up(st, ports=("FL", "FR")):          # WirePlumber autoconnects it straight to the sink (here: the USB sink's FL/FR)
    for p in ports:
        st["out"].append(f"{CH}:output_{p}")
        st["links"].append([f"{CH}:output_{p}", f"{U}:playback_{p}"])


def chrome_links():
    return sorted((a.split("_")[-1], b) for a, b in load()["links"] if a.startswith(CH))


st = {"out": [], "in": [f"{U}:playback_{p}" for p in P], "links": []}
cam_up(st); chrome_up(st); save(st)
check("Chrome while profile is film: left alone", (T.apply("on", profile="film"), chrome_links()),
      (f"{CH} on its own output", [("FL", f"{U}:playback_FL"), ("FR", f"{U}:playback_FR")]))
check("Chrome while profile is stereo: patched into CamillaDSP FL/FR, direct links dropped",
      (T.apply("on", profile="stereo:balanced"), chrome_links()),
      (f"{CH} 2ch via CamillaDSP", [("FL", "camilladsp-capture:input_1"), ("FR", "camilladsp-capture:input_2")]))
check("Chrome patch is stable on repeat", (T.apply("on", profile="stereo:balanced"), len(chrome_links())), (f"{CH} 2ch via CamillaDSP", 2))
check("EQ off: Chrome handed back (its CamillaDSP links removed)", (T.apply("off", profile="stereo:balanced"), [b for _, b in chrome_links() if "camilla" in b]),
      (f"{CH} on its own output", []))
s = load(); s["in"].remove("camilladsp-capture:input_2"); save(s)
check("half-ready CamillaDSP: Chrome not patched", [b for _, b in chrome_links() if "camilla" in b], [])
s = load(); mpv_up(s, P); save(s)
check("Chrome + mpv together: mpv result first, Chrome second", T.apply("on", profile="film").split("; ")[0], "mpv 8ch direct (CamillaDSP not ready)")
st = {"out": [], "in": [f"{U}:playback_{p}" for p in P], "links": []}
cam_up(st); chrome_up(st, ("MONO",)); save(st)
s = load(); s["out"] = [x for x in s["out"] if "MONO" not in x] + [f"{CH}:output_MONO"]; save(s)
check("mono Chrome stream feeds both FL and FR", (T.apply("on", profile="stereo:wide"), sorted(b for _, b in chrome_links() if "camilla" in b)),
      (f"{CH} 1ch via CamillaDSP", ["camilladsp-capture:input_1", "camilladsp-capture:input_2"]))
check("only matching apps are touched (other app ignored)", T.stereo_apps(["Spotify:output_FL", f"{CH}:output_FL", "mpv:output_FL", "camilladsp-playback:output_1"]),
      {CH: ["FL"]})

check("classify: Atmos TrueHD -> film", T.classify(8, "Dolby TrueHD + Dolby Atmos")[0], "film")
check("classify: Atmos E-AC-3 (6ch) -> film, not bed", T.classify(6, "Dolby Digital Plus + Dolby Atmos")[0], "film")
check("classify: plain 5.1 -> bed", T.classify(6, "DTS-HD MA")[0], "bed")
check("classify: stereo -> stereo", T.classify(2, "")[0], "stereo")
check("classify: 7.1 -> film", T.classify(8, "")[0], "film")
check("classify: unknown -> film", T.classify(None)[0], "film")
F = T.DEFAULT_FLAVOUR
check("want: Chrome only -> stereo:balanced", T.want_profile("auto", False, None, True, F), "stereo:balanced")
check("want: mpv 5.1 -> bed:balanced", T.want_profile("auto", True, {"kind": "bed"}, False, F), "bed:balanced")
check("want: mpv Atmos wins over Chrome", T.want_profile("auto", True, {"kind": "film"}, True, F), "film")
check("want: mpv not identified yet -> keep", T.want_profile("auto", True, None, False, F) is T.KEEP, True)
check("want: nothing playing -> None", T.want_profile("auto", False, None, False, F), None)
check("want: explicit mode beats everything", T.want_profile("bed", True, {"kind": "film"}, True, {"stereo": "x", "bed": "wide"}), "bed:wide")
check("decide: switch when wanted and gap respected", (T.decide("film", "stereo:balanced", 100, None, 0), T.decide("film", "stereo:balanced", 100, None, 95)),
      ("stereo:balanced", None))
check("decide: force ignores the gap", T.decide("film", "bed:balanced", 100, None, 99, force=True), "bed:balanced")
check("decide: idle returns to film only after the hold time",
      (T.decide("stereo:balanced", None, 100, 90, 0, idle_reset=120), T.decide("stereo:balanced", None, 300, 90, 0, idle_reset=120),
       T.decide("film", None, 300, 90, 0, idle_reset=120)), (None, "film", None))
check("decide: already there -> None", T.decide("bed:balanced", "bed:balanced", 100, None, 0), None)

# profile header in the config, state files, switching through a fake set-eq, mpv IPC
cfg = f"{tmp}/config.yml"; T.CONFIG = cfg
open(cfg, "w").write("# theater-profile: stereo:wide\ndevices:\n")
check("current_profile reads the config header", T.current_profile(), "stereo:wide")
open(cfg, "w").write("devices:\n"); check("no header -> film", T.current_profile(), "film")
check("default profile-mode is auto, flavours default", (T.read_pmode(), T.read_flavours()), ("auto", {"stereo": "balanced", "bed": "balanced"}))
T.write_state("flavour-bed", "wide"); T.write_state("profile-mode", "nonsense")
check("state files: valid flavour read, invalid mode falls back to auto", (T.read_flavours()["bed"], T.read_pmode()), ("wide", "auto"))
T.write_state("flavour-bed", "balanced")

fake = f"{tmp}/fake-seteq.py"; calls = f"{tmp}/calls"
open(fake, "w").write(f"""import sys
a = sys.argv[1]
open({calls!r}, 'a').write(a + chr(10))
prof = 'film' if a == '--default' else a.split('=')[1]
open({cfg!r}, 'w').write('# theater-profile: ' + prof + chr(10) + 'devices:' + chr(10))
""")
T.SETEQ = fake
T.write_mode("on")
sw = T.Switcher()
out = [f"{CH}:output_FL", f"{CH}:output_FR"]
T.manage(out, sw, now=1000.0)
check("manage: a short Chrome sound (notification ping) does not switch anything", (open(calls).read() if os.path.exists(calls) else "", T.manage([], sw, now=1002.0)), ("", None))
T.manage(out, sw, now=1010.0)
note = T.manage(out, sw, now=1010.0 + T.APP_GRACE + 1)
check("manage: Chrome starts playing -> switches to stereo:balanced via set-eq", (note.split(" (")[0], open(calls).read().split()), ("profile film -> stereo:balanced", ["--upmix=stereo:balanced"]))
check("manage: nothing more to do once there", T.manage(out, sw, now=1020.0), None)
check("manage: Chrome stops, still inside the hold time -> stays", T.manage([], sw, now=1030.0), None)
check("manage: idle long enough -> back to film", (T.manage([], sw, now=1030.0 + T.IDLE_RESET + 1) or "").split(" (")[0], "profile stereo:balanced -> film")
sw2 = T.Switcher(); open(cfg, "w").write("# theater-profile: bed:balanced\\ndevices:\\n")
check("manage: a Chrome ping during a film changes nothing", (T.manage(["mpv:output_FL", f"{CH}:output_FL", f"{CH}:output_FR"], sw2, now=7000.0, force=False)), None)
T.write_mode("off")
check("manage: EQ off -> never switches", T.manage(out, T.Switcher(), now=5000.0), None)
T.write_mode("on")

sock_path = f"{tmp}/mpv.sock"; T.MPV_SOCK = sock_path
TRACK = {"codec": "truehd", "codec-profile": "Dolby TrueHD + Dolby Atmos", "demux-channel-count": 8}


def fake_mpv(track):
    srv = socket.socket(socket.AF_UNIX); srv.bind(sock_path); srv.listen(1)

    def serve():
        c, _ = srv.accept(); f = c.makefile("rw")
        for line in f:
            req = json.loads(line); name = req["command"][1]
            data = {"current-tracks/audio": track, "path": "/films/x.mkv"}.get(name)
            reply = {"request_id": req["request_id"], "error": "success", "data": data} if data is not None else {"request_id": req["request_id"], "error": "property unavailable"}
            f.write(json.dumps(reply) + "\n"); f.flush()
        c.close(); srv.close()
    threading.Thread(target=serve, daemon=True).start()


check("ipc: no socket -> None", T.mpv_source(), None)
fake_mpv(TRACK)
src = T.mpv_source()
check("mpv IPC: Atmos TrueHD track is read and classified film", (src["kind"], src["channels"]), ("film", 8))
os.unlink(sock_path)
fake_mpv({"codec": "dts", "codec-profile": "DTS-HD MA", "demux-channel-count": 6})
check("mpv IPC: 5.1 DTS-HD MA classified bed", T.mpv_source()["kind"], "bed")
os.unlink(sock_path)
T.write_state("profile-mode", "auto")
sw = T.Switcher(); open(cfg, "w").write("# theater-profile: film\ndevices:\n"); open(calls, "w").write("")
fake_mpv({"codec": "dts", "codec-profile": "DTS-HD MA", "demux-channel-count": 6})
note = T.manage(["mpv:output_FL", "mpv:output_FR"], sw, now=9000.0)
check("manage: mpv plays 5.1 -> bed:balanced", (note or "").split(" (")[0], "profile film -> bed:balanced")
os.unlink(sock_path)
sw = T.Switcher(); open(cfg, "w").write("# theater-profile: bed:balanced\ndevices:\n")
check("manage: mpv up but no IPC yet -> keeps profile", T.manage(["mpv:output_FL"], sw, now=9100.0), None)
check("manage: still unidentified after the grace time -> film", (T.manage(["mpv:output_FL"], sw, now=9100.0 + T.UNKNOWN_GRACE + 1, force=True) or "").split(" (")[0],
      "profile bed:balanced -> film")

print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
