#!/usr/bin/env bash
set -euo pipefail

export HOSTNAME="${HOSTNAME:-0.0.0.0}"
export PORT="${PORT:-10000}"

mkdir -p output/web

if [[ "${RUN_ANALYSIS_ON_STARTUP:-0}" == "1" && ! -f output/web/latest_report.json ]]; then
  echo "No web snapshot found. Running initial analysis before starting the dashboard..."
  python main.py --quiet --no-charts --no-html || echo "Initial analysis failed; dashboard will start with an empty snapshot."
fi

cd dashboard
exec npm run start -- -H "$HOSTNAME" -p "$PORT"
