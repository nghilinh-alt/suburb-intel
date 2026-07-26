#!/bin/bash
set -e

# Post-merge setup script — runs after every task merge.
# Must be idempotent and non-interactive.

echo "==> Installing frontend dependencies..."
cd frontend && npm install --prefer-offline 2>&1 | tail -5
cd ..

echo "==> Installing backend dependencies..."
cd backend && uv pip install -r requirements.txt --quiet 2>&1 | tail -5 || true
cd ..

echo "==> Post-merge setup complete."
