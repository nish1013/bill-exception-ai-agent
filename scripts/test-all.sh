#!/usr/bin/env bash
# CI runs this same script (D56).
set -euo pipefail

cd "$(dirname "$0")/.."
RESULTS=test-results
rm -rf "$RESULTS"
mkdir -p "$RESULTS"

finish() {
  status=$?
  if [ "$status" -ne 0 ]; then
    docker compose logs --no-color > "$RESULTS/compose.log" 2>&1 || true
    echo "test-all failed (exit $status). Service logs: $RESULTS/compose.log" >&2
  fi
  docker compose down
  exit "$status"
}
trap finish EXIT

run() {
  docker compose exec -T api uv run "$@"
}

docker compose up -d --build --wait
run python manage.py migrate --database owner --noinput
run ruff format --check .
run ruff check .
run pytest
run lint-imports
