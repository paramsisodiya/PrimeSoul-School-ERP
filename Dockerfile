FROM python:3.11-slim-bookworm

# Set work directory
WORKDIR /usr/src/app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install build dependencies for C extensions (e.g. psutil on aarch64)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpython3.11-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Install python dependencies
COPY ./requirements.txt .
RUN pip install -r requirements.txt
RUN pip install gunicorn==21.2.0

# Copy application source code
COPY . .

# Ensure entrypoint and pre-deploy scripts have execution permissions
RUN chmod +x docker-entrypoint.sh pre-deploy.sh

# Collect static files during Docker build so image is self-contained with hashed assets and staticfiles.json
ENV DJANGO_SETTINGS_MODULE=config.settings.production
RUN python manage.py collectstatic --noinput

EXPOSE 8000

ENTRYPOINT ["/usr/src/app/docker-entrypoint.sh"]
CMD ["gunicorn"]
