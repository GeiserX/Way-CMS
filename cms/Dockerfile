FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create volume mount points for website files and backups
RUN mkdir -p /var/www/html && \
    mkdir -p /.way-cms-backups && \
    chmod 777 /var/www/html && \
    chmod 777 /.way-cms-backups

# Expose port
EXPOSE 5000

# Set default environment variables
ENV CMS_BASE_DIR=/var/www/html
ENV PORT=5000
ENV FLASK_APP=app.py

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/login', timeout=5)" || exit 1

# Run the application
CMD ["python", "app.py"]
