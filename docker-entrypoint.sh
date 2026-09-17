#!/bin/sh
set -e

# Dynamically bind to PORT assigned by Render or container host (default: 8000)
PORT="${PORT:-8000}"

# Optional automatic startup migration if RUN_MIGRATIONS_ON_STARTUP is enabled
if [ "${RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
    echo "[Entrypoint] Running database migrations..."
    python manage.py migrate --noinput
fi

# If no arguments provided, start Gunicorn web server
if [ "$#" -eq 0 ]; then
    echo "[Entrypoint] Starting Gunicorn on 0.0.0.0:${PORT}..."
    exec python -m gunicorn config.wsgi:application \
        --bind "0.0.0.0:${PORT}" \
        --workers 3 \
        --threads 2 \
        --timeout 120
fi

# If argument is 'gunicorn' or 'web', start Gunicorn web server with dynamic PORT binding
if [ "$1" = "gunicorn" ] || [ "$1" = "web" ]; then
    shift
    echo "[Entrypoint] Starting Gunicorn on 0.0.0.0:${PORT}..."
    exec python -m gunicorn config.wsgi:application \
        --bind "0.0.0.0:${PORT}" \
        --workers 3 \
        --threads 2 \
        --timeout 120 \
        "$@"
fi

# Otherwise, execute arbitrary commands directly (e.g. celery, bash, manage.py commands)
exec "$@"
