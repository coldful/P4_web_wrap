#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/P4_web"
FRONTEND_DIR="$ROOT_DIR/P4_web_client"
LEGACY_DIR="$ROOT_DIR/P4_legacy_runner"
VENV_DIR="$BACKEND_DIR/venv"
PYTHON_BIN="${P4_STACK_PYTHON_BIN:-python3}"
LEGACY_APP_DIR="${P4_STACK_LEGACY_APP_DIR:-$ROOT_DIR/../P4_app}"

log() {
  echo "==> $*"
}

fail() {
  echo "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Missing required command: $1"
  fi
}

require_file() {
  if [ ! -e "$1" ]; then
    fail "Missing required path: $1"
  fi
}

check_python_version() {
  "$PYTHON_BIN" - <<'PY'
import sys

if sys.version_info < (3, 12):
    raise SystemExit(
        f"python3 3.12+ is required, found {sys.version.split()[0]}"
    )
PY
}

ensure_venv() {
  if [ -x "$VENV_DIR/bin/python" ]; then
    log "Using existing virtual environment: $VENV_DIR"
    return 0
  fi

  if [ -e "$VENV_DIR" ]; then
    fail "Virtual environment path exists but is incomplete: $VENV_DIR"
  fi

  log "Creating virtual environment: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
}

install_python_dependencies() {
  log "Installing Python dependencies"
  "$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"
}

ensure_env_file() {
  if [ -f "$BACKEND_DIR/.env" ]; then
    log "Keeping existing backend config: $BACKEND_DIR/.env"
    return 0
  fi

  log "Creating backend config from template"
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
}

init_database() {
  log "Initializing backend database"
  (
    cd "$BACKEND_DIR"
    "$VENV_DIR/bin/p4web" init-db
  )
}

check_docker() {
  log "Checking Docker availability"
  if ! docker info >/dev/null 2>&1; then
    fail "Docker daemon is not available. Start Docker before running run_p4_stack.sh"
  fi
}

print_summary() {
  echo
  echo "P4 stack preparation is complete."
  echo "  Python:   $("$VENV_DIR/bin/python" --version 2>&1)"
  echo "  Venv:     $VENV_DIR"
  echo "  Backend:  $BACKEND_DIR"
  echo "  Frontend: $FRONTEND_DIR"
  echo "  Legacy:   $LEGACY_APP_DIR"
  echo
  echo "Next step:"
  echo "  ./run_p4_stack.sh"
}

require_command "$PYTHON_BIN"
require_command docker
require_file "$ROOT_DIR/requirements.txt"
require_file "$BACKEND_DIR/pyproject.toml"
require_file "$BACKEND_DIR/.env.example"
require_file "$FRONTEND_DIR/index.html"
require_file "$LEGACY_DIR/Dockerfile"
require_file "$LEGACY_APP_DIR/interface.py"

log "Checking Python version"
check_python_version
ensure_venv
install_python_dependencies
ensure_env_file
init_database
check_docker
print_summary
