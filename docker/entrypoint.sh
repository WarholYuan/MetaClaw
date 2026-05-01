#!/bin/bash
set -euo pipefail

# MetaClaw Docker entrypoint

# Copy config if provided
if [ -f /app/config/config.json ]; then
    cp /app/config/config.json ~/.metaclaw/workspace/config.json
fi

# Start MetaClaw
exec "$@"
