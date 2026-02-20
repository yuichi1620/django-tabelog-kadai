#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${ROOT_DIR}/backups"
DB_PATH="${ROOT_DIR}/db.sqlite3"

mkdir -p "${BACKUP_DIR}"

timestamp="$(date +"%Y%m%d_%H%M%S")"
backup_path="${BACKUP_DIR}/db_${timestamp}.sqlite3"

cp "${DB_PATH}" "${backup_path}"
echo "Backup created: ${backup_path}"
