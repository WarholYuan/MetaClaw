#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="MetaClaw"
PACKAGE_NAME="metaclaw"
CONFIG_DIR="${METACLAW_HOME:-$HOME/.metaclaw}"
WORKSPACE_DIR="${METACLAW_WORKSPACE:-$CONFIG_DIR/workspace}"
BACKUP_DIR="$CONFIG_DIR/backups/upgrade-$(date +%Y%m%d%H%M%S)"

error() {
  echo "Error: $*" >&2
}

info() {
  echo "==> $*"
}

find_python() {
  for candidate in "${PYTHON:-}" python3 python; do
    [ -n "$candidate" ] || continue
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" - "$candidate" <<'PY'
import subprocess
import sys

python = sys.argv[1]
code = "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
raise SystemExit(subprocess.call([python, "-c", code]))
PY
      then
        command -v "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

backup_if_exists() {
  src="$1"
  if [ -e "$src" ]; then
    mkdir -p "$BACKUP_DIR"
    cp -a "$src" "$BACKUP_DIR/"
    info "Backed up $src"
  fi
}

main() {
  info "Checking Python 3.10+"
  python_bin="$(find_python)" || {
    error "Python 3.10 or newer is required. Install Python first, then rerun this script."
    exit 1
  }

  info "Preparing backup"
  backup_if_exists "$CONFIG_DIR/config.json"
  backup_if_exists "$WORKSPACE_DIR/config.json"
  backup_if_exists "$WORKSPACE_DIR/memory"
  if [ -d "$BACKUP_DIR" ]; then
    info "Backup location: $BACKUP_DIR"
  else
    info "No existing config or memory directory found to back up"
  fi

  info "Upgrading ${PACKAGE_NAME}"
  "$python_bin" -m pip install --upgrade "$PACKAGE_NAME"

  if ! command -v metaclaw >/dev/null 2>&1; then
    error "metaclaw command was not found after upgrade. Check that your Python scripts directory is on PATH."
    exit 1
  fi

  info "Running config migrations"
  metaclaw upgrade --migrations-only

  info "Running doctor checks"
  metaclaw doctor

  cat <<EOF

${APP_NAME} upgrade complete.
Backup: ${BACKUP_DIR}
Verify runtime status with:
  metaclaw status
EOF
}

main "$@"
