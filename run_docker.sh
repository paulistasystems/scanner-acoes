#!/usr/bin/env bash
# Stack local (Linux Ubuntu / OrbStack): OpenLiteSpeed + Passenger OSS + PHP.
# Só desenvolvimento — não faz FTP/deploy/upload.
#
# No Linux Ubuntu: se o docker não estiver instalado, oferece instalar via
# script oficial (docker-ce) chamando sudo. No macOS espera o OrbStack.
set -euo pipefail
cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# Garante que o docker esteja disponível e o daemon rodando.
# No Linux instala o docker-ce se faltar; no macOS pede o OrbStack.
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  os="$(uname -s)"
  if [[ "$os" == "Darwin" ]]; then
    echo "docker não encontrado — abra o OrbStack (ou Docker Desktop) no macOS." >&2
    exit 1
  fi

  echo "docker não encontrado neste Linux."
  sudo_cmd=""
  if [[ "$(id -u)" -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
      sudo_cmd="sudo"
    else
      echo "precisa de root para instalar o Docker. Rode como root ou instale manualmente." >&2
      exit 1
    fi
  fi

  echo "Instalando o Docker (docker-ce) via script oficial..."
  tmp_script="$(mktemp /tmp/get-docker.XXXXXX.sh)"
  if ! curl -fsSL https://get.docker.com -o "$tmp_script"; then
    echo "Falhou ao baixar o instalador do Docker." >&2
    rm -f "$tmp_script"
    exit 1
  fi
  $sudo_cmd sh "$tmp_script" || { rm -f "$tmp_script"; exit 1; }
  rm -f "$tmp_script"

  # garante que o grupo docker exista (criado pelo pacote, mas reforça)
  $sudo_cmd getent group docker >/dev/null 2>&1 || $sudo_cmd groupadd docker

  if ! docker info >/dev/null 2>&1; then
    $sudo_cmd systemctl enable --now docker 2>/dev/null || \
      $sudo_cmd service docker start 2>/dev/null || true
  fi

  # adiciona o usuário ao grupo docker (evita sudo nos próximos comandos)
  if [[ -n "$sudo_cmd" ]] && [[ "$(id -un)" != "root" ]]; then
    $sudo_cmd usermod -aG docker "$(id -un)"
    echo "Você foi adicionado ao grupo 'docker'."
    echo "Aplique o grupo na sessão atual com:  sg docker -c '...'  (ou relogue / reinicie)."
    # tenta aplicar o grupo já na sessão corrente para comandos seguintes
    if command -v sg >/dev/null 2>&1; then
      export DOCKER_GROUP_APPLIED=1
    fi
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "O daemon do Docker não está acessível. Rode 'newgrp docker' ou reinicie a sessão." >&2
    exit 1
  fi
fi

# Se acabamos de adicionar o usuário ao grupo docker nesta sessão, re-executa
# o script sob o grupo docker para que os comandos seguintes funcionem sem relogin.
if [[ "${DOCKER_GROUP_APPLIED:-0}" == "1" ]] && [[ "$(id -nG)" != *docker* ]]; then
  exec sg docker -c "$(printf '%q ' "$0" "$@")"
fi

# docker compose (plugin ou binário legado)
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "docker compose não encontrado. Instale o plugin: sudo apt-get install docker-compose-plugin" >&2
  exit 1
fi

# Garante que o daemon esteja acessível (OrbStack parado no macOS, etc.)
if ! docker info >/dev/null 2>&1; then
  os="$(uname -s)"
  if [[ "$os" == "Darwin" ]]; then
    echo "O daemon do Docker não responde — abra o OrbStack (ou Docker Desktop) no macOS e tente de novo." >&2
  else
    echo "O daemon do Docker não está acessível. Rode 'newgrp docker' ou reinicie a sessão." >&2
  fi
  exit 1
fi

cmd="${1:-up}"
shift || true

case "$cmd" in
  up)
    "${COMPOSE[@]}" up --build -d "$@"
    echo ""
    echo "  Local only (sem upload / sem produção)"
    echo "  UI:      http://localhost:8080/scanner/"
    echo "  status:  http://localhost:8080/scanner/api/status"
    echo "  chart:   http://localhost:8080/yahoo_chart.php?symbol=PETR4.SA&interval=1d&range=5d"
    echo "  warm:    ./run_docker.sh warm          # preenche DB do volume Docker"
    echo "  warm 1h: ./run_docker.sh warm 1h"
    echo "  logs:    ./run_docker.sh logs"
    echo "  down:    ./run_docker.sh down"
    echo "  reset-db: apaga o scanner.db local do volume Docker (dev only)"
    ;;
  warm)
    # prewarm só no volume compose
    if [[ $# -eq 0 ]]; then
      "${COMPOSE[@]}" --profile warm run --rm warm
    else
      "${COMPOSE[@]}" --profile warm run --rm warm "$@"
    fi
    ;;
  logs)
    "${COMPOSE[@]}" logs -f --tail=120 "$@"
    ;;
  down)
    "${COMPOSE[@]}" down "$@"
    ;;
  status|ps)
    "${COMPOSE[@]}" ps
    echo "---"
    curl -fsS --max-time 5 "http://localhost:8080/scanner/api/status" \
      | python3 -m json.tool 2>/dev/null \
      || echo "(API local ainda não respondeu — veja: ./run_docker.sh logs)"
    ;;
  export-db)
    exec ./db_sync.sh export
    ;;
  reset-db)
    # Apaga o scanner.db local do volume Docker (desenvolvimento apenas).
    # Para a stack, remove o arquivo do volume e sobe de novo se estava no ar.
    if "${COMPOSE[@]}" ps -q 2>/dev/null | grep -q .; then
      "${COMPOSE[@]}" down >/dev/null 2>&1 || true
      WAS_UP=1
    else
      WAS_UP=0
    fi
    echo "Eliminando scanner.db local do volume Docker..."
    "${COMPOSE[@]}" run --rm --entrypoint sh warm -c \
      'rm -f /data/scanner.db /data/scanner.db-wal /data/scanner.db-shm' \
      2>/dev/null || {
      echo "Não foi possível remover via container — tente './run_docker.sh down' e apague manualmente." >&2
      exit 1
    }
    echo "Banco local eliminado. Re-aqueça com: ./run_docker.sh warm"
    if [[ "$WAS_UP" == "1" ]]; then
      "${COMPOSE[@]}" up --build -d
      echo "Stack local reiniciada (DB vazio até o warm)."
    fi
    ;;
  *)
    cat <<USAGE
Uso: $0 {up|warm|logs|down|status|export-db|reset-db} [args...]

  up         sobe stack local (OpenLiteSpeed + Passenger OSS + PHP)
  warm [iv]  prewarm no volume Docker (ex.: warm 1h) — só local
  status     compose ps + /scanner/api/status local
  logs       logs dos containers
  down       para o stack
  export-db  copia DB do volume → ./scanner.docker.db (opcional, fica no Mac)
  reset-db   apaga o scanner.db local do volume Docker (dev only) e re-aquece

Não faz deploy nem FTP. Produção = ./deploy.sh quando o local estiver ok.
USAGE
    exit 2
    ;;
esac
