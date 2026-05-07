#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="MetaClaw"
PACKAGE_NAME="metaclaw"
CONFIG_DIR="${METACLAW_HOME:-$HOME/.metaclaw}"

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

main() {
  info "Checking Python 3.10+"
  python_bin="$(find_python)" || {
    error "Python 3.10 or newer is required. Install Python first, then rerun this script."
    exit 1
  }
  info "Using Python: $("$python_bin" -c 'import sys; print(sys.executable + " " + sys.version.split()[0])')"

  info "Creating ${CONFIG_DIR}"
  mkdir -p "$CONFIG_DIR"

  info "Installing ${PACKAGE_NAME} from PyPI"
  "$python_bin" -m pip install --upgrade pip
  "$python_bin" -m pip install "$PACKAGE_NAME"

  info "Initializing local configuration"
  if ! command -v metaclaw >/dev/null 2>&1; then
    error "metaclaw command was not found after install. Check that your Python scripts directory is on PATH."
    exit 1
  fi
  metaclaw init

  cat <<EOF

${APP_NAME} installation complete.

Next steps:
1. Edit ${CONFIG_DIR}/.env and add at least one provider key:
   DEEPSEEK_API_KEY=...
   DOUBAO_API_KEY=...
   MOONSHOT_API_KEY=...
   OPENAI_API_KEY=...
2. Verify the installation:
   metaclaw doctor
3. Start the service:
   metaclaw start
EOF
}

main "$@"
