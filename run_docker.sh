#!/usr/bin/env bash
# Stack local (OrbStack): OpenLiteSpeed + Passenger OSS + PHP.
# Só desenvolvimento — não faz FTP/deploy/upload.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker não encontrado — abra o OrbStack." >&2
  exit 1
fi

cmd="${1:-up}"
shift || true

case "$cmd" in
  up)
    docker compose up --build -d "$@"
    echo ""
    echo "  Local only (sem upload / sem produção)"
    echo "  UI:      http://localhost:8080/scanner/"
    echo "  status:  http://localhost:8080/scanner/api/status"
    echo "  chart:   http://localhost:8080/yahoo_chart.php?symbol=PETR4.SA&interval=1d&range=5d"
    echo "  warm:    ./run_docker.sh warm          # preenche DB do volume Docker"
    echo "  warm 1h: ./run_docker.sh warm 1h"
    echo "  logs:    ./run_docker.sh logs"
    echo "  down:    ./run_docker.sh down"
    ;;
  warm)
    # prewarm só no volume compose
    if [[ $# -eq 0 ]]; then
      docker compose --profile warm run --rm warm
    else
      docker compose --profile warm run --rm warm "$@"
    fi
    ;;
  logs)
    docker compose logs -f --tail=120 "$@"
    ;;
  down)
    docker compose down "$@"
    ;;
  status|ps)
    docker compose ps
    echo "---"
    curl -fsS --max-time 5 "http://localhost:8080/scanner/api/status" \
      | python3 -m json.tool 2>/dev/null \
      || echo "(API local ainda não respondeu — veja: ./run_docker.sh logs)"
    ;;
  export-db)
    exec ./db_sync.sh export
    ;;
  *)
    cat <<USAGE
Uso: $0 {up|warm|logs|down|status|export-db} [args...]

  up         sobe stack local (OpenLiteSpeed + Passenger OSS + PHP)
  warm [iv]  prewarm no volume Docker (ex.: warm 1h) — só local
  status     compose ps + /scanner/api/status local
  logs       logs dos containers
  down       para o stack
  export-db  copia DB do volume → ./scanner.docker.db (opcional, fica no Mac)

Não faz deploy nem FTP. Produção = ./deploy.sh quando o local estiver ok.
USAGE
    exit 2
    ;;
esac
