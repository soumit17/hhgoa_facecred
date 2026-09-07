#!/usr/bin/env bash
# Convenience launcher for local development: starts the FastAPI backend and the
# Vite dev server together, and stops both on Ctrl-C.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "→ backend  http://localhost:8000  (docs at /docs)"
( cd backend && "$PYTHON" -m uvicorn app.main:app --reload --port 8000 ) &
BACK=$!

echo "→ frontend http://localhost:5173"
( cd frontend && npm run dev ) &
FRONT=$!

trap 'kill $BACK $FRONT 2>/dev/null || true' EXIT INT TERM
wait
