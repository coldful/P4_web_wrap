#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/P4_web"
FRONTEND_DIR="$ROOT_DIR/P4_web_client"
LEGACY_DIR="$ROOT_DIR/P4_legacy_runner"
LEGACY_APP_DIR="${P4_STACK_LEGACY_APP_DIR:-$ROOT_DIR/../P4_app}"

BACKEND_HOST="${P4_STACK_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${P4_STACK_BACKEND_PORT:-8000}"
FRONTEND_HOST="${P4_STACK_FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${P4_STACK_FRONTEND_PORT:-5173}"
LEGACY_IMAGE="${P4_STACK_LEGACY_IMAGE:-p4-legacy-runner}"
SESSION_ID="p4-stack-$$-$(date +%s)"

BACKEND_PID=""
FRONTEND_PID=""
STARTED_ANY=0
BACKEND_UVICORN=()

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_file() {
  if [ ! -e "$1" ]; then
    echo "Missing required path: $1" >&2
    exit 1
  fi
}

resolve_backend_uvicorn() {
  local candidate=""

  for candidate in \
    "$BACKEND_DIR/venv/bin/uvicorn" \
    "$BACKEND_DIR/.venv/bin/uvicorn"
  do
    if [ -x "$candidate" ]; then
      BACKEND_UVICORN=("$candidate")
      return 0
    fi
  done

  candidate="$(command -v uvicorn || true)"
  if [ -n "$candidate" ]; then
    BACKEND_UVICORN=("$candidate")
    return 0
  fi

  echo "Missing uvicorn. Checked:" >&2
  echo "  - $BACKEND_DIR/venv/bin/uvicorn" >&2
  echo "  - $BACKEND_DIR/.venv/bin/uvicorn" >&2
  echo "  - uvicorn in PATH" >&2
  exit 1
}

port_in_use() {
  local host="$1"
  local port="$2"
  python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
family = socket.AF_INET6 if ":" in host else socket.AF_INET
sock = socket.socket(family, socket.SOCK_STREAM)
sock.settimeout(0.2)
try:
    sock.bind((host, port))
except OSError:
    print("busy")
    raise SystemExit(0)
finally:
    sock.close()
print("free")
PY
}

cleanup() {
  set +e

  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi

  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi

  docker ps -aq --filter "label=p4.stack_session=$SESSION_ID" | while read -r container_id; do
    [ -n "$container_id" ] || continue
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  done
}

trap cleanup EXIT INT TERM

require_command docker
require_command python3
resolve_backend_uvicorn
require_file "$LEGACY_DIR/Dockerfile"
require_file "$LEGACY_APP_DIR/interface.py"
require_file "$FRONTEND_DIR/index.html"

BACKEND_PORT_STATE="$(port_in_use "$BACKEND_HOST" "$BACKEND_PORT")"
FRONTEND_PORT_STATE="$(port_in_use "$FRONTEND_HOST" "$FRONTEND_PORT")"

echo "==> Building legacy runner image: $LEGACY_IMAGE"
docker build -t "$LEGACY_IMAGE" "$LEGACY_DIR"

LEGACY_RUNNER_COMMAND=$(
  cat <<EOF
docker run --rm --label p4.stack_session=$SESSION_ID --network=host -e P4_WEB_JOB_PARAMETERS -e P4_WEB_JOB_KIND -v $LEGACY_APP_DIR:/opt/P4_app:ro -v {project_path}:/work/project $LEGACY_IMAGE run-web-job --operation {operation} --project-path /work/project --language {language}
EOF
)

if [ "$BACKEND_PORT_STATE" = "free" ]; then
  echo "==> Starting backend on http://$BACKEND_HOST:$BACKEND_PORT"
  (
    cd "$BACKEND_DIR"
    P4_WEB_ENABLE_LEGACY_RUNNER=true \
    P4_WEB_LEGACY_P4_APP_PATH="$LEGACY_APP_DIR" \
    P4_WEB_LEGACY_RUNNER_COMMAND="$LEGACY_RUNNER_COMMAND" \
    "${BACKEND_UVICORN[@]}" p4_web.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
  ) &
  BACKEND_PID=$!
  STARTED_ANY=1
else
  echo "==> Backend already running on http://$BACKEND_HOST:$BACKEND_PORT; leaving it in place"
fi

if [ "$FRONTEND_PORT_STATE" = "free" ]; then
  echo "==> Starting frontend on http://$FRONTEND_HOST:$FRONTEND_PORT"
  (
    cd "$FRONTEND_DIR"
    python3 -m http.server "$FRONTEND_PORT" --bind "$FRONTEND_HOST"
  ) &
  FRONTEND_PID=$!
  STARTED_ANY=1
else
  echo "==> Frontend already running on http://$FRONTEND_HOST:$FRONTEND_PORT; leaving it in place"
fi

echo
echo "P4 stack is up:"
echo "  Backend:  http://$BACKEND_HOST:$BACKEND_PORT"
echo "  Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo
if [ "$STARTED_ANY" -eq 1 ]; then
  echo "Press Ctrl+C to stop everything started by this script."
else
  echo "Nothing new was started; both services were already up."
fi

if [ "$STARTED_ANY" -eq 0 ]; then
  exit 0
fi

WAIT_PIDS=()
if [ -n "$BACKEND_PID" ]; then
  WAIT_PIDS+=("$BACKEND_PID")
fi
if [ -n "$FRONTEND_PID" ]; then
  WAIT_PIDS+=("$FRONTEND_PID")
fi

wait -n "${WAIT_PIDS[@]}"
