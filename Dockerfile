FROM python:3.12-slim

ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="studio-app" \
      org.opencontainers.image.version="${APP_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/metrics \
    DB_DIR=/srv/app/db

WORKDIR /srv/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --no-create-home studio

COPY app ./app
COPY db/migrations ./db/migrations
COPY db/seed.sql ./db/seed.sql
COPY wsgi.py gunicorn.conf.py ./

USER studio
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
