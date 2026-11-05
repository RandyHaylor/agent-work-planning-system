#!/usr/bin/env bash
# Clean-state end-to-end: fresh DB, bootstrap, start server, unit + integration tests, stop.
# PLANNER_PORT overrides the port (default 8787) if something else holds it.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PLANNER_PORT:-8787}"
docker compose down -v >/dev/null 2>&1 || true
docker compose up -d --wait
uv sync --extra test --quiet
OUT=$(uv run python -m server bootstrap)
echo "$OUT"
TOKEN=$(echo "$OUT" | sed -n 's/^ROOT_TOKEN=//p')
PLANNER_PORT="$PORT" uv run python -m server >/tmp/planner-server.log 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for i in $(seq 1 40); do
  curl -sk "https://localhost:$PORT/me" >/dev/null 2>&1 && break
  sleep 0.25
done
PLANNER_URL="https://localhost:$PORT" PLANNER_ROOT_TOKEN="$TOKEN" uv run pytest -q server tests
