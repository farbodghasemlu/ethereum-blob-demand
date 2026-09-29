#!/usr/bin/env bash
# Regenerate every table, figure and derived dataset from ../release (read-only).
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
for s in [0-9][0-9]_*.py; do echo "== $s"; $PY "$s" > "output/logs/${s%.py}.stdout.txt"; done
