#!/usr/bin/env bash
# docker/bootstrap-passenger.sh — Refresh do scanner.db a cada boot do container local.
#
# Por que isto existe
# -------------------
# O `__main__` de app.py (que dispara warming.start_warm no boot) SÓ roda sob
# `python app.py` (dev puro). No stack Docker local o processo é o Passenger
# Standalone (CMD do Dockerfile.passenger) — que importa `app` via WSGI sem
# executar o `__main__`. Consequência: a UI local ficava presa ao snapshot do
# último warm manual/cron, sem aquecer de novo quando a stack sobe — ex.: o DB
# ficava com barras de ontem enquanto o remoto já tinha as de hoje, gerando
# divergência nos scans.
#
# Este wrapper roda ANTES do Passenger:
#   1. invalida fill_state / chart_cache / scan_cache  → próximo get_bars
#      força re-fetch de TODOS os (symbol, interval) contra o Yahoo (egress PHP),
#      descartando snapshots obsoletos de um warm anterior.
#   2. zera warm_state                            → o frontend /api/status mostra
#      um warm rodando (em vez de "finished" de uma sessão morta).
#   3. dispara warm_cron.py em subprocesso destacado (start_new_session) —
#      sobrevive ao recicle do Passenger, popula o DB em background. Mesmo
#      mecanismo do warming.start_warm / cron de produção (lock fcntl + heartbeat).
#   4. exec passenger start ...                    → substitui o shell pelo
#      processo Passenger oficial (mesmo CMD anterior).
#
# Seguro para produção? NÃO é invocado lá — produção usa o cron do DirectAdmin
# (warm_cron.py agendado) e o Passenger roda direto do Dockerfile/passenger_wsgi
# sem este wrapper. Este script é exclusivamente do container Docker local.

set -e
cd /app

echo "[bootstrap] refresh do scanner.db no boot do container local..."

# 1+2: invalida fill_state/chart_cache/scan_cache e zera warm_state.
python3 - <<'PY'
import data_layer

# 1: invalida fill_state + chart_cache + scan_cache
data_layer.invalidate()
print("[bootstrap] fill_state + chart_cache + scan_cache invalidados")

# 2: zera warm_state — garante running=0 para o frontend não travar
#    numa sessão antiga de outro container/processo.
try:
    with data_layer._lock:
        conn = data_layer._connect()
        conn.execute(
            "UPDATE warm_state SET running=0, done=0, "
            "total=0, heartbeat_at=NULL, "
            "started_at=NULL, finished_at=NULL, last_symbol='' "
            "WHERE id=1"
        )
        conn.commit()
    print("[bootstrap] warm_state zerado")
except Exception as e:
    print(f"[bootstrap] aviso: reset warm_state falhou ({e!r})")
PY

# 3: dispara warm_cron.py em background (sobrevive ao recicle do Passenger).
#     start_new_session=True evita que o sinal SIGHUP do exec Passenger mate
#     o processo de warm.
mkdir -p /app/tmp
python3 -c "
import subprocess, sys
subprocess.Popen(
    [sys.executable, '/app/warm_cron.py'],
    stdout=open('/app/tmp/warm_cron.log', 'a'),
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
print('[bootstrap] warm_cron.py spawnado em background')
"

# 4: exec Passenger (mesma invocação original do Dockerfile.passenger).
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
