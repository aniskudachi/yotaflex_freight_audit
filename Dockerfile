# Production Container for YotaFlex Freight Invoice Validation & Audit Platform
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Copy dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Pre-build SQLite database from starter CSV data
RUN python src/load_sqlite.py

# Expose default HTTP port
EXPOSE 8080

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", 8080)}/health')" || exit 1

# Start web server
CMD ["sh", "-c", "python src/app.py --host 0.0.0.0 --port ${PORT:-8080}"]
