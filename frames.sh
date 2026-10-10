#!/usr/bin/env bash
# Thin wrapper: runs frames.py with the first Python (3.8+) it finds.
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    exec "$c" "$(dirname "$0")/frames.py" "$@"
  fi
done
echo "Python 3.8+ not found" >&2; exit 1
