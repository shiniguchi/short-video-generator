#!/bin/bash
set -e

# Ensure output directory exists and is writable
mkdir -p /app/output

echo "Running database migrations..."
alembic upgrade head

echo "Migrations complete. Starting: $@"
exec "$@"
