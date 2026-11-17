#!/usr/bin/env bash
# AgroSentinela - instalação (Linux/Mac)
set -e
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
(cd frontend && npm install)
echo "Instalação concluída. Revise o .env e rode: scripts/carregar_dados.sh"
