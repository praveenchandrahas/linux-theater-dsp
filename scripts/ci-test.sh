#!/usr/bin/env bash
# The repository's full test suite, the same command in CI and on your machine. Needs python3 with PyYAML, numpy and scipy (python3-yaml
# python3-numpy python3-scipy). No PipeWire, CamillaDSP or audio hardware.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
bash tests/run.sh
