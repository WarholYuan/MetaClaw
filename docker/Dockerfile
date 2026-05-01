FROM python:3.11-slim

LABEL maintainer="mianhuatang913"
LABEL description="MetaClaw - AI Agent Platform"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy installer
COPY scripts/install.sh /app/install.sh
COPY docker/entrypoint.sh /app/entrypoint.sh

# Run installer
RUN bash /app/install.sh --no-shims

# Create config directory
RUN mkdir -p /app/config /app/data

# Expose web console port
EXPOSE 9899

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9899/health || exit 1

# Entry point
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["metaclaw", "start"]
