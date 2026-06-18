#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_PATH="${1:-}"

if [ -z "$PROJECT_PATH" ]; then
  echo "Usage: run-generate-pdf.sh PROJECT_PATH [LANGUAGE] [extra runner args...]" >&2
  exit 2
fi

shift
LANGUAGE="${1:-${P4_LEGACY_LANGUAGE:-de}}"
if [ "$#" -gt 0 ]; then
  shift
fi

exec "$SCRIPT_DIR/../bin/p4-legacy-runner" \
  generate-pdf \
  --project-path "$PROJECT_PATH" \
  --language "$LANGUAGE" \
  "$@"
