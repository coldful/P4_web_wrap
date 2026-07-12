# Shared deploy helpers. Source from deploy/*.sh:
#   source "$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

log() { echo "==> $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

P4_RSYNC_EXCLUDES=(
  --exclude 'venv/'
  --exclude '.venv/'
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude '.git/'
  --exclude 'P4_web/var/'
  --exclude '.env'
  --exclude 'deploy/config.env'
  --exclude 'temp/'
)

p4_install_backend_deps() {
  local web_wrap="$1"
  local dry_run="${2:-0}"
  local venv="$web_wrap/P4_web/venv"
  local req="$web_wrap/requirements.txt"

  if [[ ! -x "$venv/bin/pip" ]]; then
    fail "Backend venv missing: $venv — run prepare_p4_stack.sh on the server first"
  fi
  if [[ ! -f "$req" ]]; then
    fail "requirements.txt missing: $req"
  fi
  if [[ ! -f "$web_wrap/P4_web/pyproject.toml" ]]; then
    fail "pyproject.toml missing: $web_wrap/P4_web/pyproject.toml"
  fi

  log "Installing Python dependencies (editable P4_web)"
  if [[ "$dry_run" -eq 1 ]]; then
    echo "  [dry-run] cd $web_wrap/P4_web && $venv/bin/pip install -r ../requirements.txt"
    return 0
  fi
  (
    cd "$web_wrap/P4_web"
    "$venv/bin/pip" install -r ../requirements.txt
  )
}

p4_rebuild_legacy_runner() {
  local web_wrap="$1"
  local dry_run="${2:-0}"
  local image="${P4_LEGACY_RUNNER_IMAGE:-p4-legacy-runner}"
  local base="${P4_LEGACY_BASE_IMAGE:-s.egorkin/heinz_p4:latest}"
  local context="$web_wrap/P4_legacy_runner"

  [[ -f "$context/Dockerfile" ]] || fail "Legacy Dockerfile missing: $context/Dockerfile"
  command -v docker >/dev/null 2>&1 || fail "docker command not found"

  log "Building Docker image: $image"
  if [[ "$dry_run" -eq 1 ]]; then
    echo "  [dry-run] docker build --build-arg BASE_IMAGE=$base -t $image $context"
    return 0
  fi
  docker build \
    --build-arg "BASE_IMAGE=$base" \
    -t "$image" \
    "$context"
}

p4_restart_web_service() {
  local dry_run="${1:-0}"
  local service="${P4_WEB_SERVICE:-p4-web}"
  [[ -n "$service" ]] || return 0

  if [[ "$dry_run" -eq 1 ]]; then
    echo "  [dry-run] systemctl restart $service"
    return 0
  fi
  if systemctl is-enabled "$service" >/dev/null 2>&1; then
    log "Restarting service: $service"
    sudo systemctl restart "$service"
  else
    log "Service not enabled, skip restart: $service"
  fi
}

p4_reload_nginx() {
  local dry_run="${1:-0}"
  local service="${P4_NGINX_SERVICE:-nginx}"
  [[ -n "$service" ]] || return 0

  if [[ "$dry_run" -eq 1 ]]; then
    echo "  [dry-run] systemctl reload $service"
    return 0
  fi
  if systemctl is-enabled "$service" >/dev/null 2>&1; then
    log "Reloading $service"
    sudo systemctl reload "$service"
  fi
}

p4_verify_deployment() {
  local web_wrap="$1"
  local dry_run="${2:-0}"
  local health_url="${P4_HEALTH_URL:-http://127.0.0.1:8000/api/health}"

  if [[ "$dry_run" -eq 1 ]]; then
    echo "  [dry-run] verify deployment at $health_url"
    return 0
  fi

  local failed=0

  if curl -sf "$health_url" >/dev/null 2>&1; then
    log "Health check OK: $health_url"
  else
    echo "WARNING: backend health check failed: $health_url" >&2
    failed=1
  fi

  local -a static_files=(
    "$web_wrap/P4_web_client/index.html"
    "$web_wrap/P4_web_client/reduced/index.html"
    "$web_wrap/P4_web_client/reduced/reduced.js"
    "$web_wrap/P4_web_client/src/legacy-images/gtk-open.png"
    "$web_wrap/P4_web/src/p4_web/main.py"
    "$web_wrap/P4_legacy_runner/Dockerfile"
  )
  for file in "${static_files[@]}"; do
    if [[ -f "$file" ]]; then
      log "Present: ${file#"$web_wrap/"}"
    else
      echo "WARNING: expected file missing: $file" >&2
      failed=1
    fi
  done

  if command -v docker >/dev/null 2>&1; then
    local image="${P4_LEGACY_RUNNER_IMAGE:-p4-legacy-runner}"
    if docker image inspect "$image" >/dev/null 2>&1; then
      log "Docker image present: $image"
    else
      echo "WARNING: Docker image missing: $image (run legacy deploy)" >&2
      failed=1
    fi
  fi

  return "$failed"
}
