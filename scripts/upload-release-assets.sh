#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 v2.0.20" >&2
  exit 2
fi

tag="$1"

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: GitHub CLI is required. Install gh and authenticate first." >&2
  exit 1
fi

assets=(
  "dist/README-ONECLICK.txt"
  "dist/install-metaclaw-oneclick.command"
  "dist/metaclaw-main.bundle"
  "dist/metaclaw-oneclick-macos-v2.tar.gz"
  "dist/metaclaw-oneclick-macos.tar.gz"
  "dist/metaclaw-oneclick-macos.zip"
)

missing=0
for asset in "${assets[@]}"; do
  if [[ ! -f "$asset" ]]; then
    echo "Missing release asset: $asset" >&2
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

gh release upload "$tag" "${assets[@]}" --clobber
