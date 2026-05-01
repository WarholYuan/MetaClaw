#!/usr/bin/env bash
set -euo pipefail

# MetaClaw install script with signature verification
# Usage: bash <(curl -fsSL .../install.sh) [--verify]

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ${NC}  $*"; }
log_success() { echo -e "${GREEN}✔${NC}  $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
log_error() { echo -e "${RED}✖${NC}  $*" >&2; }

# Signature verification
verify_script() {
  local script_path="$1"
  local expected_hash="$2"
  
  if ! command -v shasum >/dev/null 2>&1 && ! command -v sha256sum >/dev/null 2>&1; then
    log_warn "Cannot verify script integrity: shasum/sha256sum not found"
    return 0
  fi
  
  local actual_hash
  if command -v sha256sum >/dev/null 2>&1; then
    actual_hash=$(sha256sum "$script_path" | awk '{print $1}')
  else
    actual_hash=$(shasum -a 256 "$script_path" | awk '{print $1}')
  fi
  
  if [[ "$actual_hash" != "$expected_hash" ]]; then
    log_error "Script integrity check failed!"
    log_error "Expected: $expected_hash"
    log_error "Actual:   $actual_hash"
    log_error "The script may have been tampered with. Aborting."
    exit 1
  fi
  
  log_success "Script integrity verified"
}

# Main install function
main() {
  local verify_mode=0
  local expected_hash=""
  
  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --verify) verify_mode=1; shift ;;
      --expected-hash) expected_hash="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  
  # If running from curl, we can't verify ourselves
  # But we can provide instructions
  if [[ "$verify_mode" == "1" && -n "$expected_hash" ]]; then
    verify_script "$0" "$expected_hash"
  fi
  
  # Continue with normal installation
  log_info "Starting MetaClaw installation..."
  
  # ... rest of install logic ...
}

main "$@"
