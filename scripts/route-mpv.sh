#!/usr/bin/env bash
# Usage: ./route-mpv.sh on|off|status
#   on      mpv -> CamillaDSP -> USB interface (bass EQ active)
#   off     mpv -> USB interface directly (as before)
#   status  show where each mpv channel goes right now
#
# Run while a film is playing (mpv's ports only exist then); re-run for each new mpv session.
#
# Safe by design: it checks that CamillaDSP is really there, links CamillaDSP's outputs to the USB
# interface itself, builds the new route BEFORE removing the old one, and rolls back if anything
# is missing. A failed 'on' leaves you with direct sound, never silence.
set -u
USB=alsa_output.usb-0d8c_USB_Sound_Device-00.analog-surround-71
PORTS=(FL FR RL RR FC LFE SL SR)
MODE=${1:-}
case "$MODE" in on|off|status) ;; *) echo "usage: $0 on|off|status"; exit 1 ;; esac

# "src -> dst" for every existing link
links() { pw-link -l 2>/dev/null | awk '/^[^ ]/ {port=$0; next} /\|->/ {sub(/^ *\|-> /,""); print port " -> " $0}'; }
LINKS=""
refresh() { LINKS=$(links); }
has() { grep -qxF -- "$1 -> $2" <<<"$LINKS"; }
add() { has "$1" "$2" || { pw-link "$1" "$2" 2>/dev/null; refresh; }; }
del() { if has "$1" "$2"; then pw-link -d "$1" "$2" 2>/dev/null; refresh; fi; }

OUT=$(pw-link -o 2>/dev/null)
IN=$(pw-link -i 2>/dev/null)
exists_out() { grep -qxF -- "$1" <<<"$OUT"; }
exists_in() { grep -qxF -- "$1" <<<"$IN"; }

show_status() {
  refresh
  local direct=0 via=0 outs=0 silent=0 i p n d v o
  for i in 0 1 2 3 4 5 6 7; do
    p=${PORTS[$i]}; n=$((i + 1)); d=0; v=0; o=0
    has "mpv:output_$p" "$USB:playback_$p" && d=1
    has "mpv:output_$p" "camilladsp-capture:input_$n" && v=1
    has "camilladsp-playback:output_$n" "$USB:playback_$p" && o=1
    direct=$((direct + d)); via=$((via + v)); outs=$((outs + o))
    if [ $d -eq 0 ] && { [ $v -eq 0 ] || [ $o -eq 0 ]; }; then silent=$((silent + 1)); fi
  done
  echo "mpv -> USB direct: $direct/8   mpv -> CamillaDSP: $via/8   CamillaDSP -> USB: $outs/8"
  if [ $silent -gt 0 ]; then echo "WARNING: $silent/8 channels have no working path (silent)."; fi
}

if [ "$MODE" = status ]; then
  if exists_out "mpv:output_FL"; then show_status; else echo "mpv ports not found. Is a film playing?"; fi
  exit 0
fi

exists_out "mpv:output_FL" || { echo "mpv ports not found. Is a film playing?"; exit 1; }
exists_in "$USB:playback_FL" || { echo "USB interface ($USB) not found. Card names can change after a reboot: check 'pw-link -i | grep usb'."; exit 1; }
refresh

if [ "$MODE" = on ]; then
  for n in 1 2 3 4 5 6 7 8; do
    if ! exists_in "camilladsp-capture:input_$n" || ! exists_out "camilladsp-playback:output_$n"; then
      echo "CamillaDSP ports not found, so nothing was changed (mpv still plays directly)."
      echo "Check: systemctl --user status camilladsp"
      exit 1
    fi
  done
  # 1. CamillaDSP -> USB (these do not survive a CamillaDSP restart, so make sure they exist)
  for i in 0 1 2 3 4 5 6 7; do add "camilladsp-playback:output_$((i + 1))" "$USB:playback_${PORTS[$i]}"; done
  # 2. mpv -> CamillaDSP, while the direct route still exists
  for i in 0 1 2 3 4 5 6 7; do add "mpv:output_${PORTS[$i]}" "camilladsp-capture:input_$((i + 1))"; done
  # 3. verify the whole new path before breaking the old one
  bad=0
  for i in 0 1 2 3 4 5 6 7; do
    p=${PORTS[$i]}; n=$((i + 1))
    has "mpv:output_$p" "camilladsp-capture:input_$n" && has "camilladsp-playback:output_$n" "$USB:playback_$p" || bad=1
  done
  if [ $bad -eq 1 ]; then
    for i in 0 1 2 3 4 5 6 7; do del "mpv:output_${PORTS[$i]}" "camilladsp-capture:input_$((i + 1))"; done
    echo "Could not build the full path mpv -> CamillaDSP -> USB, so I rolled back. mpv still plays directly."
    show_status
    exit 1
  fi
  # 4. now drop the direct route
  for i in 0 1 2 3 4 5 6 7; do del "mpv:output_${PORTS[$i]}" "$USB:playback_${PORTS[$i]}"; done
  echo "Routed through CamillaDSP (bass EQ on)."
else
  for i in 0 1 2 3 4 5 6 7; do add "mpv:output_${PORTS[$i]}" "$USB:playback_${PORTS[$i]}"; done
  bad=0
  for i in 0 1 2 3 4 5 6 7; do has "mpv:output_${PORTS[$i]}" "$USB:playback_${PORTS[$i]}" || bad=1; done
  if [ $bad -eq 1 ]; then echo "Could not link mpv to the USB interface; leaving the CamillaDSP route in place."; show_status; exit 1; fi
  for i in 0 1 2 3 4 5 6 7; do del "mpv:output_${PORTS[$i]}" "camilladsp-capture:input_$((i + 1))"; done
  echo "Direct to the USB interface (bass EQ off)."
fi
show_status
