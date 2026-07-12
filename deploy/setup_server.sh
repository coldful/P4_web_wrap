#!/usr/bin/env bash
# One-time server bootstrap: directory layout, SFTP deploy user, helper scripts.
#
# Run on the server as root:
#   sudo ./deploy/setup_server.sh

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
CONFIG_FILE="${P4_DEPLOY_CONFIG:-/srv/p4/config.env}"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

P4_SRV_ROOT="${P4_SRV_ROOT:-/srv/p4}"
P4_APP_ROOT="${P4_APP_ROOT:-$P4_SRV_ROOT/app}"
P4_INCOMING_ROOT="${P4_INCOMING_ROOT:-$P4_SRV_ROOT/incoming}"
P4_UPDATE_STAGING="${P4_UPDATE_STAGING:-$P4_INCOMING_ROOT/updates}"
P4_BACKUP_ROOT="${P4_BACKUP_ROOT:-$P4_SRV_ROOT/backups}"
P4_DEPLOY_USER="${P4_DEPLOY_USER:-p4deploy}"
P4_DEPLOY_GROUP="${P4_DEPLOY_GROUP:-$P4_DEPLOY_USER}"
P4_WEB_WRAP="${P4_WEB_WRAP:-$P4_APP_ROOT/P4_web_wrap}"
APP_USER="${P4_APP_USER:-ubuntu}"

log() { echo "==> $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    fail "Run as root: sudo $0"
  fi
}

create_deploy_user() {
  if id "$P4_DEPLOY_USER" >/dev/null 2>&1; then
    log "SFTP user already exists: $P4_DEPLOY_USER"
  else
    log "Creating SFTP-only user: $P4_DEPLOY_USER"
    useradd \
      --system \
      --home "$P4_INCOMING_ROOT" \
      --shell /usr/sbin/nologin \
      --comment "P4 code/project upload (SFTP only)" \
      "$P4_DEPLOY_USER"
  fi

  if ! getent group "$P4_DEPLOY_GROUP" >/dev/null 2>&1; then
    groupadd "$P4_DEPLOY_GROUP"
  fi
  usermod -g "$P4_DEPLOY_GROUP" "$P4_DEPLOY_USER" 2>/dev/null || true
}

create_directories() {
  log "Creating server directories under $P4_SRV_ROOT"
  install -d -m 755 -o root -g root "$P4_SRV_ROOT"
  install -d -m 755 -o root -g root "$P4_INCOMING_ROOT"
  install -d -m 775 -o "$P4_DEPLOY_USER" -g "$P4_DEPLOY_GROUP" "$P4_UPDATE_STAGING"
  install -d -m 775 -o "$P4_DEPLOY_USER" -g "$P4_DEPLOY_GROUP" "$P4_INCOMING_ROOT/projects"
  install -d -m 755 -o "$APP_USER" -g "$APP_USER" "$P4_APP_ROOT"
  install -d -m 755 -o "$APP_USER" -g "$APP_USER" "$P4_SRV_ROOT/data"
  install -d -m 755 -o "$APP_USER" -g "$APP_USER" "$P4_SRV_ROOT/logs"
  install -d -m 750 -o "$APP_USER" -g "$APP_USER" "$P4_BACKUP_ROOT"
  install -d -m 755 -o "$APP_USER" -g "$APP_USER" "$P4_SRV_ROOT/bin"
}

install_sshd_sftp_config() {
  local drop_in="/etc/ssh/sshd_config.d/99-p4-deploy-sftp.conf"
  log "Installing OpenSSH SFTP drop-in: $drop_in"

  cat >"$drop_in" <<EOF
# Managed by P4_web_wrap deploy/setup_server.sh
Match User $P4_DEPLOY_USER
    ChrootDirectory $P4_INCOMING_ROOT
    ForceCommand internal-sftp
    AllowTcpForwarding no
    X11Forwarding no
    PasswordAuthentication yes
EOF

  if sshd -t 2>/dev/null; then
    systemctl reload ssh || systemctl reload sshd || true
    log "sshd configuration reloaded"
  else
    fail "sshd -t failed after writing $drop_in"
  fi
}

install_helper_scripts() {
  log "Installing deploy scripts to $P4_WEB_WRAP/deploy"
  install -d -m 755 -o "$APP_USER" -g "$APP_USER" "$P4_WEB_WRAP/deploy"
  for script in apply_update.sh common.sh deploy.sh upload_update.sh push_update.sh setup_server.sh; do
    if [[ -f "$SCRIPT_DIR/$script" ]]; then
      install -m 755 "$SCRIPT_DIR/$script" "$P4_WEB_WRAP/deploy/$script"
      chown "$APP_USER":"$APP_USER" "$P4_WEB_WRAP/deploy/$script"
    fi
  done
  install -m 644 "$SCRIPT_DIR/config.env.example" "$P4_WEB_WRAP/deploy/config.env.example"
  chown "$APP_USER":"$APP_USER" "$P4_WEB_WRAP/deploy/config.env.example"

  log "Installing /srv/p4/bin/apply-update"
  cat >"$P4_SRV_ROOT/bin/apply-update" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$P4_WEB_WRAP/deploy/apply_update.sh" "\$@"
EOF
  chmod 755 "$P4_SRV_ROOT/bin/apply-update"
  install -m 644 "$SCRIPT_DIR/config.env.example" "$P4_SRV_ROOT/config.env.example"
  if [[ ! -f "$CONFIG_FILE" ]]; then
    install -m 640 "$SCRIPT_DIR/config.env.example" "$CONFIG_FILE"
    chown root:"$APP_USER" "$CONFIG_FILE"
    log "Created $CONFIG_FILE — review before production use"
  fi
}

set_deploy_password() {
  log "Set a password for SFTP user $P4_DEPLOY_USER:"
  passwd "$P4_DEPLOY_USER"
}

print_summary() {
  cat <<EOF

P4 server layout is ready.

Directories:
  Application code:  $P4_APP_ROOT
  SFTP upload root:  $P4_INCOMING_ROOT  (chroot for $P4_DEPLOY_USER)
  Code updates:      $P4_UPDATE_STAGING
  P4 projects:       $P4_INCOMING_ROOT/projects

SFTP (FileZilla / WinSCP):
  Protocol:  SFTP
  Host:      <your-server-ip>
  Port:      22
  User:      $P4_DEPLOY_USER
  Remote:    /updates/     → upload P4_web_wrap and P4_app here
             /projects/    → upload P4 publishing projects here

After SFTP upload:
  sudo -u $APP_USER $P4_SRV_ROOT/bin/apply-update all

Or from workstation:
  P4_UPLOAD_HOST=$APP_USER@<server-ip> ./deploy/push_update.sh all

EOF
}

main() {
  require_root
  create_deploy_user
  create_directories
  install_sshd_sftp_config
  install_helper_scripts
  set_deploy_password
  print_summary
}

main "$@"
