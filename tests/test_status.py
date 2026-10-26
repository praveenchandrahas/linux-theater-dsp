"""`eq status` text must not change when status() is built on collect_status() (golden files in tests/golden-status/), and
`eq status --json` must describe the same facts.   Run: python3 tests/test_status.py [--update]"""
import contextlib, importlib.machinery, importlib.util, io, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(HERE, "golden-status")
tmp = tempfile.mkdtemp()
os.environ.update(FAKE_PW_STATE=f"{tmp}/s.json", THEATER_PW_LINK=f"{HERE}/fake-pw-link", THEATER_STATE_DIR=f"{tmp}/state",
                  THEATER_CAMILLA_CONFIG=f"{tmp}/config.yml")
loader = importlib.machinery.SourceFileLoader("trs", os.path.join(HERE, "..", "scripts", "theater-route"))
T = importlib.util.module_from_spec(importlib.util.spec_from_loader("trs", loader))
loader.exec_module(T)
P, U = T.PORTS, T.USB
open(f"{tmp}/config.yml", "w").write("# theater-profile: film\nd2_1:\nal_delay_1:\nheights_in:\nht_trim:\n")
T.service_state = lambda n: "active"
SRC = {"codec": "truehd", "profile": "Dolby TrueHD + Dolby Atmos", "channels": 8, "kind": "film", "why": "Atmos: object rendering, no upmix"}


def world(cam=True, usb=True, mpv=None, mpv_via=None, chrome=None, engine_up=False, engine_linked=False, pw=True):
    st = {"out": [], "in": [], "links": []}
    if usb:
        st["in"] += [f"{U}:playback_{p}" for p in P]
    if cam:
        for n in range(1, 9):
            st["out"].append(f"camilladsp-playback:output_{n}"); st["in"].append(f"camilladsp-capture:input_{n}")
            if usb:
                st["links"].append([f"camilladsp-playback:output_{n}", f"{U}:playback_{P[n - 1]}"])
    for p in (mpv or []):
        st["out"].append(f"mpv:output_{p}")
        if mpv_via == "cam":
            st["links"].append([f"mpv:output_{p}", f"camilladsp-capture:input_{P.index(p) + 1}"])
        elif mpv_via == "direct":
            st["links"].append([f"mpv:output_{p}", f"{U}:playback_{p}"])
        elif mpv_via == "mixed":
            st["links"].append([f"mpv:output_{p}", f"{U}:playback_{p}"])
            st["links"].append([f"mpv:output_{p}", f"camilladsp-capture:input_{P.index(p) + 1}"])
    if chrome:
        for i, p in enumerate(chrome[0]):
            st["out"].append(f"Google Chrome:output_{p}")
            if chrome[1]:
                st["links"].append([f"Google Chrome:output_{p}", f"camilladsp-capture:input_{i + 1}"])
    if engine_up:
        st["in"] += T.ENGINE_IN; st["out"] += T.ENGINE_OUT
        if engine_linked:
            for i, o in enumerate(T.ENGINE_OUT):
                st["links"].append([o, T.cam_in(T.ENGINE_TO_CAM[i])])
    json.dump(st, open(os.environ["FAKE_PW_STATE"], "w"))


def state(**kv):
    os.makedirs(os.environ["THEATER_STATE_DIR"], exist_ok=True)
    for f in os.listdir(os.environ["THEATER_STATE_DIR"]):
        os.unlink(os.path.join(os.environ["THEATER_STATE_DIR"], f))
    for k, v in kv.items():
        open(os.path.join(os.environ["THEATER_STATE_DIR"], k), "w").write(v + "\n")


SCEN = {
    "idle_engine_linked": (dict(engine_up=True, engine_linked=True), dict(engine="on"), None),
    "idle_engine_down": (dict(), dict(engine="failed", **{"profile-mode": "film"}), None),
    "chrome_patched": (dict(chrome=(["FL", "FR"], True), engine_up=True, engine_linked=True), dict(), None),
    "chrome_unpatched": (dict(chrome=(["FL", "FR"], False)), dict(eq="off"), None),
    "atmos_via_cam": (dict(mpv=P, mpv_via="cam"), dict(), SRC),
    "mpv_direct_unidentified": (dict(mpv=P, mpv_via="direct"), dict(), None),
    "mpv_mixed": (dict(mpv=P, mpv_via="mixed"), dict(), SRC),
    "usb_missing": (dict(mpv=["FL", "FR"], mpv_via="direct", usb=False), dict(), None),
    "no_cam_mpv": (dict(cam=False, mpv=P, mpv_via="direct"), dict(), SRC),
}


def render(name):
    w, st, src = SCEN[name]
    world(**w); state(**st)
    T.mpv_source = lambda: src
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        T.status()
    return buf.getvalue().replace(os.environ["THEATER_STATE_DIR"], "<STATE>")


ok = True


def check(msg, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + msg, extra)
    ok = ok and cond


if "--update" in sys.argv:
    os.makedirs(GOLD, exist_ok=True)
    for n in SCEN:
        open(os.path.join(GOLD, n + ".txt"), "w").write(render(n))
    print("goldens written"); sys.exit(0)

for n in SCEN:
    check(f"status text is unchanged: {n}", render(n) == open(os.path.join(GOLD, n + ".txt")).read())

if hasattr(T, "collect_status"):
    def js(name):
        w, st, src = SCEN[name]; render(name); return T.collect_status()
    d = js("atmos_via_cam")
    check("json: schema, switch, profile and the mpv route", d["schema"] == 1 and d["eq"]["switch"] == "on" and d["dsp"]["profile"] == "film"
          and d["mpv"]["playing"] and d["mpv"]["route"] == {"via": 8, "direct": 0, "to_usb": 8, "channels": 8}, str(d.get("mpv")))
    check("json: source block", d["mpv"]["source"]["kind"] == "film" and d["mpv"]["verdict"] == "cam")
    d = js("chrome_patched")
    check("json: Chrome app patched 2/2 and engine linked", d["apps"] == [{"name": "Google Chrome", "patched": 2, "total": 2}] and d["dsp"]["engine"]["linked"] is True)
    d = js("idle_engine_down")
    check("json: engine failed, pinned mode shown", d["dsp"]["engine"]["state"] == "failed" and d["dsp"]["pmode"] == "film" and not d["mpv"]["playing"])
    check("json: it is valid JSON text with the same facts", json.loads(json.dumps(d))["dsp"]["pmode"] == "film")
    d = js("usb_missing"); check("json: USB missing is a verdict", d["mpv"]["verdict"] == "usb-missing" and d["usb_up"] is False)
    d = js("mpv_mixed"); check("json: mixed routing is a verdict", d["mpv"]["verdict"] == "mixed")
    d = js("mpv_direct_unidentified"); check("json: unidentified source is null", d["mpv"]["source"] is None and d["mpv"]["verdict"] == "direct")

print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
