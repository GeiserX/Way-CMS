FROM python:3.11-slim

WORKDIR /app

# Set default environment variables (do this early for better caching)
ENV CMS_BASE_DIR=/var/www/html \
    PORT=5000 \
    FLASK_APP=app.py \
    PYTHONUNBUFFERED=1

# Create volume mount points (do this early, rarely changes)
RUN mkdir -p /var/www/html /.way-cms-backups && \
    chmod 777 /var/www/html /.way-cms-backups

# Install system dependencies (cache this layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching (dependencies change less frequently)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (this layer will invalidate on code changes, but dependencies stay cached)
COPY . .

# Expose port
EXPOSE 5000

# Health check (use curl or wget if available, or simple Python check)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(1); result=s.connect_ex(('127.0.0.1', 5000)); s.close(); exit(0 if result == 0 else 1)" || exit 1

# Run the application
CMD ["python", "app.py"]
