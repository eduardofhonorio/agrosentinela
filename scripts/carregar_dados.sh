#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../backend"
source .venv/bin/activate
python -m app.seed
python -m app.etl.pipeline
