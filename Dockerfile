FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    curl \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app /app/app
COPY ./config /app/config
COPY alembic.ini .
COPY ./alembic /app/alembic
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh
COPY ./fonts /usr/share/fonts/truetype/montserrat
RUN fc-cache -f

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Command specified in docker-compose.yml
