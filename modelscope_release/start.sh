#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d /app/app ]]; then
  cd /app
else
  cd "${SCRIPT_DIR}/.."
fi

mkdir -p ./data/uploads

PORT="${PORT:-7860}"

exec uvicorn modelscope_release.server:app --host 0.0.0.0 --port "${PORT}"
