#!/usr/bin/env bash
set -euo pipefail

cd /app

mkdir -p ./data/uploads

PORT="${PORT:-7860}"

exec uvicorn modelscope_release.server:app --host 0.0.0.0 --port "${PORT}"

