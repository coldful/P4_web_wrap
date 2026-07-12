#!/usr/bin/env bash
# Apply a code update staged under P4_UPDATE_STAGING (uploaded via SFTP/rsync).
#
# Run on the server:
#   ./deploy/apply_update.sh [all|frontend|backend|legacy|p4-app] [--dry-run]
#
# Installed copy: /srv/p4/bin/apply-update

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

CONFIG_FILE="${P4_DEPLOY_CONFIG:-/srv/p4/config.env}"
if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
elif [[ -f "$SCRIPT_DIR/config.env" ]]; then
  # shellcheck disable=SC1090
  source "$SCRIPT_DIR/config.env"
fi

COMMON_SH="$SCRIPT_DIR/common.sh"
if [[ ! -f "$COMMON_SH" && -n "${P4_WEB_WRAP:-}" ]]; then
  COMMON_SH="$P4_WEB_WRAP/deploy/common.sh"
fi
if [[ ! -f "$COMMON_SH" ]]; then
  COMMON_SH="/srv/p4/app/P4_web_wrap/deploy/common.sh"
fi
if [[ ! -f "$COMMON_SH" ]]; then
  echo "ERROR: common.sh not found — run ./deploy/deploy.sh scripts first" >&2
  exit 1
fi
# shellcheck source=common.sh
source "$COMMON_SH"

P4_SRV_ROOT="${P4_SRV_ROOT:-/srv/p4}"
P4_UPDATE_STAGING="${P4_UPDATE_STAGING:-$P4_SRV_ROOT/incoming/updates}"
P4_BACKUP_ROOT="${P4_BACKUP_ROOT:-$P4_SRV_ROOT/backups}"
P4_WEB_WRAP="${P4_WEB_WRAP:-$P4_SRV_ROOT/app/P4_web_wrap}"
P4_LEGACY_APP="${P4_LEGACY_APP:-$P4_SRV_ROOT/app/P4_app}"
P4_LEGACY_RUNNER_IMAGE="${P4_LEGACY_RUNNER_IMAGE:-p4-legacy-runner}"
P4_LEGACY_BASE_IMAGE="${P4_LEGACY_BASE_IMAGE:-s.egorkin/heinz_p4:latest}"
P4_WEB_SERVICE="${P4_WEB_SERVICE:-p4-web}"
P4_NGINX_SERVICE="${P4_NGINX_SERVICE:-nginx}"
P4_HEALTH_URL="${P4_HEALTH_URL:-http://127.0.0.1:8000/api/health}"

COMPONENT="${1:-all}"
DRY_RUN=0
if [[ "${2:-}" == "--dry-run" ]] || [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  if [[ "${1:-}" == "--dry-run" ]]; then
    COMPONENT="${2:-all}"
  fi
fi

usage() {
  cat <<'EOF'
Usage: apply_update.sh [COMPONENT] [--dry-run]

Components: all | frontend | backend | legacy | p4-app

Staging layout (SFTP upload to /updates/ on server):
  updates/P4_web_wrap/P4_web_client/
  updates/P4_web_wrap/P4_web/src/
  updates/P4_web_wrap/P4_web/pyproject.toml
  updates/P4_web_wrap/requirements.txt
  updates/P4_web_wrap/P4_legacy_runner/
  updates/P4_app/
EOF
}

require_staging() {
  if [[ ! -d "$P4_UPDATE_STAGING" ]]; then
    fail "Staging directory missing: $P4_UPDATE_STAGING"
  fi
}

backup_tree() {
  local label="$1"
  local target="$2"
  [[ -e "$target" ]] || return 0
  local stamp dest
  stamp="$(date +%Y%m%d-%H%M%S)"
  dest="$P4_BACKUP_ROOT/${label}-${stamp}"
  log "Backing up $target -> $dest"
  mkdir -p "$P4_BACKUP_ROOT"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  [dry-run] cp -a $target $dest"
    return 0
  fi
  cp -a "$target" "$dest"
}

backup_file() {
  local label="$1"
  local target="$2"
  [[ -f "$target" ]] || return 0
  backup_tree "$label" "$target"
}

rsync_apply() {
  local src="$1"
  local dest="$2"
  if [[ ! -d "$src" ]]; then
    log "Skip (not in staging): $src"
    return 0
  fi
  log "Sync $src -> $dest"
  mkdir -p "$(dirname -- "$dest")"
  local -a cmd=(rsync -a --delete "${P4_RSYNC_EXCLUDES[@]}")
  if [[ "$DRY_RUN" -eq 1 ]]; then
    cmd+=(--dry-run --itemize-changes)
  fi
  cmd+=("$src/" "$dest/")
  "${cmd[@]}"
}

copy_staged_file() {
  local src="$1"
  local dest="$2"
  if [[ ! -f "$src" ]]; then
    log "Skip (not in staging): $src"
    return 0
  fi
  log "Copy $src -> $dest"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  [dry-run] cp $src $dest"
    return 0
  fi
  mkdir -p "$(dirname -- "$dest")"
  cp "$src" "$dest"
}

apply_frontend() {
  backup_tree "frontend" "$P4_WEB_WRAP/P4_web_client"
  rsync_apply "$P4_UPDATE_STAGING/P4_web_wrap/P4_web_client" "$P4_WEB_WRAP/P4_web_client"
}

apply_backend_files() {
  backup_tree "backend-src" "$P4_WEB_WRAP/P4_web/src"
  rsync_apply "$P4_UPDATE_STAGING/P4_web_wrap/P4_web/src" "$P4_WEB_WRAP/P4_web/src"
  copy_staged_file \
    "$P4_UPDATE_STAGING/P4_web_wrap/P4_web/pyproject.toml" \
    "$P4_WEB_WRAP/P4_web/pyproject.toml"
  copy_staged_file \
    "$P4_UPDATE_STAGING/P4_web_wrap/requirements.txt" \
    "$P4_WEB_WRAP/requirements.txt"
}

apply_legacy_files() {
  backup_tree "legacy-runner" "$P4_WEB_WRAP/P4_legacy_runner"
  rsync_apply "$P4_UPDATE_STAGING/P4_web_wrap/P4_legacy_runner" "$P4_WEB_WRAP/P4_legacy_runner"
}

apply_p4_app_files() {
  backup_tree "p4-app" "$P4_LEGACY_APP"
  rsync_apply "$P4_UPDATE_STAGING/P4_app" "$P4_LEGACY_APP"
}

activate_backend() {
  p4_install_backend_deps "$P4_WEB_WRAP" "$DRY_RUN"
}

activate_legacy() {
  p4_rebuild_legacy_runner "$P4_WEB_WRAP" "$DRY_RUN"
}

activate_all() {
  activate_backend
  activate_legacy
  p4_reload_nginx "$DRY_RUN"
  p4_restart_web_service "$DRY_RUN"
  p4_verify_deployment "$P4_WEB_WRAP" "$DRY_RUN" || true
}

apply_backend() {
  apply_backend_files
  activate_backend
  p4_restart_web_service "$DRY_RUN"
  p4_verify_deployment "$P4_WEB_WRAP" "$DRY_RUN" || true
}

apply_legacy() {
  apply_legacy_files
  activate_legacy
  p4_restart_web_service "$DRY_RUN"
}

apply_p4_app() {
  apply_p4_app_files
  activate_legacy
  p4_restart_web_service "$DRY_RUN"
}

case "${COMPONENT:-}" in
  -h|--help|help) usage; exit 0 ;;
  all)
    require_staging
    apply_frontend
    apply_backend_files
    apply_legacy_files
    [[ -d "$P4_UPDATE_STAGING/P4_app" ]] && apply_p4_app_files
    activate_all
    log "Update complete"
    ;;
  frontend)
    require_staging
    apply_frontend
    p4_reload_nginx "$DRY_RUN"
    log "Frontend update complete"
    ;;
  backend) require_staging; apply_backend; log "Backend update complete" ;;
  legacy) require_staging; apply_legacy; log "Legacy runner update complete" ;;
  p4-app) require_staging; apply_p4_app; log "P4_app update complete" ;;
  *) usage; fail "Unknown component: $COMPONENT" ;;
esac
