# Python 3.9 — mesmo major do Passenger em paulista.dev
FROM python:3.9-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-py39.txt /app/requirements-py39.txt
RUN pip install --no-cache-dir -r requirements-py39.txt gunicorn==21.2.0

# Código sobe via bind-mount no compose (dev). Cópia mínima para build standalone.
COPY app.py passenger_wsgi.py data_layer.py warming.py warm_cron.py \
     warm_cron_status.py indicators.py scanners_core.py \
     symbol_store.py symbols_fallback.py /app/
COPY static /app/static

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SCANNER_DB=/data/scanner.db \
    SCANNER_CHART_URL=http://php:8008/yahoo_chart.php

# Gunicorn WSGI (análogo ao Passenger): 1 worker, recicla a cada N requests
# para simular o "processo morre após request" do hosting.
# max-requests=0 desliga recycle (dev estável); compose usa valor baixo.
EXPOSE 8000
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--threads", "1", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "passenger_wsgi:application"]
