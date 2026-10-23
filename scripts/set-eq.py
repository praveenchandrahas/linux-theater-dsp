#!/usr/bin/env python3
"""Change the CamillaDSP bass EQ live, without restarting the service.

Usage: ./set-eq.py [<scale> <max_freq_hz>] [--set=NAME] [--skip=a,b] [--dry]

  --set=NAME   which filter set to use (default: rew)
                 rew      the 8 cut filters REW fitted to flatten your L sweep (the first version you heard)
                 hump8    fitted to your L sweep so 36-160 Hz sits about 8 dB above the mids, tapering to flat by 250 Hz
                 hump14   same, about 14 dB above the mids
                 hump20   same, about 20 dB above the mids
                 thump14  hump14 plus roughly 8 dB extra around 63 Hz (53-74 Hz), where the Toliver 808s sit
               The hump sets cap Q at 5 so they react less to small changes in mic or head position.
               With a hump set you can leave out <scale> and <max_freq_hz> (they default to 1.0 and 300).
  scale        multiplies every cut in dB. 1.0 = the set as fitted, 0.5 = half the dB, 0 = no cuts at all.
  max_freq_hz  keep only filters at or below this frequency (the hump sets reach 250 Hz, so use 300 to keep all).
  --skip=...   leave the named filters out entirely. Names: bass_1..bass_9 for rew, h8_1.., h14_1.., h20_1.., t14_1.. for the others.
  --dry        only print the resulting filter response; do not write or reload anything.
  --align      also apply the measured per-speaker delays and level trims (see ALIGN in this file).
  --invert=FC  flip the polarity of the named channels (comma list: FL,FR,RL,RR,FC,LFE,SL,SR).
  --align=bed  same, but only for the 5.1 bed (FL FR FC SL SR + LFE); the two heights are left untouched.

  --heights    high-pass the two height speakers (LR4) and send what they lose, low-passed and summed, to the
               LFE channel (the sub). Add --heights-hp=120 (Hz, default 120), --heights-lfe=0 (dB, default 0: gain of
               the height bass as it joins the LFE), --heights-delay=0 (ms, extra delay of that bass path),
               --heights-invert (flip its polarity), --heights-tone (tone-match the heights to the bed, see HEIGHT_TONE).

Examples:
  ./set-eq.py --set=hump14             deliberate hump, middle size
  ./set-eq.py --set=thump14            same, with extra weight at 63 Hz
  ./set-eq.py --set=thump20            hump20 with the 63 Hz thump lifted back (also punch20, thump20x)
  ./set-eq.py --set=drone2             punch20x plus extra cuts at 72 and 84 Hz (also drone1 = gentler, drone3 = stronger)
  ./set-eq.py 1.0 200                  the original REW set (what you heard first)
  ./set-eq.py 1.0 200 --skip=bass_4,bass_5     REW set without the two ~60 Hz cuts
  ./set-eq.py 0 300                    effectively bypassed

Channels filtered (hardware order FL FR RL RR FC LFE SL SR): 0,1,4,5,6,7. Heights (2,3) untouched unless --heights.
"""
import cmath, math, os, shutil, subprocess, sys, tempfile, time

FS = 48000
CONFIG = os.path.expanduser("~/.config/camilladsp/config.yml")

# name, freq Hz, gain dB, Q
FILTER_SETS = {
    # from REW export L-Oct-19-2026.txt (filter 8 removed)
    "rew": [
        ("bass_1", 37.05, -6.1, 7.578),
        ("bass_2", 43.8, -6.5, 8.253),
        ("bass_3", 47.8, -12.8, 7.423),
        ("bass_4", 60.4, -24.7, 4.842),
        ("bass_5", 65.8, -10.0, 7.454),
        ("bass_6", 84.9, -18.8, 5.111),
        ("bass_7", 106.5, -11.5, 7.158),
        ("bass_9", 155.0, -15.2, 1.948),
    ],
    # fitted to the measured L sweep (L-for-Claude.txt, variable smoothing), cut-only, Q <= 5
    "hump8": [
        ("h8_1", 46.92, -12.48, 5.0),
        ("h8_2", 61.91, -27.33, 4.92),
        ("h8_3", 83.83, -12.58, 3.18),
        ("h8_4", 107.69, -7.84, 5.0),
        ("h8_5", 135.51, -4.94, 4.17),
        ("h8_6", 154.85, -7.56, 5.0),
        ("h8_7", 177.33, -5.55, 5.0),
        ("h8_8", 248.22, -4.08, 5.0),
    ],
    "hump14": [
        ("h14_1", 47.7, -8.07, 5.0),
        ("h14_2", 62.06, -22.43, 5.0),
        ("h14_3", 84.18, -8.85, 5.0),
        ("h14_4", 107.6, -7.0, 5.0),
        ("h14_5", 138.04, -3.55, 4.99),
        ("h14_6", 155.18, -6.7, 5.0),
        ("h14_7", 177.08, -4.84, 5.0),
        ("h14_8", 249.37, -4.62, 5.0),
    ],
    "hump20": [
        ("h20_1", 48.1, -3.67, 5.0),
        ("h20_2", 61.71, -15.5, 5.0),
        ("h20_3", 84.15, -4.95, 5.0),
        ("h20_4", 107.13, -3.61, 5.0),
        ("h20_5", 142.2, -1.55, 5.0),
        ("h20_6", 154.65, -5.54, 5.0),
        ("h20_7", 176.67, -3.92, 5.0),
        ("h20_8", 250.32, -4.96, 5.0),
    ],
    "thump14": [
        ("t14_1", 47.3, -9.6, 5.0),
        ("t14_2", 61.34, -11.82, 5.0),
        ("t14_3", 84.69, -10.09, 5.0),
        ("t14_4", 107.51, -7.64, 5.0),
        ("t14_5", 137.25, -3.76, 4.97),
        ("t14_6", 155.14, -6.89, 5.0),
        ("t14_7", 177.13, -4.95, 5.0),
        ("t14_8", 249.47, -4.7, 5.0),
    ],
    # hump20 with the 63 Hz region lifted back (about +5 dB at 60-64 Hz vs hump20)
    "thump20": [
        ("u20_1", 47.83, -4.06, 5.0),
        ("u20_2", 61.22, -8.85, 5.0),
        ("u20_3", 84.74, -5.19, 5.0),
        ("u20_4", 107.12, -3.92, 5.0),
        ("u20_5", 142.05, -1.69, 5.0),
        ("u20_6", 154.73, -5.53, 5.0),
        ("u20_7", 176.68, -3.96, 5.0),
        ("u20_8", 250.36, -5.0, 5.0),
    ],
    # as thump20 but the 45-52 Hz region (where output.mka booms) is cut harder
    "punch20": [
        ("p20_1", 47.29, -9.09, 5.0),
        ("p20_2", 60.97, -6.61, 5.0),
        ("p20_3", 84.94, -5.03, 5.0),
        ("p20_4", 107.11, -3.95, 5.0),
        ("p20_5", 142.31, -1.77, 5.0),
        ("p20_6", 154.85, -5.44, 5.0),
        ("p20_7", 176.64, -3.96, 5.0),
        ("p20_8", 250.36, -5.0, 5.0),
    ],
    # biggest 63 Hz restoration (about +11 dB at 60 Hz vs hump20); the room's strongest mode is here, so try last
    "thump20x": [
        ("x20_1", 47.65, -4.15, 5.0),
        ("x20_2", 60.94, -2.75, 5.0),
        ("x20_3", 85.25, -5.04, 5.0),
        ("x20_4", 107.1, -4.11, 5.0),
        ("x20_5", 141.75, -1.68, 5.0),
        ("x20_6", 154.67, -5.62, 4.99),
        ("x20_7", 176.73, -3.97, 5.0),
        ("x20_8", 250.38, -5.01, 5.0),
    ],
    # thump20x with 45-52 Hz cut harder (about -6 dB there vs thump20x), 63 Hz punch kept
    "punch20x": [
        ("q20_1", 47.06, -10.26, 5.0),
        ("q20_2", 60.66, -2.51, 5.0),
        ("q20_3", 85.3, -4.87, 5.0),
        ("q20_4", 107.09, -4.06, 5.0),
        ("q20_5", 142.27, -1.82, 5.0),
        ("q20_6", 154.88, -5.44, 4.99),
        ("q20_7", 176.64, -3.97, 5.0),
        ("q20_8", 250.37, -5.01, 5.0),
    ],
    # thump20x with 80-130 Hz cut harder (about -3 to -4 dB there vs thump20x), 45-52 Hz unchanged
    "tight20x": [
        ("w20_1", 47.65, -4.02, 5.0),
        ("w20_2", 60.96, -2.45, 5.0),
        ("w20_3", 85.25, -8.38, 5.0),
        ("w20_4", 107.68, -7.45, 5.0),
        ("w20_5", 136.21, -2.36, 4.99),
        ("w20_6", 154.93, -5.51, 5.0),
        ("w20_7", 176.74, -3.77, 5.0),
        ("w20_8", 250.32, -4.93, 5.0),
    ],
}
# punch20x plus two extra cuts on the 70-90 Hz "drone" region (found by comparing the quiet opening of the F1 clip
# with its loud section: the opening sits 63-92 Hz, the thump sits 56-63 Hz). Cuts go at 72 Hz (room dip) and 84-88 Hz.
FILTER_SETS["drone1"] = FILTER_SETS["punch20x"] + [("d1_1", 72.0, -4.0, 10.0), ("d1_2", 84.0, -4.0, 4.0)]
FILTER_SETS["drone2"] = FILTER_SETS["punch20x"] + [("d2_1", 72.0, -6.0, 8.0), ("d2_2", 84.0, -6.0, 4.0)]
FILTER_SETS["drone3"] = FILTER_SETS["punch20x"] + [("d3_1", 72.0, -8.0, 6.0), ("d3_2", 88.0, -8.0, 4.0)]
CHANNELS = [0, 1, 4, 5, 6, 7]

HEAD = """devices:
  samplerate: 48000
  chunksize: 1024

  capture:
    type: PipeWire
    channels: 8
    node_name: camilladsp-capture
    node_description: CamillaDSP Capture

  playback:
    type: PipeWire
    channels: 8
    node_name: camilladsp-playback
    node_description: CamillaDSP Playback
"""


def peaking_db(f, f0, gain, q):
    """Magnitude (dB) of an RBJ peaking biquad at frequency f."""
    if gain == 0:
        return 0.0
    a = 10 ** (gain / 40)
    w0 = 2 * math.pi * f0 / FS
    alpha = math.sin(w0) / (2 * q)
    b = [1 + alpha * a, -2 * math.cos(w0), 1 - alpha * a]
    d = [1 + alpha / a, -2 * math.cos(w0), 1 - alpha / a]
    z1 = cmath.exp(-1j * 2 * math.pi * f / FS)
    z2 = z1 * z1
    h = (b[0] + b[1] * z1 + b[2] * z2) / (d[0] + d[1] * z1 + d[2] * z2)
    return 20 * math.log10(abs(h))


# Time alignment and level trims measured at the seat on 21 Oct 2026 (delaytest2: mic at the listening position).
# Hardware channel index -> (name, delay ms, trim dB). Delays align every speaker to the farthest one (FR).
# Trims bring the five bed speakers to the front-left level (500-4000 Hz, slot energy) and leave the heights
# about 2 dB above the bed. LFE gets the front-left delay (the sub's own arrival time has not been measured).
ALIGN = {
    0: ("FL", 0.20, 0.0),
    1: ("FR", 0.00, -1.9),
    2: ("RL height", 4.60, -0.6),
    3: ("RR height", 4.70, -0.3),
    4: ("FC", 0.97, -0.8),
    5: ("LFE", 0.20, 0.0),
    6: ("SL", 3.00, -4.4),
    7: ("SR", 2.72, -0.7),
}


# Tone-match for the two ceiling heights, from MODULE 7 of the pan test (23 Oct 2026, each speaker alone, pink noise,
# seat position, relative to the mean of FL FR C SL SR). Heights were 3-5 dB low above 4 kHz (TFL -4.9, TFR -3.1)
# and both showed a bump of +4 to +8 dB at 250-315 Hz. REW sweeps of BL/BR on 19 Oct 2026 (before any DSP) agree: both
# peak at 250-315 Hz, about +10 to +12 dB over their own 400 Hz-1 kHz level, falling steeply above 315 Hz. Only broad, shared features are corrected: single 1/3-octave
# bins differ by 3-5 dB between the two heights in the 0.5-3 kHz range (ceiling reflections / comb filtering) and
# a one-seat measurement cannot be EQ'd narrowly. Re-measure after applying.
HEIGHT_TONE = [
    ("ht_290", {"type": "Peaking", "freq": 290, "gain": -7.0, "q": 1.5}),
    ("ht_hs", {"type": "Highshelf", "freq": 3000, "gain": 4.0, "q": 0.7}),
]
HEIGHT_CH = (2, 3)
HEIGHT_BUS = 8       # internal 9th channel: the sum of the two heights, low-passed, then added to the LFE


def height_blocks(hp, lfe_gain, tone, delay=0.0, invert=False):
    """Returns (filters_yaml, mixers_yaml, steps_yaml) for the heights-to-LFE bass management."""
    f = ""
    for ch in HEIGHT_CH:
        f += f"  h_hp_{ch}:\n    type: BiquadCombo\n    parameters: {{type: LinkwitzRileyHighpass, freq: {hp}, order: 4}}\n"
    f += f"  h_lp_bus:\n    type: BiquadCombo\n    parameters: {{type: LinkwitzRileyLowpass, freq: {hp}, order: 4}}\n"
    if delay > 0:
        f += f"  h_dly_bus:\n    type: Delay\n    parameters: {{delay: {delay}, unit: ms, subsample: false}}\n"
    if tone:
        for n, p in HEIGHT_TONE:
            f += f"  {n}:\n    type: Biquad\n    parameters: {{{', '.join(f'{k}: {v}' for k, v in p.items())}}}\n"
    m = "  heights_in:\n    channels: {in: 8, out: 9}\n    mapping:\n"
    for d in range(8):
        m += f"      - dest: {d}\n        sources:\n          - {{channel: {d}, gain: 0.0}}\n"
    m += f"      - dest: {HEIGHT_BUS}\n        sources:\n" + "".join(f"          - {{channel: {c}, gain: 0.0}}\n" for c in HEIGHT_CH)
    m += "  heights_out:\n    channels: {in: 9, out: 8}\n    mapping:\n"
    for d in range(8):
        if d == 5:
            m += f"      - dest: 5\n        sources:\n          - {{channel: 5, gain: 0.0}}\n          - {{channel: {HEIGHT_BUS}, gain: {lfe_gain}{', inverted: true' if invert else ''}}}\n"
        else:
            m += f"      - dest: {d}\n        sources:\n          - {{channel: {d}, gain: 0.0}}\n"
    st = "  - type: Mixer\n    name: heights_in\n"
    st += f"  - type: Filter\n    channels: [{HEIGHT_BUS}]\n    names:\n      - h_lp_bus\n" + ("      - h_dly_bus\n" if delay > 0 else "")
    for ch in HEIGHT_CH:
        names = [f"h_hp_{ch}"] + ([n for n, _ in HEIGHT_TONE] if tone else [])
        st += f"  - type: Filter\n    channels: [{ch}]\n    names:\n" + "".join(f"      - {n}\n" for n in names)
    st += "  - type: Mixer\n    name: heights_out\n"
    return f, m, st


INVERT_CH = {"FL": 0, "FR": 1, "RL": 2, "RR": 3, "FC": 4, "LFE": 5, "SL": 6, "SR": 7}


def build_config(chosen, align=None, invert=(), heights=None):
    """chosen: list of (name, freq, gain, q). Returns the CamillaDSP YAML text."""
    text = HEAD + "\nfilters:\n"
    for n, f, g, q in chosen:
        text += f"  {n}:\n    type: Biquad\n    parameters: {{type: Peaking, freq: {f}, gain: {g}, q: {q}}}\n"
    steps = ""
    hmix = ""
    if heights:
        hf, hmix, hst = height_blocks(**heights)
        text += hf
        steps += hst
    if chosen:
        steps += f"  - type: Filter\n    channels: {CHANNELS}\n    names:\n"
        steps += "".join(f"      - {n}\n" for n, *_ in chosen)
    for nm in invert:
        ch = INVERT_CH[nm]
        text += f"  inv_{ch}:\n    type: Gain\n    parameters: {{gain: 0.0, inverted: true, mute: false}}\n"
        steps += f"  - type: Filter\n    channels: [{ch}]\n    names:\n      - inv_{ch}\n"
    if align:
        for ch, (label, delay, trim) in ALIGN.items():
            if align == "bed" and ch in (2, 3):      # heights left exactly as they are
                continue
            names = []
            if delay > 0:
                text += f"  al_delay_{ch}:\n    type: Delay\n    parameters: {{delay: {delay}, unit: ms, subsample: false}}\n"
                names.append(f"al_delay_{ch}")
            if trim != 0:
                text += f"  al_gain_{ch}:\n    type: Gain\n    parameters: {{gain: {trim}, inverted: false, mute: false}}\n"
                names.append(f"al_gain_{ch}")
            if names:
                steps += f"  - type: Filter\n    channels: [{ch}]\n    names:\n" + "".join(f"      - {n}\n" for n in names)
    if hmix:
        text += "\nmixers:\n" + hmix
    text += "\npipeline:\n" + steps if steps else "\npipeline: []\n"
    return text


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    dry = "--dry" in sys.argv
    invert = []
    for x in sys.argv[1:]:
        if x.startswith("--invert="):
            invert = [v.strip().upper() for v in x.split("=", 1)[1].split(",") if v.strip()]
    heights = None
    if "--heights" in sys.argv:
        heights = {"hp": 120, "lfe_gain": 0.0, "tone": "--heights-tone" in sys.argv}
        for x in sys.argv[1:]:
            if x.startswith("--heights-hp="):
                heights["hp"] = float(x.split("=", 1)[1])
            elif x.startswith("--heights-lfe="):
                heights["lfe_gain"] = float(x.split("=", 1)[1])
            elif x.startswith("--heights-delay="):
                heights["delay"] = float(x.split("=", 1)[1])
        heights["invert"] = "--heights-invert" in sys.argv
    align = "bed" if "--align=bed" in sys.argv else ("all" if "--align" in sys.argv else None)
    setname, skip = "rew", set()
    for x in sys.argv[1:]:
        if x.startswith("--set="):
            setname = x.split("=", 1)[1]
        elif x.startswith("--skip="):
            skip = set(x.split("=", 1)[1].split(","))
    if setname not in FILTER_SETS:
        print(f"Unknown --set '{setname}'. Choose from: {', '.join(FILTER_SETS)}")
        sys.exit(1)
    if len(args) == 0 and setname != "rew":
        scale, max_f = 1.0, 300.0
    elif len(args) == 2:
        scale, max_f = float(args[0]), float(args[1])
    else:
        print(__doc__)
        sys.exit(1)
    filters = FILTER_SETS[setname]
    unknown = skip - {n for n, *_ in filters}
    if unknown:
        print("Unknown filter name(s) in --skip for this set:", ", ".join(sorted(unknown)))
        sys.exit(1)
    chosen = [(n, f, round(g * scale, 2), q) for n, f, g, q in filters if f <= max_f and n not in skip]
    print(f"Filter set: {setname}, scale {scale}, max {max_f:g} Hz, {len(chosen)} filters")
    if skip:
        print("Leaving these filters out:", ", ".join(sorted(skip)))

    print("Net filter response (dB, filtered channels):")
    for f in (40, 48, 52, 56, 60, 64, 68, 72, 85, 100, 125, 155, 200, 250, 1000):
        print(f"  {f:>5} Hz: {sum(peaking_db(f, f0, g, q) for _, f0, g, q in chosen):6.1f}")
    if align:
        print(f"Time alignment and trims (--align{'=bed: heights untouched' if align == 'bed' else ''}):")
        for ch, (label, delay, trim) in ALIGN.items():
            if align == "bed" and ch in (2, 3):
                print(f"  channel {ch} {label:<10} untouched")
                continue
            print(f"  channel {ch} {label:<10} delay {delay:5.2f} ms   trim {trim:+.1f} dB")
    if heights:
        print(f"Heights: LR4 high-pass at {heights['hp']:g} Hz on RL/RR height; their sum, LR4 low-passed at the same "
              f"frequency, joins the LFE at {heights['lfe_gain']:+.1f} dB" + (f", delayed {heights['delay']:g} ms" if heights.get("delay") else "") + (", polarity inverted" if heights.get("invert") else "") + ("; tone-match: " + ", ".join(
                  f"{p['type']} {p['freq']} Hz {p['gain']:+.1f} dB" for _, p in HEIGHT_TONE) if heights["tone"] else ""))
    if dry:
        return

    bad = [n for n in invert if n not in INVERT_CH]
    if bad:
        print("Unknown name(s) in --invert:", ", ".join(bad), "(use FL,FR,RL,RR,FC,LFE,SL,SR)")
        sys.exit(1)
    if invert:
        print("Polarity inverted on:", ", ".join(invert))
    text = build_config(chosen, align, invert, heights)
    exe = shutil.which("camilladsp") or "/usr/local/bin/camilladsp"
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as tmp:
        tmp.write(text)
    check = subprocess.run([exe, "-c", tmp.name], capture_output=True, text=True)
    if check.returncode != 0:
        print("Config check FAILED, nothing changed:\n", check.stdout, check.stderr)
        sys.exit(1)
    shutil.copy(tmp.name, CONFIG)
    os.unlink(tmp.name)
    was_via = ("mpv:output_FL", "camilladsp-capture:input_1") in current_links()
    # A full restart is slower than a reload signal but deterministic: the ports and filters come back
    # exactly as at boot. The links to CamillaDSP's ports are lost on restart, so they are rebuilt below.
    subprocess.run(["systemctl", "--user", "restart", "camilladsp.service"], check=True)
    print(f"\nWrote {CONFIG} and restarted CamillaDSP.")
    relink(was_via)


USB = "alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71"
PORTS = ["FL", "FR", "RL", "RR", "FC", "LFE", "SL", "SR"]


def pw(*a):
    return subprocess.run(["pw-link", *a], capture_output=True, text=True)


def port_list(flag):
    return {x.strip() for x in pw(flag).stdout.splitlines() if x.strip()}


def current_links():
    """Set of (source port, destination port) for every existing link."""
    out, port = set(), None
    for line in pw("-l").stdout.splitlines():
        if line and not line.startswith(" "):
            port = line.rstrip()
        elif "|->" in line and port is not None:
            out.add((port, line.split("|->", 1)[1].strip()))
    return out


def wait_for_ports(timeout):
    need_o = {f"camilladsp-playback:output_{n}" for n in range(1, 9)}
    need_i = {f"camilladsp-capture:input_{n}" for n in range(1, 9)}
    end = time.time() + timeout
    while time.time() < end:
        if need_o <= port_list("-o") and need_i <= port_list("-i"):
            return True
        time.sleep(0.5)
    return False


def direct_route():
    """mpv straight to the USB interface (no EQ). Used as a fallback so a problem never leaves you silent."""
    for p in PORTS:
        pw(f"mpv:output_{p}", f"{USB}:playback_{p}")


def relink(was_via):
    """After the restart: wait for CamillaDSP's ports, link its outputs to the USB interface, and, if mpv
    was going through CamillaDSP before, put it back. If anything fails, mpv falls back to a direct route."""
    mpv_up = "mpv:output_FL" in port_list("-o")
    if not wait_for_ports(float(os.environ.get("SETEQ_WAIT", "12"))):
        print("CamillaDSP's ports did not appear. Check: systemctl --user status camilladsp")
        if mpv_up and was_via:
            direct_route()
            print("Fell back to a direct route so you still have sound (no EQ).")
        return
    for n, p in enumerate(PORTS, 1):
        pw(f"camilladsp-playback:output_{n}", f"{USB}:playback_{p}")
    links = current_links()
    outs = sum((f"camilladsp-playback:output_{n}", f"{USB}:playback_{p}") in links for n, p in enumerate(PORTS, 1))
    print(f"CamillaDSP -> USB links: {outs}/8")
    if not mpv_up:
        print("mpv is not running. Start a film, then run ./route-mpv.sh on.")
        return
    if not was_via:
        print("mpv was playing directly and still is. Run ./route-mpv.sh on to hear the EQ.")
        return
    for n, p in enumerate(PORTS, 1):
        pw(f"mpv:output_{p}", f"camilladsp-capture:input_{n}")
    links = current_links()
    via = sum((f"mpv:output_{p}", f"camilladsp-capture:input_{n}") in links for n, p in enumerate(PORTS, 1))
    if outs == 8 and via == 8:
        for p in PORTS:
            pw("-d", f"mpv:output_{p}", f"{USB}:playback_{p}")
        print("mpv -> CamillaDSP -> USB restored (8/8 channels).")
    else:
        for n, p in enumerate(PORTS, 1):
            pw("-d", f"mpv:output_{p}", f"camilladsp-capture:input_{n}")
        direct_route()
        print(f"Could not rebuild the full path ({via}/8 in, {outs}/8 out). Fell back to a direct route (no EQ).")
        print("Check: systemctl --user status camilladsp   and   ./route-mpv.sh status")


if __name__ == "__main__":
    main()
