FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libmariadb-dev \
    gcc \
    libraw-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/python /app/src/python
COPY src/web /app/src/web

# Set Python path
ENV PYTHONPATH=/app/src/python

# Default port
EXPOSE 5100

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5100", "--workers", "4", "--chdir", "/app/src/web", "app:app"]
