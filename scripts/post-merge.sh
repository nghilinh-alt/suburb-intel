#!/bin/bash
set -e

echo "==> Installing frontend dependencies..."
cd frontend && npm install --legacy-peer-deps
cd ..

echo "==> Installing backend dependencies..."
cd backend && pip install -r requirements.txt -q
cd ..

echo "==> Post-merge setup complete."
