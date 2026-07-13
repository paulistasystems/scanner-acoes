#!/usr/bin/env bash
# tools/verify_warm_local.sh — valida o warm LOCALMENTE via egress PHP (run_web.sh),
# num DB descartável, antes de deploy. Observa done/total subindo rápido (sem stall)
# e falhas registradas com "yfinance skipped".
#
# Uso:
#   ./tools/verify_warm_local.sh                 # DB /tmp, porta 5006, 1d+1h
#   PORT=5007 INTERVALS=1d,1h,30m ./tools/verify_warm_local.sh
set -u
cd "$(dirname "$0")/.."

export SCANNER_DB="${SCANNER_DB:-/tmp/verify_warm.db}"
export PORT="${PORT:-5006}"
INTERVALS="${INTERVALS:-1d,1h}"
rm -f "$SCANNER_DB"

echo ">> subindo app local (PHP egress :8008 + Flask :$PORT), DB=$SCANNER_DB"
./run_web.sh >/tmp/verify_app.log 2>&1 &
APP=$!
cleanup() { kill "$APP" 2>/dev/null; pkill -f "php -S 127.0.0.1:8008" 2>/dev/null; }
trap cleanup EXIT

for i in $(seq 1 25); do
  curl -fsS --max-time 2 "http://127.0.0.1:$PORT/api/status" >/dev/null 2>&1 && break
  sleep 1
done
if ! curl -fsS --max-time 2 "http://127.0.0.1:$PORT/api/status" >/dev/null 2>&1; then
  echo "!! app não subiu — veja /tmp/verify_app.log"; exit 1
fi

echo ">> POST /api/warm (intervals=$INTERVALS)"
curl -sS -X POST "http://127.0.0.1:$PORT/api/warm" -H 'Content-Type: application/json' \
     -d "{\"intervals\":\"$INTERVALS\"}" >/dev/null

echo ">> observando taxa (esperado: ~2 itens/s, sem congelar)"
prev=0; stalled=no
for t in 20 40 60 80; do
  sleep 20
  read -r done total bars < <(curl -sS "http://127.0.0.1:$PORT/api/status" | \
    python3 -c "import json,sys;d=json.load(sys.stdin);print(d['warm_progress']['done'],d['warm_progress']['total'],d['summary']['bars'])")
  delta=$((done - prev))
  [ "$t" != 20 ] && [ "$delta" -lt 3 ] && stalled=yes
  printf "+%ss done=%s/%s (Δ%s) bars=%s\n" "$t" "$done" "$total" "$delta" "$bars"
  prev=$done
done

echo ">> failures (devem trazer 'yfinance skipped'):"
curl -sS "http://127.0.0.1:$PORT/api/failures" | \
  python3 -c "import json,sys;d=json.load(sys.stdin);print('  ', d[:3] if d else 'nenhuma')"

if [ "$stalled" = yes ]; then
  echo ">> RESULTADO: STALL detectado (done parou) — investigar."
  exit 2
fi
echo ">> RESULTADO: warm progredindo sem stall. ✅"
