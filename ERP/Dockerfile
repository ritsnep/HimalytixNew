# =============================================================================
# MULTI-STAGE DOCKERFILE FOR HIMALYTIX ERP
# =============================================================================
# Stage 1: Builder - Install dependencies
# Stage 2: Runtime - Minimal production image
# =============================================================================

FROM python:3.12-slim AS builder

# Install system dependencies for Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# =============================================================================
# STAGE 2: RUNTIME
# =============================================================================
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN groupadd -r erp && useradd -r -g erp -u 1000 erp

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=erp:erp . /app/

# Create required directories
RUN mkdir -p /app/static /app/media /app/logs && \
    chown -R erp:erp /app/static /app/media /app/logs

# Switch to non-root user
USER erp

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Default command (override in docker-compose)
CMD ["gunicorn", "dashboard.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "60"]
