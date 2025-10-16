# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN groupadd -g 65539 dockerro \
    && useradd -m -u 1034 -g 65539 appuser \
    && chown -R appuser:dockerro /app
USER appuser

# Expose port
EXPOSE 5100

# Run with gunicorn
# Add --reload flag for development (auto-restart on code changes)
CMD ["gunicorn", "--bind", "0.0.0.0:5100", "--workers", "2", "--timeout", "300", "--access-logfile", "-", "--worker-class", "sync", "--max-requests", "100", "--max-requests-jitter", "10", "--reload", "app:app"]
