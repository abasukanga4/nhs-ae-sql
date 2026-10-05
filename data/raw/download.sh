#!/usr/bin/env bash
# Compatibility entry point; validates pinned source hashes before replacing files.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python "$ROOT/load.py" --download
