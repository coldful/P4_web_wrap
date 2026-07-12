#!/usr/bin/env bash
# Ensure P4_web/.env on the server enables legacy jobs through Docker.
#
# Run on the server as the app user:
#   /srv/p4/app/P4_web_wrap/deploy/configure_production_env.sh
#
# Or from the workstation:
#   ./deploy/deploy.sh scripts
#   ssh ubuntu@SERVER '/srv/p4/app/P4_web_wrap/deploy/configure_production_env.sh'

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
WEB_WRAP="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$WEB_WRAP/P4_web/.env"
CONFIG_FILE="${P4_DEPLOY_CONFIG:-/srv/p4/config.env}"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

P4_LEGACY_APP="${P4_LEGACY_APP:-${P4_REMOTE_P4_APP:-/srv/p4/app/P4_app}}"
P4_LEGACY_RUNNER_IMAGE="${P4_LEGACY_RUNNER_IMAGE:-p4-legacy-runner}"
WORKSPACE_ROOT="${P4_WEB_WORKSPACE_ROOT:-/srv/p4/data/workspaces}"
STORAGE_ROOT="${P4_WEB_STORAGE_ROOT:-/srv/p4/data/storage}"

log() { echo "==> $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

require_file() {
  [[ -e "$1" ]] || fail "Missing required path: $1"
}

set_env_value() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
  fi
}

build_docker_command() {
  local app_path="$1"
  local image="$2"
  cat <<EOF
docker run --rm --network=host -e P4_WEB_JOB_PARAMETERS -e P4_WEB_JOB_KIND -v ${app_path}:/opt/P4_app:ro -v {project_path}:/work/project ${image} run-web-job --operation {operation} --project-path /work/project --language {language}
EOF
}

main() {
  require_file "$P4_LEGACY_APP/interface.py"
  command -v docker >/dev/null 2>&1 || fail "docker command not found"
  docker image inspect "$P4_LEGACY_RUNNER_IMAGE" >/dev/null 2>&1 \
    || fail "Docker image missing: $P4_LEGACY_RUNNER_IMAGE (run ./deploy/deploy.sh legacy)"

  if [[ ! -f "$ENV_FILE" ]]; then
    log "Creating $ENV_FILE from template"
    cp "$WEB_WRAP/P4_web/.env.example" "$ENV_FILE"
  fi

  legacy_command="$(build_docker_command "$P4_LEGACY_APP" "$P4_LEGACY_RUNNER_IMAGE")"

  set_env_value "P4_WEB_ENABLE_LEGACY_RUNNER" "true"
  set_env_value "P4_WEB_LEGACY_P4_APP_PATH" "$P4_LEGACY_APP"
  set_env_value "P4_WEB_WORKSPACE_ROOT" "$WORKSPACE_ROOT"
  set_env_value "P4_WEB_LOCAL_STORAGE_ROOT" "$STORAGE_ROOT"
  set_env_value "P4_WEB_LEGACY_RUNNER_COMMAND" "$legacy_command"

  log "Updated legacy runner settings in $ENV_FILE"
  log "Restart the backend service to apply changes:"
  echo "  sudo systemctl restart ${P4_WEB_SERVICE:-p4-web}"
}

main "$@"
