# =============================================================================
# ConstructionAI Telegram Bot - Production Dockerfile
# Multi-stage build for smaller image, non-root user for security
# =============================================================================

# Stage 1: Builder - install dependencies
FROM python:3.10-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies to a specific location
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# =============================================================================
# Stage 2: Runtime - minimal production image
# =============================================================================
FROM python:3.10-slim as runtime

# Labels for image metadata
LABEL maintainer="ConstructionAI Team"
LABEL version="1.0.0"
LABEL description="ConstructionAI Telegram Bot for construction retail assistance"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    APP_HOME=/app \
    APP_USER=botuser \
    APP_UID=1000 \
    APP_GID=1000

# Create non-root user for security
RUN groupadd --gid ${APP_GID} ${APP_USER} \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --shell /bin/bash --create-home ${APP_USER}

# Set working directory
WORKDIR ${APP_HOME}

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Create necessary directories with proper permissions
RUN mkdir -p ${APP_HOME}/data \
             ${APP_HOME}/logs \
             ${APP_HOME}/experiments \
             ${APP_HOME}/prompt_engineering/experiments \
    && chown -R ${APP_USER}:${APP_USER} ${APP_HOME}

# Copy application code
COPY --chown=${APP_USER}:${APP_USER} . .

# Create healthcheck script
RUN echo '#!/bin/bash\n\
# Healthcheck: verify bot process is running and responsive\n\
# Check if main process is running\n\
if ! pgrep -f "python.*telegram_bot.py" > /dev/null; then\n\
    echo "Bot process not running"\n\
    exit 1\n\
fi\n\
# Check if Python can import main modules\n\
python -c "from src.config import Config; Config.validate()" 2>/dev/null\n\
if [ $? -ne 0 ]; then\n\
    echo "Config validation failed"\n\
    exit 1\n\
fi\n\
echo "Healthy"\n\
exit 0' > /usr/local/bin/healthcheck.sh \
    && chmod +x /usr/local/bin/healthcheck.sh

# Switch to non-root user
USER ${APP_USER}

# Healthcheck instruction
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD /usr/local/bin/healthcheck.sh

# Expose port for potential webhook mode (optional)
EXPOSE 8443

# Default command - run the bot
CMD ["python", "telegram_bot.py"]
