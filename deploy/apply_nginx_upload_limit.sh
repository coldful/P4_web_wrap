#!/usr/bin/env bash
# Raise nginx upload limit for P4 project folder import.
#
# Run on the server:
#   sudo ./deploy/apply_nginx_upload_limit.sh
#
# Or from workstation via deploy.sh nginx

set -euo pipefail

LIMIT="${P4_NGINX_CLIENT_MAX_BODY_SIZE:-512m}"
SITE="${P4_NGINX_SITE:-/etc/nginx/sites-available/p4}"

log() { echo "==> $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    fail "Run as root: sudo $0"
  fi
}

install_full_site() {
  local script_dir example
  script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
  example="$script_dir/nginx-p4.conf.example"
  [[ -f "$example" ]] || example="/srv/p4/app/P4_web_wrap/deploy/nginx-p4.conf.example"
  [[ -f "$example" ]] || fail "nginx-p4.conf.example not found"

  log "Installing full nginx site config from $example"
  install -m 644 "$example" "$SITE"
  ln -sf "$SITE" "/etc/nginx/sites-enabled/p4"
  rm -f /etc/nginx/sites-enabled/default
}

patch_existing_site() {
  local tmp
  tmp="$(mktemp)"
  cp "$SITE" "$tmp"

  if grep -q 'client_max_body_size' "$tmp"; then
    sed -i "s/client_max_body_size[^;]*;/client_max_body_size $LIMIT;/g" "$tmp"
  else
    sed -i "/server {/a\\    client_max_body_size $LIMIT;" "$tmp"
  fi

  if grep -q 'location /api/' "$tmp" && ! awk '
    /location \/api\// { in_api=1 }
    in_api && /client_max_body_size/ { found=1 }
    END { exit(found ? 0 : 1) }
  ' "$tmp"; then
    sed -i "/location \\/api\\//a\\        client_max_body_size $LIMIT;" "$tmp"
  fi

  install -m 644 "$tmp" "$SITE"
  rm -f "$tmp"
  log "Updated client_max_body_size to $LIMIT in $SITE"
}

main() {
  require_root
  if [[ ! -f "$SITE" ]]; then
    install_full_site
  else
    patch_existing_site
  fi
  nginx -t
  systemctl reload nginx
  log "nginx reloaded — upload limit is now $LIMIT"
}

main "$@"
