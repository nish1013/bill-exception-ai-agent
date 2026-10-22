#!/usr/bin/env bash
# The model key lives only in worker-propose-ai (D54). The api and web containers and the
# console bundle must hold none. Runs against the Compose stack, after the web build.
set -euo pipefail

cd "$(dirname "$0")/.."
KEY_PATTERN='(^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}'
failed=0

for service in api web; do
  if docker compose exec -T "$service" env | grep -q '^OPENAI_API_KEY='; then
    echo "check-llm-key: the $service container has OPENAI_API_KEY" >&2
    failed=1
  fi
done

if [ ! -d web/dist ]; then
  echo "check-llm-key: web/dist is missing. Build the console first" >&2
  failed=1
elif grep -rEl "$KEY_PATTERN" web/dist; then
  echo "check-llm-key: web/dist holds a key pattern" >&2
  failed=1
fi
if docker compose exec -T web grep -rEl "$KEY_PATTERN" /usr/share/nginx/html; then
  echo "check-llm-key: the web image holds a key pattern" >&2
  failed=1
fi
if [ -n "${OPENAI_API_KEY:-}" ] && grep -rlF "$OPENAI_API_KEY" web/dist; then
  echo "check-llm-key: web/dist holds the OPENAI_API_KEY value" >&2
  failed=1
fi

exit "$failed"
