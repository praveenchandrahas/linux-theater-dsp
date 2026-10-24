#!/usr/bin/env bash
# Installs the automatic mpv -> CamillaDSP routing and the `eq` on/off command.
#   ./install-autoroute.sh          install (safe to re-run; also how you update)
#   ./install-autoroute.sh remove   stop and remove it again (mpv then plays directly, as before)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$HOME/.local/bin
UNITDIR=$HOME/.config/systemd/user
UNIT=theater-router.service

if [ "${1:-}" = remove ]; then
  systemctl --user disable --now "$UNIT" 2>/dev/null
  systemctl --user disable --now theater-upmix.service 2>/dev/null
  rm -f "$UNITDIR/$UNIT" "$UNITDIR/theater-upmix.service" "$BIN/theater-route" "$BIN/eq" "$BIN/set-eq.py" "$BIN/upmix.py" "$BIN/upmix_engine.py"
  systemctl --user daemon-reload
  echo "Removed. mpv stays on whatever route it has now; restart mpv to get direct sound."
  exit 0
fi

[ -f "$HERE/theater-route" ] || { echo "theater-route must be in the same folder as this script."; exit 1; }
command -v pw-link >/dev/null || { echo "pw-link not found (install pipewire-bin)."; exit 1; }

mkdir -p "$BIN" "$UNITDIR"
if [ -e "$BIN/eq" ] && [ "$(readlink "$BIN/eq")" != "theater-route" ]; then
  echo "$BIN/eq already exists and is not ours. Remove or rename it, then re-run."; exit 1
fi
install -m 755 "$HERE/theater-route" "$BIN/theater-route"
ln -sf theater-route "$BIN/eq"
# The router switches CamillaDSP profiles by running set-eq.py, and the adaptive upmix engine runs from upmix_engine.py: keep them beside it.
for f in set-eq.py upmix.py upmix_engine.py; do
  [ -f "$HERE/$f" ] || { echo "$f must be in the same folder as this script."; exit 1; }
  install -m 755 "$HERE/$f" "$BIN/$f"
done
python3 -c "import numpy, scipy" 2>/dev/null || echo "NOTE: numpy and scipy are needed by upmix_engine.py (pip install --user numpy scipy, or your distro's python3-numpy python3-scipy). Without them the stereo upmix falls back to the fixed matrix."

cat > "$UNITDIR/$UNIT" <<UNITEOF
[Unit]
Description=Route mpv through CamillaDSP automatically
After=pipewire.service camilladsp.service
Wants=camilladsp.service

[Service]
ExecStart=$BIN/theater-route daemon
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
UNITEOF

# The adaptive upmix engine: started and stopped by the router while the stereo-ad profile is active, so it is not enabled at boot.
cat > "$UNITDIR/theater-upmix.service" <<UNITEOF
[Unit]
Description=Adaptive ambience engine for the stereo upmix (started by theater-router)
After=pipewire.service

[Service]
ExecStart=/usr/bin/env python3 $BIN/upmix_engine.py run
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
UNITEOF

systemctl --user daemon-reload
systemctl --user enable --now "$UNIT" || { echo "Could not enable $UNIT"; exit 1; }

echo
echo "== Start at boot =="
state=$(systemctl --user is-enabled camilladsp.service 2>&1)
echo "camilladsp.service: $state"
if [ "$state" != enabled ]; then
  systemctl --user enable camilladsp.service 2>&1 | sed 's/^/  /'
  echo "camilladsp.service now: $(systemctl --user is-enabled camilladsp.service 2>&1)"
fi
linger=$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)
echo "Linger (user services start at boot, before anyone logs in): ${linger:-unknown}"
[ "$linger" = no ] && echo "  If this PC does not auto-login to the desktop, run once:  loginctl enable-linger $USER"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "NOTE: $BIN is not in your PATH yet. Log out and in once, or use $BIN/eq" ;; esac

echo
sleep 1.5
"$BIN/eq" status
echo
echo "Switch:  eq off | eq on | eq toggle | eq status        Log: journalctl --user -u $UNIT -f"
