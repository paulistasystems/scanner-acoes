#!/usr/bin/env bash
# docker/bootstrap-passenger.sh — Entrypoint do container Passenger local.
#
# Por que isto existe
# -------------------
# O `__main__` de app.py (que dispara warming.start_warm no boot) SÓ roda sob
# `python app.py` (dev puro). No stack Docker local o processo é o Passenger
# Standalone (CMD do Dockerfile.passenger) — que importa `app` via WSGI sem
# executar o `__main__`. Por isso o aquecimento é orquestrado pelo
# `run_docker.sh up`, que roda o perfil `warm` (prewarm síncrono contra o
# volume compartilhado) ANTES de subir o servidor. Assim o Passenger já encontra
# o scanner.db preenchido e nunca serve dados vazios.
#
# Este wrapper roda ANTES do Passenger e só faz uma coisa: rede de segurança.
# Se o DB estiver vazio (bare `docker compose up` sem warm prévio, ou volume
# novo), dispara warm_cron.py em background (start_new_session — sobrevive ao
# recicle do Passenger). Se o DB já foi aquecido pelo run_docker.sh up, o
# servidor sobe direto lendo o DB pronto (sem re-aquecer nem invalidar).
#
# Seguro para produção? NÃO é invocado lá — produção usa o cron do DirectAdmin
# (warm_cron.py agendado) e o Passenger roda direto do Dockerfile/passenger_wsgi
# sem este wrapper. Este script é exclusivamente do container Docker local.

set -e
cd /app
mkdir -p /app/tmp

# Rede de segurança: só aquece em background se o DB estiver vazio. Se o
# run_docker.sh up já aqueceu, o Passenger sobe lendo o DB pronto.
python3 - <<'PY'
import data_layer
data_layer._ensure_schema()
filled = data_layer._connect().execute("SELECT COUNT(*) FROM fill_state").fetchone()[0]
if filled == 0:
    print("[bootstrap] DB vazio — disparando warm_cron.py em background (rede de segurança)...")
    import subprocess, sys
    # start_new_session=True: o SIGHUP do exec Passenger não mata este processo.
    subprocess.Popen(
        [sys.executable, "/app/warm_cron.py"],
        stdout=open("/app/tmp/warm_cron.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print("[bootstrap] warm_cron.py spawnado (sobrevive ao recicle do Passenger)")
else:
    print(f"[bootstrap] DB já aquecido ({filled} pares em fill_state) — servidor sobe lendo o DB pronto")
PY

# exec Passenger (mesma invocação original do Dockerfile.passenger).
exec passenger start /app \
  --address 0.0.0.0 \
  --port 3000 \
  --app-type wsgi \
  --startup-file passenger_wsgi.py \
  --python python3 \
  --min-instances 1 \
  --max-pool-size 2 \
  --max-requests "${PASSENGER_MAX_REQUESTS:-25}" \
  --log-level 2
