# shellcheck shell=bash disable=SC2034  # sourced by build-deb.sh, which uses these variables
# Package definition for kit/build-deb.sh (sourced; see Software-Defined-Home-Theatre/packaging/kit).
PKG=linux-theater-dsp
HOMEPAGE=https://github.com/praveenchandrahas/linux-theater-dsp
SUMMARY="PipeWire router, CamillaDSP profile generator and upmixers for a home theatre"
DESCRIPTION="The routing and DSP-configuration part of the Software Defined Home
Theatre project. The eq command (theater-route) keeps mpv linked into CamillaDSP
through PipeWire and switches the profile by what is playing; theater-set-eq
generates and loads the CamillaDSP configuration; the upmixers handle stereo and 5.1.
.
Written for one rig and one room. CamillaDSP is not in Ubuntu's repositories and is
not part of this package: get it from github.com/HEnquist/camilladsp (the sdht
install.sh does this with a checksum). This package does not enable or start any
service and does not write into any home folder; run theater-setup for that."
DEPENDS="python3, python3-yaml, pipewire-bin, systemd"
RECOMMENDS="python3-numpy, python3-scipy, pulseaudio-utils, wireplumber"
SUGGESTS="mpv, ffmpeg"
PYDIRS=/usr/lib/linux-theater-dsp

stage() {
  local L=/usr/lib/linux-theater-dsp
  for f in theater-route set-eq.py upmix_engine.py route-mpv.sh; do inst 755 "scripts/$f" "$L/$f"; done
  for f in upmix.py layout.py; do inst 644 "scripts/$f" "$L/$f"; done   # modules (no shebang); layout.py is started through roomtone-layout
  pyshebang "$L/theater-route" "$L/set-eq.py" "$L/upmix_engine.py"
  # `eq` decides what it is by its own name, so it is a symlink to theater-route (resolved to the real folder for its imports)
  link ../lib/linux-theater-dsp/theater-route /usr/bin/theater-route
  link ../lib/linux-theater-dsp/theater-route /usr/bin/eq
  script /usr/bin/roomtone-layout <<'X'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/linux-theater-dsp/layout.py "$@"
X
  script /usr/bin/theater-set-eq <<'X'
#!/bin/sh
# set-eq.py needs its sibling modules, so it is started from its own folder
exec /usr/bin/python3 /usr/lib/linux-theater-dsp/set-eq.py "$@"
X
  inst 755 packaging/theater-setup /usr/bin/theater-setup
  inst 644 packaging/theater-router.service /usr/lib/systemd/user/theater-router.service
  inst 644 packaging/theater-upmix.service /usr/lib/systemd/user/theater-upmix.service
  inst 644 configs/systemd/camilladsp.service.example /usr/share/doc/linux-theater-dsp/examples/camilladsp.service.example
  inst 644 configs/camilladsp/example-drone2-bed.yml /usr/share/doc/linux-theater-dsp/examples/example-drone2-bed.yml
  inst 644 tools/upmixtest/README.md /usr/share/doc/linux-theater-dsp/upmixtest-README.md
  manpage eq "switch the theatre EQ on or off and show the routing status (the theater-route command)"
  manpage theater-route "keep mpv linked into CamillaDSP through PipeWire and pick the profile by what plays"
  manpage theater-set-eq "generate and load the CamillaDSP configuration for a profile"
  manpage roomtone-layout "detect, write and validate the speaker layout file"
  manpage theater-setup "enable or disable the linux-theater-dsp user services for one user" "Subcommands: install, uninstall, check. Option: --dry-run."
}
