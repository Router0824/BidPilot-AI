#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -n "${PORT:-}" || "${BIDPILOT_RELEASE_MODE:-}" == "1" ]]; then
  exec ./modelscope_release/start.sh
fi

python scripts/dev_start.py
