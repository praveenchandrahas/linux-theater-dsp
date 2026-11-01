#!/usr/bin/env bash
# Smoke test of the INSTALLED linux-theater-dsp package (run after `apt install ./linux-theater-dsp_*.deb`). It uses a throw-away HOME, a
# simulated PipeWire (tests/fake-pw-link from this checkout) and never needs audio hardware, PipeWire or CamillaDSP.
#   scripts/ci-smoke.sh [REPO_DIR]
set -euo pipefail
REPO=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
H=$(mktemp -d); trap 'rm -rf "$H"' EXIT
export HOME=$H ROOMTONE_LAYOUT=$H/layout.yml XDG_CONFIG_HOME=$H/.config
fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }
for c in eq theater-route theater-set-eq roomtone-layout theater-setup; do command -v "$c" >/dev/null || fail "$c is not on PATH"; done
case "$(command -v eq)" in /usr/bin/eq) ;; *) fail "eq resolves to $(command -v eq), not the packaged /usr/bin/eq" ;; esac
[ -f /usr/lib/systemd/user/theater-router.service ] || fail "router unit missing"
grep -q '^ExecStart=/usr/bin/theater-route daemon' /usr/lib/systemd/user/theater-router.service || fail "unit ExecStart"

echo "== layout: presets, init, validate"
roomtone-layout --presets >/dev/null
roomtone-layout --init 5.1.2 >/dev/null
[ -f "$ROOMTONE_LAYOUT" ] || fail "--init wrote no file"
roomtone-layout --validate | tee "$H/v.txt"

echo "== set-eq generates a CamillaDSP profile (--dry: nothing is written or loaded)"
theater-set-eq --dry >"$H/seteq.txt" 2>&1 || { cat "$H/seteq.txt"; fail "set-eq --dry"; }
grep -q 'channel 0' "$H/seteq.txt" || fail "set-eq output has no channel table"
theater-set-eq --write-config="$H/cfg.yml" >/dev/null 2>&1 || fail "set-eq --write-config"
grep -q 'heights_in' "$H/cfg.yml" || fail "generated config lacks the standing profile"

echo "== router status against a simulated PipeWire graph"
FAKE=$REPO/tests/fake-pw-link
[ -f "$FAKE" ] || fail "tests/fake-pw-link not found (pass the repo dir)"
python3 - "$H" <<'PY'
import importlib.machinery, importlib.util, json, sys
l = importlib.machinery.SourceFileLoader("trs", "/usr/lib/linux-theater-dsp/theater-route")
T = importlib.util.module_from_spec(importlib.util.spec_from_loader("trs", l)); l.exec_module(T)
st = {"out": [], "in": [f"{T.USB}:playback_{p}" for p in T.PORTS], "links": []}
for n in range(1, 9):
    st["out"].append(f"camilladsp-playback:output_{n}"); st["in"].append(f"camilladsp-capture:input_{n}")
    st["links"].append([f"camilladsp-playback:output_{n}", f"{T.USB}:playback_{T.PORTS[n - 1]}"])
json.dump(st, open(sys.argv[1] + "/pw.json", "w"))
PY
printf '# theater-profile: film\nd2_1:\nal_delay_1:\nheights_in:\nht_trim:\n' >"$H/config.yml"
export FAKE_PW_STATE=$H/pw.json THEATER_PW_LINK=$FAKE THEATER_STATE_DIR=$H/state THEATER_CAMILLA_CONFIG=$H/config.yml
eq status --json >"$H/status.json" 2>"$H/status.err" || true
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("status keys:", ", ".join(sorted(d)[:8]))' "$H/status.json" || { cat "$H/status.err"; fail "eq status --json is not JSON"; }

echo "== setup command (dry run only: it must print, not change)"
theater-setup --dry-run install | tee "$H/setup.txt"
grep -q 'would run: systemctl --user enable --now theater-router.service' "$H/setup.txt" || fail "dry-run text"
theater-setup --dry-run uninstall >/dev/null
[ ! -e "$H/.config/systemd" ] || fail "theater-setup --dry-run created ~/.config/systemd"
[ -z "$(find "$H" -newer "$H/layout.yml" -path "$H/.config/systemd*" 2>/dev/null)" ] || fail "units written into the home folder"

echo "SMOKE OK (linux-theater-dsp)"
