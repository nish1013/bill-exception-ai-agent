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

web() {
  npm --prefix web "$@"
}

docker compose up -d --build --wait
run python manage.py migrate --database owner --noinput
run python manage.py seed_demo
run ruff format --check .
run ruff check .
run pytest -m "not timing"
# Other workers load the CPU. Wall-clock limits are measured with no parallel tests.
run pytest -m timing -n 0
run lint-imports

# The console generates its types from web/schema.graphql. It must match the API schema.
run python manage.py export_schema | diff -u web/schema.graphql -
web ci --ignore-scripts
web run lint
web run typecheck
web run test
web run build
npx --prefix web playwright install ${CI:+--with-deps} chromium
web run e2e
