#!/usr/bin/env bash
# Start Inside the Game. Uses Foundry if .env exists, otherwise runs fully offline.
#   ./run.sh            -> http://localhost:8000
#   ./run.sh --offline  -> ignore .env (no model calls)
cd "$(dirname "$0")"
if [ "$1" != "--offline" ] && [ -f .env ]; then set -a; . ./.env; set +a; fi
[ -f src/itg/static/index.html ] || (cd frontend && npm install --legacy-peer-deps && npm run build)
echo "Open http://localhost:8000  (phone on same Wi-Fi: http://$(ipconfig getifaddr en0 2>/dev/null):8000)"
PYTHONPATH=src exec .venv311/bin/uvicorn itg.server:app --host 0.0.0.0 --port 8000
