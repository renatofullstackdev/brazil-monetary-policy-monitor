#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT/web"

PORT="${PORT:-8000}"
exec python -m http.server "$PORT" --bind 127.0.0.1
