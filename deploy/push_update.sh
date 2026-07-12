#!/usr/bin/env bash
# Upload to staging and apply on server in one step.
#
# Usage:
#   P4_UPLOAD_HOST=ubuntu@SERVER_IP ./deploy/push_update.sh [COMPONENT] [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
COMPONENT="${1:-all}"
DRY_RUN_FLAG=""

if [[ "${2:-}" == "--dry-run" ]]; then
  DRY_RUN_FLAG="--dry-run"
fi
if [[ "$COMPONENT" == "--dry-run" ]]; then
  DRY_RUN_FLAG="--dry-run"
  COMPONENT="${2:-all}"
fi

if [[ -f "$SCRIPT_DIR/config.env" ]]; then
  # shellcheck disable=SC1090
  source "$SCRIPT_DIR/config.env"
fi

P4_UPLOAD_HOST="${P4_UPLOAD_HOST:-${P4_DEPLOY_HOST:-}}"
P4_UPLOAD_SSH_KEY="${P4_UPLOAD_SSH_KEY:-${P4_DEPLOY_SSH_KEY:-}}"

if [[ -z "$P4_UPLOAD_HOST" ]]; then
  echo "Set P4_UPLOAD_HOST or P4_DEPLOY_HOST in deploy/config.env" >&2
  exit 1
fi

export P4_UPLOAD_HOST P4_UPLOAD_SSH_KEY
"$SCRIPT_DIR/upload_update.sh" "$COMPONENT"

SSH_CMD=(ssh -o StrictHostKeyChecking=accept-new)
if [[ -n "$P4_UPLOAD_SSH_KEY" ]]; then
  SSH_CMD+=(-i "$P4_UPLOAD_SSH_KEY")
fi

echo "==> Applying update on server"
"${SSH_CMD[@]}" "$P4_UPLOAD_HOST" bash -s -- "$COMPONENT" "$DRY_RUN_FLAG" <<'REMOTE'
set -euo pipefail
component="$1"
dry_run="${2:-}"
if [[ -x /srv/p4/bin/apply-update ]]; then
  exec /srv/p4/bin/apply-update "$component" $dry_run
elif [[ -x /srv/p4/app/P4_web_wrap/deploy/apply_update.sh ]]; then
  exec /srv/p4/app/P4_web_wrap/deploy/apply_update.sh "$component" $dry_run
else
  echo "ERROR: apply-update not found. Run: sudo ./deploy/setup_server.sh" >&2
  exit 1
fi
REMOTE
