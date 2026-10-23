#!/usr/bin/env bash
# Makes the standing profile permanent and automatic. Safe to re-run.
#
#   ./make-default.sh            apply it
#   ./make-default.sh --check    only report; change nothing
#
# What "the standing profile" means: ./set-eq.py with no arguments = --set=drone2 --align --heights --heights-tone
# (bass EQ, measured delays and trims, heights high-passed with their bass sent to the sub, heights tone-matched).
#
# What it sets up, and why that survives a reboot:
#   1. ~/.config/camilladsp/config.yml  gets the profile (set-eq.py validates it with `camilladsp -c` first).
#      CamillaDSP reads this file every time it starts, so the profile is the default from then on.
#   2. camilladsp.service and theater-router.service are enabled (start with your session; linger covers boot without login).
#   3. mpv-atmos calls `eq ensure` first, which starts either service if it is down, then the router links mpv to CamillaDSP.
#   4. EQ switch set to ON.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
CHECK=0; [ "${1:-}" = "--check" ] && CHECK=1
BIN=$HOME/.local/bin
say() { printf '%s\n' "$*"; }
bad=0

if [ "$CHECK" = 0 ]; then
  [ -x "$HERE/set-eq.py" ] || chmod +x "$HERE/set-eq.py"
  say "== 1. applying the profile =="
  "$HERE/set-eq.py" || { say "set-eq.py failed; nothing else was changed."; exit 1; }
  say
  say "== 2. services =="
  [ -x "$BIN/theater-route" ] || "$HERE/install-autoroute.sh" || { say "install-autoroute.sh failed"; exit 1; }
  # keep the installed router and eq command in step with this checkout (adds `eq ensure`)
  install -m 755 "$HERE/theater-route" "$BIN/theater-route"
  systemctl --user daemon-reload
  systemctl --user enable camilladsp.service theater-router.service 2>&1 | sed 's/^/  /'
  systemctl --user start camilladsp.service theater-router.service 2>&1 | sed 's/^/  /'
  command -v eq >/dev/null || ln -sf theater-route "$BIN/eq"
  "$BIN/eq" on >/dev/null 2>&1
fi

say "== check =="
for u in camilladsp.service theater-router.service; do
  en=$(systemctl --user is-enabled "$u" 2>&1); ac=$(systemctl --user is-active "$u" 2>&1)
  say "  $u: enabled=$en active=$ac"; [ "$en" = enabled ] && [ "$ac" = active ] || bad=1
done
lg=$(loginctl show-user "${USER:-$(id -un)}" -p Linger --value 2>/dev/null)
say "  linger: ${lg:-unknown}"
[ "$lg" = no ] && say "  (only needed if this PC does not log in to the desktop by itself; then run: loginctl enable-linger ${USER:-$(id -un)})"
CFG=$HOME/.config/camilladsp/config.yml
if grep -q "heights_in" "$CFG" 2>/dev/null && grep -q "ht_trim" "$CFG" && grep -q "al_delay_" "$CFG" && grep -q "d2_1:" "$CFG"; then
  say "  config.yml: standing profile present"
else
  say "  config.yml: standing profile NOT present"; bad=1
fi

# mpv-atmos: make it call `eq ensure` (the repo copy already does; this patches the copy you actually run)
M=$(command -v mpv-atmos || true)
if [ -n "$M" ] && [ -f "$M" ]; then
  if grep -q "eq ensure" "$M"; then
    say "  mpv-atmos ($M): already calls eq ensure"
  elif [ "$CHECK" = 1 ]; then
    say "  mpv-atmos ($M): does NOT call eq ensure yet (run without --check to add it)"; bad=1
  elif [ -w "$M" ]; then
    cp -n "$M" "$M.bak" && sed -i '1a command -v eq >/dev/null \&\& eq ensure   # added by make-default.sh' "$M" \
      && say "  mpv-atmos ($M): added the eq ensure line (backup: $M.bak)"
  else
    say "  mpv-atmos ($M): not writable; add this line after the first line yourself:  command -v eq >/dev/null && eq ensure"; bad=1
  fi
else
  say "  mpv-atmos: not found in PATH (the repo copy scripts/mpv-atmos already has the line); if yours lives elsewhere, add after its first line:"
  say "      command -v eq >/dev/null && eq ensure"
fi
say
"$BIN/eq" status 2>/dev/null || true
[ "$bad" = 0 ] && say "=> all set." || say "=> something above needs attention."
exit "$bad"
