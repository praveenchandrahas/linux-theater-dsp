#!/usr/bin/env bash
# Runs all tests. Needs python3 with PyYAML; no PipeWire, CamillaDSP or audio hardware.
set -e
cd "$(dirname "$0")"
python3 test_router.py
python3 test_seteq.py
bash -n ../scripts/route-mpv.sh ../scripts/rec.sh ../scripts/tone-test.sh ../scripts/install-autoroute.sh && echo "PASS shell syntax"
