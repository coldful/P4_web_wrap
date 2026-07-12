#!/usr/bin/env bash
# Upload a code update to the server staging area (rsync over SSH).
# Same destination as SFTP uploads to /updates/.
#
# Usage:
#   P4_UPLOAD_HOST=ubuntu@SERVER_IP ./deploy/upload_update.sh [all|frontend|backend|legacy|p4-app]

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if [[ -f "$SCRIPT_DIR/config.env" ]]; then
  # shellcheck disable=SC1090
  source "$SCRIPT_DIR/config.env"
fi

P4_UPLOAD_HOST="${P4_UPLOAD_HOST:-${P4_DEPLOY_HOST:-}}"
P4_UPLOAD_SSH_KEY="${P4_UPLOAD_SSH_KEY:-${P4_DEPLOY_SSH_KEY:-}}"
P4_REMOTE_STAGING="${P4_REMOTE_STAGING:-${P4_UPDATE_STAGING:-/srv/p4/incoming/updates}}"
P4_LOCAL_WEB_WRAP="${P4_LOCAL_WEB_WRAP:-$REPO_ROOT}"
P4_LOCAL_P4_APP="${P4_LOCAL_P4_APP:-$REPO_ROOT/../P4_app}"
P4_REMOTE_WEB_WRAP="${P4_REMOTE_WEB_WRAP:-/srv/p4/app/P4_web_wrap}"

RSYNC_SSH="ssh"
if [[ -n "$P4_UPLOAD_SSH_KEY" ]]; then
  RSYNC_SSH="ssh -i $P4_UPLOAD_SSH_KEY -o StrictHostKeyChecking=accept-new"
fi

COMPONENT="${1:-all}"

usage() {
  cat <<'EOF'
Usage: upload_update.sh [COMPONENT]

Upload to server staging for apply_update.sh (or SFTP to /updates/ manually).

Components: all | frontend | backend | legacy | p4-app

After upload, on server:
  /srv/p4/bin/apply-update all
EOF
}

require_host() {
  if [[ -z "$P4_UPLOAD_HOST" ]]; then
    usage
    fail "Set P4_UPLOAD_HOST or P4_DEPLOY_HOST in deploy/config.env"
  fi
}

rsync_to_staging() {
  local src="$1"
  local dest_subpath="$2"
  [[ -e "$src" ]] || fail "Local path not found: $src"
  log "Upload $src -> $P4_UPLOAD_HOST:$P4_REMOTE_STAGING/$dest_subpath"
  rsync -avz --delete "${P4_RSYNC_EXCLUDES[@]}" \
    -e "$RSYNC_SSH" \
    "$src/" \
    "$P4_UPLOAD_HOST:$P4_REMOTE_STAGING/$dest_subpath/"
}

rsync_file_to_staging() {
  local src="$1"
  local dest_path="$2"
  [[ -f "$src" ]] || fail "Local file not found: $src"
  log "Upload $src -> $P4_UPLOAD_HOST:$dest_path"
  rsync -avz -e "$RSYNC_SSH" "$src" "$P4_UPLOAD_HOST:$dest_path"
}

upload_scripts() {
  log "Upload deploy scripts -> $P4_UPLOAD_HOST:$P4_REMOTE_WEB_WRAP/deploy"
  rsync -avz "${P4_RSYNC_EXCLUDES[@]}" \
    -e "$RSYNC_SSH" \
    "$SCRIPT_DIR/" \
    "$P4_UPLOAD_HOST:$P4_REMOTE_WEB_WRAP/deploy/"
  ssh ${P4_UPLOAD_SSH_KEY:+-i "$P4_UPLOAD_SSH_KEY"} -o StrictHostKeyChecking=accept-new \
    "$P4_UPLOAD_HOST" "chmod +x $P4_REMOTE_WEB_WRAP/deploy/*.sh"
}

upload_frontend() {
  rsync_to_staging "$P4_LOCAL_WEB_WRAP/P4_web_client" "P4_web_wrap/P4_web_client"
}

upload_backend() {
  rsync_to_staging "$P4_LOCAL_WEB_WRAP/P4_web/src" "P4_web_wrap/P4_web/src"
  rsync_file_to_staging \
    "$P4_LOCAL_WEB_WRAP/P4_web/pyproject.toml" \
    "$P4_REMOTE_STAGING/P4_web_wrap/P4_web/pyproject.toml"
  rsync_file_to_staging \
    "$P4_LOCAL_WEB_WRAP/requirements.txt" \
    "$P4_REMOTE_STAGING/P4_web_wrap/requirements.txt"
}

upload_legacy() {
  rsync_to_staging "$P4_LOCAL_WEB_WRAP/P4_legacy_runner" "P4_web_wrap/P4_legacy_runner"
}

upload_p4_app() {
  rsync_to_staging "$P4_LOCAL_P4_APP" "P4_app"
}

case "${COMPONENT:-}" in
  -h|--help|help) usage; exit 0 ;;
  all)
    require_host
    upload_scripts
    upload_frontend
    upload_backend
    upload_legacy
    if [[ -d "$P4_LOCAL_P4_APP" ]]; then
      upload_p4_app
    else
      log "Skip P4_app (not found at $P4_LOCAL_P4_APP)"
    fi
    log "Upload complete. On server: /srv/p4/bin/apply-update all"
    ;;
  frontend) require_host; upload_frontend ;;
  backend) require_host; upload_backend ;;
  legacy) require_host; upload_legacy ;;
  p4-app) require_host; upload_p4_app ;;
  *) usage; fail "Unknown component: $COMPONENT" ;;
esac
