#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v stripe >/dev/null 2>&1; then
  echo "[ERROR] stripe CLI が見つかりません。"
  exit 1
fi

if [ ! -f .env ]; then
  echo "[ERROR] .env が見つかりません。.env.example をコピーして作成してください。"
  exit 1
fi

set -a
source ./.env
set +a

if [ -z "${STRIPE_SECRET_KEY:-}" ]; then
  echo "[ERROR] STRIPE_SECRET_KEY が .env に設定されていません。"
  exit 1
fi

stripe listen --print-secret
