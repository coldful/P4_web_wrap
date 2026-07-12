#!/usr/bin/env bash
# Deploy P4_web_wrap (and optionally P4_app) to a remote server via rsync + SSH.
#
# Setup:
#   cp deploy/config.env.example deploy/config.env
#   edit deploy/config.env
#
# Usage:
#   ./deploy/deploy.sh              # deploy everything
#   ./deploy/deploy.sh frontend     # P4_web_client only
#   ./deploy/deploy.sh backend      # P4_web + pip + restart
#   ./deploy/deploy.sh legacy       # P4_legacy_runner + docker build
#   ./deploy/deploy.sh p4-app       # P4_app + docker build
#   ./deploy/deploy.sh scripts      # deploy/ helpers only

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if [[ -f "$SCRIPT_DIR/config.env" ]]; then
  # shellcheck disable=SC1090
  source "$SCRIPT_DIR/config.env"
fi

P4_DEPLOY_HOST="${P4_DEPLOY_HOST:-}"
P4_DEPLOY_SSH_KEY="${P4_DEPLOY_SSH_KEY:-}"
P4_LOCAL_WEB_WRAP="${P4_LOCAL_WEB_WRAP:-$REPO_ROOT}"
P4_LOCAL_P4_APP="${P4_LOCAL_P4_APP:-$REPO_ROOT/../P4_app}"
P4_REMOTE_WEB_WRAP="${P4_REMOTE_WEB_WRAP:-/srv/p4/app/P4_web_wrap}"
P4_REMOTE_P4_APP="${P4_REMOTE_P4_APP:-/srv/p4/app/P4_app}"
P4_LEGACY_RUNNER_IMAGE="${P4_LEGACY_RUNNER_IMAGE:-p4-legacy-runner}"
P4_LEGACY_BASE_IMAGE="${P4_LEGACY_BASE_IMAGE:-s.egorkin/heinz_p4:latest}"
P4_WEB_SERVICE="${P4_WEB_SERVICE:-p4-web}"
P4_NGINX_SERVICE="${P4_NGINX_SERVICE:-nginx}"
P4_HEALTH_URL="${P4_HEALTH_URL:-http://127.0.0.1:8000/api/health}"

RSYNC_SSH="ssh"
if [[ -n "$P4_DEPLOY_SSH_KEY" ]]; then
  RSYNC_SSH="ssh -i $P4_DEPLOY_SSH_KEY -o StrictHostKeyChecking=accept-new"
fi

COMPONENT="${1:-all}"

usage() {
  cat <<'EOF'
Usage: deploy.sh [COMPONENT]

Deploy project code to the server (rsync over SSH, then restart services).

Components:
  all        scripts + frontend + backend + legacy (+ P4_app if present)
  frontend   P4_web_client (main UI + reduced UI + assets)
  backend    P4_web/src, pyproject.toml, requirements.txt + pip install
  legacy     P4_legacy_runner + docker build
  p4-app     P4_app + docker build
  scripts    deploy/ helpers on the server

Configuration: deploy/config.env (see config.env.example)
EOF
}

require_host() {
  if [[ -z "$P4_DEPLOY_HOST" ]]; then
    usage
    fail "Set P4_DEPLOY_HOST in deploy/config.env"
  fi
}

rsync_up() {
  local src="$1"
  local dest="$2"
  if [[ ! -e "$src" ]]; then
    fail "Local path not found: $src"
  fi
  log "Upload $src -> $P4_DEPLOY_HOST:$dest"
  rsync -avz --delete "${P4_RSYNC_EXCLUDES[@]}" \
    -e "$RSYNC_SSH" \
    "$src/" \
    "$P4_DEPLOY_HOST:$dest/"
}

rsync_file() {
  local src="$1"
  local dest="$2"
  [[ -f "$src" ]] || fail "Local file not found: $src"
  log "Upload $src -> $P4_DEPLOY_HOST:$dest"
  rsync -avz -e "$RSYNC_SSH" "$src" "$P4_DEPLOY_HOST:$dest"
}

ssh_run() {
  local -a cmd=(ssh -o StrictHostKeyChecking=accept-new)
  if [[ -n "$P4_DEPLOY_SSH_KEY" ]]; then
    cmd+=(-i "$P4_DEPLOY_SSH_KEY")
  fi
  cmd+=("$P4_DEPLOY_HOST" "$@")
  log "Remote: $*"
  "${cmd[@]}"
}

remote_exec() {
  local body="$1"
  ssh_run "bash -s" <<REMOTE
set -euo pipefail
P4_WEB_WRAP="$P4_REMOTE_WEB_WRAP"
P4_LEGACY_RUNNER_IMAGE="$P4_LEGACY_RUNNER_IMAGE"
P4_LEGACY_BASE_IMAGE="$P4_LEGACY_BASE_IMAGE"
P4_WEB_SERVICE="$P4_WEB_SERVICE"
P4_NGINX_SERVICE="$P4_NGINX_SERVICE"
P4_HEALTH_URL="$P4_HEALTH_URL"
# shellcheck source=/dev/null
source "$P4_REMOTE_WEB_WRAP/deploy/common.sh"
$body
REMOTE
}

deploy_scripts() {
  rsync_up "$SCRIPT_DIR" "$P4_REMOTE_WEB_WRAP/deploy"
  ssh_run "chmod +x $P4_REMOTE_WEB_WRAP/deploy/*.sh"
  ssh_run "bash -s" <<REMOTE
set -euo pipefail
if [[ -d /srv/p4/bin ]]; then
  cat >/tmp/p4-apply-update <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec $P4_REMOTE_WEB_WRAP/deploy/apply_update.sh "\$@"
EOF
  sudo mv /tmp/p4-apply-update /srv/p4/bin/apply-update
  sudo chmod 755 /srv/p4/bin/apply-update
fi
REMOTE
}

sync_frontend() {
  rsync_up "$P4_LOCAL_WEB_WRAP/P4_web_client" "$P4_REMOTE_WEB_WRAP/P4_web_client"
}

sync_backend() {
  rsync_up "$P4_LOCAL_WEB_WRAP/P4_web/src" "$P4_REMOTE_WEB_WRAP/P4_web/src"
  rsync_file "$P4_LOCAL_WEB_WRAP/P4_web/pyproject.toml" "$P4_REMOTE_WEB_WRAP/P4_web/pyproject.toml"
  rsync_file "$P4_LOCAL_WEB_WRAP/requirements.txt" "$P4_REMOTE_WEB_WRAP/requirements.txt"
}

sync_legacy() {
  rsync_up "$P4_LOCAL_WEB_WRAP/P4_legacy_runner" "$P4_REMOTE_WEB_WRAP/P4_legacy_runner"
}

sync_p4_app() {
  if [[ ! -d "$P4_LOCAL_P4_APP" ]]; then
    fail "P4_app not found: $P4_LOCAL_P4_APP"
  fi
  rsync_up "$P4_LOCAL_P4_APP" "$P4_REMOTE_P4_APP"
}

activate_backend() {
  remote_exec '
p4_install_backend_deps "$P4_WEB_WRAP" 0
p4_restart_web_service 0
'
}

activate_legacy() {
  remote_exec '
p4_rebuild_legacy_runner "$P4_WEB_WRAP" 0
p4_restart_web_service 0
'
}

activate_all() {
  remote_exec '
p4_install_backend_deps "$P4_WEB_WRAP" 0
p4_rebuild_legacy_runner "$P4_WEB_WRAP" 0
p4_reload_nginx 0
p4_restart_web_service 0
p4_verify_deployment "$P4_WEB_WRAP" 0 || true
'
}

deploy_frontend() {
  sync_frontend
  remote_exec 'p4_reload_nginx 0'
}

deploy_backend() {
  sync_backend
  activate_backend
  remote_exec 'p4_verify_deployment "$P4_WEB_WRAP" 0 || true'
}

deploy_legacy() {
  sync_legacy
  activate_legacy
}

deploy_p4_app() {
  sync_p4_app
  activate_legacy
}

deploy_all() {
  deploy_scripts
  sync_frontend
  sync_backend
  sync_legacy
  if [[ -d "$P4_LOCAL_P4_APP" ]]; then
    sync_p4_app
  else
    log "Skip P4_app (not found at $P4_LOCAL_P4_APP)"
  fi
  activate_all
}

case "${COMPONENT:-}" in
  -h|--help|help) usage; exit 0 ;;
  all) require_host; deploy_all; log "Deploy complete" ;;
  scripts) require_host; deploy_scripts; log "Deploy scripts updated" ;;
  frontend) require_host; deploy_frontend; log "Frontend deployed" ;;
  backend) require_host; deploy_backend; log "Backend deployed" ;;
  legacy) require_host; deploy_legacy; log "Legacy runner deployed" ;;
  p4-app) require_host; deploy_p4_app; log "P4_app deployed" ;;
  *) usage; fail "Unknown component: $COMPONENT" ;;
esac
