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

# Create volume mount point for website files
RUN mkdir -p /var/www/html && chmod 777 /var/www/html

# Expose port
EXPOSE 5000

# Set environment variables
ENV CMS_BASE_DIR=/var/www/html
ENV PORT=5000
ENV FLASK_APP=app.py

# Run the application
CMD ["python", "app.py"]
