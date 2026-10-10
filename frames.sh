#!/usr/bin/env bash
# Thin wrapper: runs frames.py with python3 (or python on Windows).
PY=$(command -v python3 || command -v python) || { echo "Python 3 not found" >&2; exit 1; }
exec "$PY" "$(dirname "$0")/frames.py" "$@"
