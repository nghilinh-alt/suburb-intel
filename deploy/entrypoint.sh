#!/usr/bin/env sh
set -e
if [ -n "$DB_DOWNLOAD_URL" ]; then
  echo "Fetching database..."
  curl -fsSL "$DB_DOWNLOAD_URL" -o /app/backend/suburb_intel_dev.db
fi
exec uvicorn app.serve:app --host 0.0.0.0 --port "${PORT:-8000}"
