#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/P4_web"
FRONTEND_DIR="$ROOT_DIR/P4_web_client"
LEGACY_DIR="$ROOT_DIR/P4_legacy_runner"
LEGACY_APP_DIR="${P4_STACK_LEGACY_APP_DIR:-$ROOT_DIR/../P4_app}"
OS_NAME="$(uname -s)"

BACKEND_HOST="${P4_STACK_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${P4_STACK_BACKEND_PORT:-8000}"
FRONTEND_HOST="${P4_STACK_FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${P4_STACK_FRONTEND_PORT:-5173}"
LEGACY_IMAGE="${P4_STACK_LEGACY_IMAGE:-p4-legacy-runner}"
LEGACY_BASE_IMAGE="${P4_STACK_LEGACY_BASE_IMAGE:-s.egorkin/heinz_p4:latest}"
LEGACY_DOCKER_NETWORK_MODE="${P4_STACK_LEGACY_DOCKER_NETWORK_MODE:-auto}"
SESSION_ID="p4-stack-$$-$(date +%s)"

BACKEND_PID=""
FRONTEND_PID=""
STARTED_ANY=0
BACKEND_UVICORN=()
LEGACY_DOCKER_NETWORK_FLAG=""
LEGACY_DOCKER_NETWORK_DESCRIPTION=""
RESTARTED_ANY=0

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

find_listening_pids() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u
}

wait_for_port_state() {
  local host="$1"
  local port="$2"
  local expected="$3"
  local attempts="${4:-20}"
  local delay="${5:-0.25}"
  local state=""
  local i=0

  while [ "$i" -lt "$attempts" ]; do
    state="$(port_in_use "$host" "$port")"
    if [ "$state" = "$expected" ]; then
      return 0
    fi
    sleep "$delay"
    i=$((i + 1))
  done

  return 1
}

stop_port_listeners() {
  local service_name="$1"
  local host="$2"
  local port="$3"
  local pids=""

  pids="$(find_listening_pids "$port")"
  if [ -z "$pids" ]; then
    echo "Port $port is busy, but no listening PID was found for $service_name" >&2
    exit 1
  fi

  echo "==> Restarting $service_name: stopping listener(s) on port $port: $(echo "$pids" | tr '\n' ' ' | xargs)"
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    kill "$pid" >/dev/null 2>&1 || true
  done <<EOF
$pids
EOF

  if wait_for_port_state "$host" "$port" free 20 0.25; then
    RESTARTED_ANY=1
    return 0
  fi

  echo "==> Forcing $service_name listener(s) to stop on port $port"
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    kill -9 "$pid" >/dev/null 2>&1 || true
  done <<EOF
$pids
EOF

  if wait_for_port_state "$host" "$port" free 20 0.25; then
    RESTARTED_ANY=1
    return 0
  fi

  echo "Failed to free port $port for $service_name" >&2
  exit 1
}

resolve_legacy_docker_network() {
  case "$LEGACY_DOCKER_NETWORK_MODE" in
    auto)
      case "$OS_NAME" in
        Linux)
          LEGACY_DOCKER_NETWORK_FLAG="--network=host"
          LEGACY_DOCKER_NETWORK_DESCRIPTION="host"
          ;;
        Darwin)
          LEGACY_DOCKER_NETWORK_FLAG=""
          LEGACY_DOCKER_NETWORK_DESCRIPTION="default bridge"
          ;;
        *)
          LEGACY_DOCKER_NETWORK_FLAG=""
          LEGACY_DOCKER_NETWORK_DESCRIPTION="default bridge"
          ;;
      esac
      ;;
    host)
      LEGACY_DOCKER_NETWORK_FLAG="--network=host"
      LEGACY_DOCKER_NETWORK_DESCRIPTION="host"
      ;;
    bridge)
      LEGACY_DOCKER_NETWORK_FLAG=""
      LEGACY_DOCKER_NETWORK_DESCRIPTION="default bridge"
      ;;
    *)
      echo "Unsupported P4_STACK_LEGACY_DOCKER_NETWORK_MODE: $LEGACY_DOCKER_NETWORK_MODE" >&2
      echo "Expected one of: auto, host, bridge" >&2
      exit 1
      ;;
  esac
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
require_command lsof
resolve_backend_uvicorn
resolve_legacy_docker_network
require_file "$LEGACY_DIR/Dockerfile"
require_file "$LEGACY_APP_DIR/interface.py"
require_file "$FRONTEND_DIR/index.html"

BACKEND_PORT_STATE="$(port_in_use "$BACKEND_HOST" "$BACKEND_PORT")"
FRONTEND_PORT_STATE="$(port_in_use "$FRONTEND_HOST" "$FRONTEND_PORT")"

if [ "$OS_NAME" = "Darwin" ] && [ "$LEGACY_DOCKER_NETWORK_MODE" = "auto" ]; then
  echo "==> macOS detected; using Docker Desktop default bridge network for legacy runner"
elif [ -n "$LEGACY_DOCKER_NETWORK_DESCRIPTION" ]; then
  echo "==> Legacy runner Docker network: $LEGACY_DOCKER_NETWORK_DESCRIPTION"
fi

echo "==> Building legacy runner image: $LEGACY_IMAGE"
echo "==> Legacy runner base image: $LEGACY_BASE_IMAGE"
docker build \
  --build-arg "BASE_IMAGE=$LEGACY_BASE_IMAGE" \
  -t "$LEGACY_IMAGE" \
  "$LEGACY_DIR"

LEGACY_RUNNER_COMMAND=$(
  cat <<EOF
docker run --rm --label p4.stack_session=$SESSION_ID $LEGACY_DOCKER_NETWORK_FLAG -e P4_WEB_JOB_PARAMETERS -e P4_WEB_JOB_KIND -v $LEGACY_APP_DIR:/opt/P4_app:ro -v {project_path}:/work/project $LEGACY_IMAGE run-web-job --operation {operation} --project-path /work/project --language {language}
EOF
)

if [ "$BACKEND_PORT_STATE" = "busy" ]; then
  stop_port_listeners "backend" "$BACKEND_HOST" "$BACKEND_PORT"
fi

if [ "$FRONTEND_PORT_STATE" = "busy" ]; then
  stop_port_listeners "frontend" "$FRONTEND_HOST" "$FRONTEND_PORT"
fi

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

echo "==> Starting frontend on http://$FRONTEND_HOST:$FRONTEND_PORT"
(
  cd "$FRONTEND_DIR"
  python3 -m http.server "$FRONTEND_PORT" --bind "$FRONTEND_HOST"
) &
FRONTEND_PID=$!
STARTED_ANY=1

echo
echo "P4 stack is up:"
echo "  Backend:  http://$BACKEND_HOST:$BACKEND_PORT"
echo "  Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo
if [ "$RESTARTED_ANY" -eq 1 ]; then
  echo "Existing listeners were restarted before launch."
fi
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
