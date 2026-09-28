#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATABASE_PATH="${1:-$ROOT_DIR/data/database/monitor.sqlite3}"

PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
  python -m brazil_monetary_policy_monitor.db "$DATABASE_PATH"
