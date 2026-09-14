#!/usr/bin/env bash
set -Eeuo pipefail

OBS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OBS_FRONTEND="$OBS_ROOT/frontend"
OBS_BACKEND_PID=""
OBS_FRONTEND_PID=""

fail() {
  echo "Dispute Observatory: $*" >&2
  exit 1
}

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$OBS_FRONTEND_PID" ]] && kill -0 "$OBS_FRONTEND_PID" 2>/dev/null; then
    kill "$OBS_FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$OBS_BACKEND_PID" ]] && kill -0 "$OBS_BACKEND_PID" 2>/dev/null; then
    kill "$OBS_BACKEND_PID" 2>/dev/null || true
  fi
  [[ -z "$OBS_FRONTEND_PID" ]] || wait "$OBS_FRONTEND_PID" 2>/dev/null || true
  [[ -z "$OBS_BACKEND_PID" ]] || wait "$OBS_BACKEND_PID" 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 130' INT TERM

for command in uv npm curl; do
  command -v "$command" >/dev/null 2>&1 || fail "missing required command: $command"
done

[[ -x "$OBS_FRONTEND/node_modules/.bin/vite" ]] || fail "frontend dependencies missing; run: cd frontend && npm install"
(
  cd "$OBS_ROOT"
  uv run python -c "import fastapi, sse_starlette, uvicorn" >/dev/null
) || fail "backend API dependencies missing; run: uv sync --extra dev --extra graph --extra api"

echo "Dispute Observatory: starting backend on http://127.0.0.1:8000"
(
  cd "$OBS_ROOT"
  if [[ -f "$OBS_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$OBS_ROOT/.env"
    set +a
  fi
  exec uv run uvicorn api.app:app --app-dir src --host 127.0.0.1 --port 8000
) &
OBS_BACKEND_PID=$!

for _ in {1..80}; do
  kill -0 "$OBS_BACKEND_PID" 2>/dev/null || fail "backend exited before becoming healthy"
  if curl --silent --fail http://127.0.0.1:8000/api/v1/health >/dev/null; then
    break
  fi
  sleep 0.25
done
curl --silent --fail http://127.0.0.1:8000/api/v1/health >/dev/null || fail "backend health check timed out"
echo "Dispute Observatory: backend healthy"

echo "Dispute Observatory: starting frontend on http://127.0.0.1:5173"
(
  cd "$OBS_FRONTEND"
  exec env -u OPENAI_API_KEY ./node_modules/.bin/vite --host 127.0.0.1 --port 5173 --strictPort
) &
OBS_FRONTEND_PID=$!

for _ in {1..80}; do
  kill -0 "$OBS_FRONTEND_PID" 2>/dev/null || fail "frontend exited before becoming ready"
  if curl --silent --fail http://127.0.0.1:5173 >/dev/null; then
    break
  fi
  sleep 0.25
done
curl --silent --fail http://127.0.0.1:5173 >/dev/null || fail "frontend health check timed out"

echo "Dispute Observatory: ready at http://127.0.0.1:5173 (Ctrl-C to stop)"
while kill -0 "$OBS_BACKEND_PID" 2>/dev/null && kill -0 "$OBS_FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
fail "a development server stopped unexpectedly"
