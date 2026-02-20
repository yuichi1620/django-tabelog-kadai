#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "[ERROR] .env が見つかりません。.env.example をコピーして作成してください。"
  exit 1
fi

set -a
source ./.env
set +a

source venv/bin/activate
python manage.py runserver
