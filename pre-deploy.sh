#!/bin/sh
set -e

echo "=== [Pre-Deploy] Starting Django Pre-Deployment Tasks ==="

echo "1. Applying database migrations..."
python manage.py migrate --noinput

echo "2. Collecting static files..."
python manage.py collectstatic --noinput

echo "3. Seeding idempotent production roles & permissions..."
python seed.py

echo "=== [Pre-Deploy] Pre-deployment tasks completed successfully! ==="
