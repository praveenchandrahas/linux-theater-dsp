#!/usr/bin/env bash
# Router, config-generation and upmix-engine tests. Needs python3 with PyYAML, numpy and scipy. No PipeWire, CamillaDSP or audio hardware.
set -e
cd "$(dirname "$0")"
python3 test_router.py
python3 test_status.py
python3 test_seteq.py
python3 test_engine.py
python3 test_layout.py
python3 test_layout_golden.py
bash -n ../scripts/install-autoroute.sh ../scripts/route-mpv.sh ../scripts/make-default.sh && echo "PASS shell syntax"
