#!/usr/bin/env bash
# Stack local (OrbStack / Docker): OpenLiteSpeed + Passenger OSS + PHP.
# Só desenvolvimento — não faz FTP/deploy/upload.
#
# Cross-platform:
#   - macOS  → espera OrbStack (ou Docker Desktop) rodando.
#   - Linux  → se o docker não estiver instalado, oferece instalar via
#              script oficial (docker-ce). Precisa de sudo.
set -euo pipefail
cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# Garante que o docker (e docker compose) esteja disponível.
# No Linux, instala o docker-ce se não existir; no macOS pede o OrbStack.
# ---------------------------------------------------------------------------
ensure_docker() {
  if command -v docker >/dev/null 2>&1; then
    return 0
  fi

  local os
  os="$(uname -s)"

  if [[ "$os" == "Darwin" ]]; then
    echo "docker não encontrado — abra o OrbStack (ou Docker Desktop) no macOS." >&2
    exit 1
  fi

  # Linux: tenta instalar o docker-ce (script oficial da Docker Inc.)
  echo "docker não encontrado neste Linux."
  local sudo_cmd=""
  if [[ "$(id -u)" -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
      sudo_cmd="sudo"
    else
      echo "precisa de root para instalar o Docker. Rode como root ou instale o docker-ce manualmente." >&2
      exit 1
    fi
  fi

  echo "Instalando o Docker (docker-ce) via script oficial..."
  # Baixa o script get.docker.com e executa como root.
  local tmp_script
  tmp_script="$(mktemp /tmp/get-docker.XXXXXX.sh)"
  if ! curl -fsSL https://get.docker.com -o "$tmp_script"; then
    echo "Falhou ao baixar o instalador do Docker." >&2
    rm -f "$tmp_script"
    exit 1
  fi
  $sudo_cmd sh "$tmp_script" || {
    echo "Falhou ao instalar o Docker. Veja erros acima." >&2
    rm -f "$tmp_script"
    exit 1
  }
  rm -f "$tmp_script"

  # Garante que o daemon esteja rodando e o usuário atual possa usá-lo.
  if ! docker info >/dev/null 2>&1; then
    echo "Iniciando o dockerd..."
    $sudo_cmd systemctl enable --now docker 2>/dev/null || \
      $sudo_cmd service docker start 2>/dev/null || true
  fi

  # Adiciona o usuário ao grupo docker (evita sudo nos próximos comandos).
  if [[ -n "$sudo_cmd" ]] && [[ "$(id -un)" != "root" ]]; then
    $sudo_cmd usermod -aG docker "$(id -un)" || true
    echo ""
    echo "ATENÇÃO: você foi adicionado ao grupo 'docker'."
    echo "Faça logout/login (ou rode 'newgrp docker') para aplicar sem sudo."
    echo "Tentando prosseguir agora com sudo onde necessário..."
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "O daemon do Docker não está acessível. Rode 'newgrp docker' ou reinicie a sessão." >&2
    exit 1
  fi
}

ensure_docker

cmd="${1:-up}"
shift || true

case "$cmd" in
  up)
    docker compose up --build -d "$@"
    # O cache de IP do extprocessor do OLS fica obsoleto quando
    # passenger/php são recriados e recebem outro IP. Reload graceful do
    # LSWS força re-resolução do hostname do backend (sem downtime).
    # (Com IPs fixos no compose isto é cinto+suspendentes, mas mantemos
    #  o reload como seguro-de-falha.)
    ols_container="$(docker compose ps -q openlitespeed 2>/dev/null || true)"
    if [[ -n "$ols_container" ]] \
       && docker exec "$ols_container" test -x /usr/local/lsws/bin/lswsctrl 2>/dev/null; then
      echo "Reloading OpenLiteSpeed (re-resolve backends)..."
      docker exec "$ols_container" /usr/local/lsws/bin/lswsctrl restart >/dev/null 2>&1 \
        || docker exec "$ols_container" /usr/local/lsws/bin/lswsctrl restart 2>&1 || true
    fi
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
  reset-db)
    # remove o scanner.db do volume Docker (scanner_acoes_data).
    # não precisa que a stack esteja no ar; cria o volume se não existir.
    echo "Removendo /data/scanner.db do volume scanner_acoes_data..."
    docker volume create scanner_acoes_data >/dev/null
    docker run --rm -v scanner_acoes_data:/data alpine rm -f /data/scanner.db \
      && echo "DB removido (ou já inexistente). Rode './run_docker.sh warm' para repreenchê-lo."
    ;;
  *)
    cat <<USAGE
Uso: $0 {up|warm|logs|down|status|export-db} [args...]

  up         sobe stack local (OpenLiteSpeed + Passenger OSS + PHP)
  warm [iv]  prewarm no volume Docker (ex.: warm 1h) — só local
  status     compose ps + /scanner/api/status local
  logs       logs dos containers
  down       para o stack
  reset-db   remove o scanner.db do volume Docker (limpa dados locais)
  export-db  copia DB do volume → ./scanner.docker.db (opcional, fica no Mac)

Não faz deploy nem FTP. Produção = ./deploy.sh quando o local estiver ok.
USAGE
    exit 2
    ;;
esac
