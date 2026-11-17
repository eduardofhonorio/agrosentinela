#!/usr/bin/env bash
# Sobe API e frontend; Ctrl+C encerra os dois.
cd "$(dirname "$0")/.."
(cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev) &
trap "kill 0" EXIT
wait
