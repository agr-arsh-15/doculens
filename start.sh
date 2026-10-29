#!/usr/bin/env bash
# Starts the DocuLens API (port 8000) and the Vite dev server (port 5173).
set -e
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "Creating Python virtualenv and installing backend dependencies..."
  python3 -m venv .venv
  .venv/bin/pip install -r backend/requirements.txt
fi

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend dependencies..."
  (cd frontend && npm install)
fi

.venv/bin/python backend/run.py &
BACKEND_PID=$!
trap "kill $BACKEND_PID 2>/dev/null" INT TERM EXIT
echo "API: http://127.0.0.1:8000/docs"

cd frontend
npm run dev -- --host 127.0.0.1
