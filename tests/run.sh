#!/usr/bin/env bash
# Runs all tests. Needs python3 with PyYAML; no PipeWire, CamillaDSP or audio hardware.
set -e
cd "$(dirname "$0")"
python3 test_router.py
python3 test_seteq.py
python3 test_engine.py
python3 test_drift.py
python3 test_seekthumbs.py
bash -n ../scripts/install-autoroute.sh ../scripts/mpv-atmos ../scripts/route-mpv.sh ../scripts/rec.sh ../scripts/tone-test.sh ../scripts/preflight ../scripts/object-audio-install.sh ../scripts/mpv-object-audio && python3 -m py_compile ../tools/seekthumbs/seekthumbs.py && echo "PASS shell syntax"
