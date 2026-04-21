FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# OS deps za psycopg2 + lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libxml2-dev libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

EXPOSE 8080

# Migracije pred startup-om + bootstrap medijev + gunicorn
CMD ["sh", "-c", "alembic upgrade head && python scripts/bootstrap_admin.py && gunicorn -w 1 --threads 4 -b 0.0.0.0:8080 --timeout 300 web.app:app"]
