#!/bin/bash
# deploy.sh — sobe aplicação e dependências via tarball + PHP extraction.
#
# As etapas lentas (mirror FTP de milhares de ficheiros) foram substituídas por:
#   tar → ftp_put (single file) → curl php/io.php (server-side extract).
# Isto é muito mais rápido e confiável que o mirror FTP antigo.
#
# NUNCA sincroniza scanner.db (nem upload nem download).
# O banco de produção fica no servidor; warm/DB é outro fluxo (cron / POST /api/warm).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Git clean check — aborta se houver algo não commitado ou untracked
if ! git diff --quiet HEAD 2>/dev/null; then
  echo "ERRO: há alterações não commitadas no repositório. Commit ou stash antes de deployar." >&2
  exit 1
fi
if [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "ERRO: há ficheiros untracked no repositório. Commit, stash ou .gitignore antes de deployar." >&2
  exit 1
fi

# Load credentials
set -a; . ./.env; set +a
echo "Deploy -> $FTP_USER@$FTP_HOST"
echo "   Política: só aplicação. scanner.db NÃO é enviado nem baixado."

# ---- Helpers (tarball+PHP para uploads rápidos) ----------------------------
check_deps() {
  for cmd in lftp curl openssl; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      echo "ERRO: $cmd não encontrado. Instale-o primeiro." >&2
      exit 1
    fi
  done
}

ftp_put() {
  local local_file="$1" remote_file="$2"
  echo "   ftp_put: $(basename "$local_file") -> $remote_file"
  lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 120
set net:max-retries 3
put "$local_file" -o '$remote_file'
bye
EOF
}

io_php() {
  local op="$1"; shift
  local args=(-s --max-time 300 -G "https://paulista.dev/scanner/io.php")
  args+=(--data-urlencode "token=${IO_PHP_TOKEN}")
  args+=(--data-urlencode "op=${op}")
  for p in "$@"; do
    args+=(--data-urlencode "$p")
  done
  local output
  output=$(curl "${args[@]}")
  local rc=$?
  echo "$output"
  if echo "$output" | grep -q '^ERRO'; then
    echo "   !! io.php falhou" >&2
    return 1
  fi
  return $rc
}

io_extract_tgz() {
  local tgz="$1" dest="$2"
  echo "   io.php extract_tgz $tgz -> $dest"
  io_php "extract_tgz" "tgz=$tgz" "dest=$dest"
}

io_extract_app() {
  echo "   io.php extract_app"
  io_php "extract_app"
}

check_deps

# 1. Stage — lista explícita de ficheiros da app (sem DB, sem venv, sem dumps)
echo ""
echo "==> Montando stage (app only)..."
STAGE=$(mktemp -d)
mkdir -p "$STAGE/static" "$STAGE/tmp"

# Preserve original modification times (mtime) so LFTP doesn't think files changed.
cp -p app.py passenger_wsgi.py scanners_core.py warming.py indicators.py \
   data_layer.py symbol_store.py symbols_fallback.py warm_cron.py warm_cron_status.py "$STAGE/"
cp -p static/* "$STAGE/static/"
cp -p requirements-py39.txt .python-version .env "$STAGE/"
date > "$STAGE/tmp/restart.txt"

# Fixa SCANNER_CHART_URL para a URL de produção — NUNCA deployar com
# http://127.0.0.1:8008 (Docker) ou outro valor local. Isto já causou
# "852 falhas · 0% preenchido" em produção quando o .env local estava
# contaminado com a URL do Docker (docker-compose.yml / Dockerfile.*).
# Ver .env.example para contexto.
if grep -q '^SCANNER_CHART_URL=' "$STAGE/.env"; then
  sed -i 's|^SCANNER_CHART_URL=.*|SCANNER_CHART_URL=https://paulista.dev/scanner/yahoo_chart.php|' "$STAGE/.env"
else
  echo 'SCANNER_CHART_URL=https://paulista.dev/scanner/yahoo_chart.php' >> "$STAGE/.env"
fi

# Guarda: se por engano houver .db no stage, aborta
if find "$STAGE" -type f \( -name '*.db' -o -name 'scanner.db*' \) | grep -q .; then
  echo "ERRO: stage contém ficheiro de base de dados — abortando deploy." >&2
  find "$STAGE" -type f \( -name '*.db' -o -name 'scanner.db*' \) >&2
  exit 1
fi

echo "   Stage: $STAGE"
echo "   Files: $(find "$STAGE" -type f | wc -l | tr -d ' ')"
echo "   (sem scanner.db / sem sync de banco)"

FORCE_DEPLOY=false
SHOW_HELP=false
RESET_DB=false
UNKNOWN_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --force) FORCE_DEPLOY=true ;;
    --reset-db) RESET_DB=true ;;
    -h|--help) SHOW_HELP=true ;;
    *) UNKNOWN_ARGS+=("$arg") ;;
  esac
done

if [ "${#UNKNOWN_ARGS[@]}" -gt 0 ]; then
  echo "   ERRO: parâmetro(s) desconhecido(s): ${UNKNOWN_ARGS[*]}" >&2
  cat <<'HELP'
Uso: ./deploy.sh [opções]

Faz upload da aplicação (app only) para o servidor via FTP.
NUNCA sincroniza scanner.db (nem upload nem download) — salvo com --reset-db.

Opções:
  --force      Força o upload de site-packages e dos ficheiros da app,
               independentemente do hash de mudança.
  --reset-db   Apaga o scanner.db de PRODUÇÃO no servidor e dispara re-aquecimento
               via warm_cron (ação destrutiva — confirmação solicitada).
  -h, --help   Mostra esta ajuda e sai.

Exemplos:
  ./deploy.sh
  ./deploy.sh --force
  ./deploy.sh --reset-db
HELP
  exit 1
fi

if [ "$SHOW_HELP" = true ]; then
  cat <<'HELP'
Uso: ./deploy.sh [opções]

Faz upload da aplicação (app only) para o servidor via FTP.
NUNCA sincroniza scanner.db (nem upload nem download) — salvo com --reset-db.

Opções:
  --force      Força o upload de site-packages e dos ficheiros da app,
               independentemente do hash de mudança.
  --reset-db   Apaga o scanner.db de PRODUÇÃO no servidor e dispara re-aquecimento
               via warm_cron (ação destrutiva — confirmação solicitada).
  -h, --help   Mostra esta ajuda e sai.

Exemplos:
  ./deploy.sh
  ./deploy.sh --force
  ./deploy.sh --reset-db
HELP
  exit 0
fi

if [ "$RESET_DB" = true ]; then
  echo ""
  echo "==> ATENÇÃO: reset remoto do scanner.db de PRODUÇÃO"
  echo "   Isto apaga o banco de dados em produção (/scanner/scanner.db) e força"
  echo "   o re-aquecimento via warm_cron. Os scanners ficarão vazios até o warm."
  read -r -p "   Confirma a eliminação do scanner.db remoto? [digite RESET para confirmar]: " CONFIRM
  if [ "$CONFIRM" != "RESET" ]; then
    echo "   Cancelado. Nenhuma alteração no banco remoto."
    exit 1
  fi
  echo "   Eliminando scanner.db remoto..."
  lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 60
set net:max-retries 3
rm -f /scanner/scanner.db /scanner/scanner.db-wal /scanner/scanner.db-shm
bye
EOF
  echo "   Banco remoto eliminado. Disparando re-aquecimento via POST /api/warm..."
  # O worker de warm em background do servidor (warming.start_warm) reassume o
  # preenchimento; o frontend faz poll de /api/status. Não depende de cron.
  sleep 2
  if curl -fsS --connect-timeout 10 -X POST "https://paulista.dev/scanner/api/warm" \
       2>/dev/null | python3 -m json.tool 2>/dev/null; then
    echo "   Warm remoto disparado. Acompanhe em: https://paulista.dev/scanner/api/status"
  else
    echo "   ⚠️  Aviso: não foi possível disparar /api/warm (servidor offline ou bloqueio)."
    echo "      Dispare manualmente no servidor:"
    echo "      cd /home/paulista/scanner && /home/paulista/virtualenv/scanner/3.9/bin/python warm_cron.py"
    echo "      (ou aguarde o próximo ciclo de cron 10-17h, seg-sex)."
  fi
fi

if [ "$FORCE_DEPLOY" = true ]; then
  echo "   Modo force ativado — forçando upload de site-packages e app."
fi

# ── 1. PHP + static assets → tarball via FTP + io.php extract_tgz ──────────
# Sobe PHP proxies, io.php, symbols.json e assets estáticos (js/css/html)
# para o docroot do LiteSpeed (public_html/scanner/). Os assets estáticos
# precisam estar no docroot porque o LiteSpeed retorna 503 para .js servidos
# via Flask.
#
# Estratégia: sobe o io.php primeiro (necessário para os extract steps),
# depois empacota o resto num tarball e extrai via io.php — 2 uploads + 1
# curl em vez de 11 lftp put individuais. Hash guard evita re-upload.
PHP_DEPLOY="domains/paulista.dev/public_html/scanner"
PHP_MARKER="/tmp/scanner_php_marker"
CURRENT_PHP_HASH=$(find php/yahoo_chart.php php/yahoo_bulk.php php/yahoo_probe.php \
  php/yahoo_snapshot.php php/warm_cron_status.php php/io.php php/symbols.json \
  static/app.js static/intraday.js static/style.css static/index.html static/intraday.html \
  -type f -exec sha1sum {} \; | sort | sha1sum | cut -d' ' -f1)
PREVIOUS_PHP_HASH=""
[ -f "$PHP_MARKER" ] && PREVIOUS_PHP_HASH=$(cat "$PHP_MARKER")

if [ "$FORCE_DEPLOY" = true ] || [ "$CURRENT_PHP_HASH" != "$PREVIOUS_PHP_HASH" ]; then
  echo ""
  echo "==> 1. Enviando PHP + static assets para $PHP_DEPLOY ..."
  # 1a. Sobe io.php sozinho (precisa estar no ar antes do extract)
  echo "   1a. io.php individual..."
  lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 60
set net:max-retries 3
# lftp's mkdir (unlike shell `mkdir -p`) errors on an existing dir, so tolerate
# the "550 File exists" failure — the dir is already there from prior deploys.
mkdir -p $PHP_DEPLOY || true
put php/io.php -o $PHP_DEPLOY/io.php
bye
EOF
  # 1b. Stage flat (sem io.php) → tarball → ftp_put → io.php extract_tgz
  echo "   1b. Tarball dos demais assets -> io.php extract_tgz..."
  PHP_STAGE=$(mktemp -d)
  for f in php/yahoo_chart.php php/yahoo_bulk.php php/yahoo_probe.php \
    php/yahoo_snapshot.php php/warm_cron_status.php php/symbols.json \
    static/app.js static/intraday.js static/style.css static/index.html static/intraday.html; do
    cp -p "$f" "$PHP_STAGE/$(basename "$f")"
  done
  PHP_TGZ="/tmp/scanner_php_assets.tgz"
  cd "$PHP_STAGE" && find . -mindepth 1 -maxdepth 1 | tar -czf "$PHP_TGZ" -T - && cd - >/dev/null
  rm -rf "$PHP_STAGE"
  if [ -s "$PHP_TGZ" ]; then
    ftp_put "$PHP_TGZ" "/scanner/scanner_php_assets.tgz"
    io_php "extract_tgz" "tgz=scanner/scanner_php_assets.tgz" "dest=${PHP_DEPLOY}"
    rm -f "$PHP_TGZ"
    echo "   Tarball extraído em $PHP_DEPLOY"
  else
    rm -f "$PHP_TGZ"
    echo "   Tarball vazio (só io.php mudou), pulando extract."
  fi
  echo "$CURRENT_PHP_HASH" > "$PHP_MARKER"
  echo "   PHP + static assets sincronizados (docroot)."
else
  echo ""
  echo "==> 1. PHP + static assets não mudaram, pulando."
fi

# ── 2. Build and Upload site-packages ────────────────────────────────────────
# Só executa se requirements mudaram ou build não existe.
echo ""
echo "==> Verificando dependências (site-packages)..."
BUILD_DIR="/tmp/scanner_linux_sitepackages"
REQ_MARKER="/tmp/scanner_req_marker"
CURRENT_REQ_HASH=$(sha1sum requirements-py39.txt | cut -d' ' -f1)
PREVIOUS_REQ_HASH=""

if [ -f "$REQ_MARKER" ]; then
  PREVIOUS_REQ_HASH=$(cat "$REQ_MARKER")
fi

if [ "$FORCE_DEPLOY" = true ] || [ "$CURRENT_REQ_HASH" != "$PREVIOUS_REQ_HASH" ] || [ ! -d "$BUILD_DIR" ]; then
  echo "   Requirements mudaram ou não foram compilados localmente. Instalando pacotes no Docker..."
  # Remove leftover root-owned files from previous docker builds.
  docker run --rm -v "$BUILD_DIR":/clean alpine sh -c 'rm -rf /clean/* /clean/.[!.]*' >/dev/null 2>&1 || true
  rm -rf "$BUILD_DIR" tmp_build_output 2>/dev/null || true
  mkdir -p "$BUILD_DIR"

  docker run --rm \
    -v "$PWD/requirements-py39.txt":/req.txt:ro \
    -v "$BUILD_DIR":/wheels \
    python:3.9-slim-bookworm \
    sh -c 'python -m pip install --upgrade pip -q && pip install -r /req.txt --target /wheels --no-cache-dir && echo DONE'

  echo "   Compactando site-packages em tarball (single file)..."
  SITE_TGZ="/tmp/scanner_sitepackages.tgz"
  cd "$BUILD_DIR" && find . -mindepth 1 -maxdepth 1 | tar -czf "$SITE_TGZ" -T - && cd - >/dev/null
  echo "   Enviando tarball ($(du -h "$SITE_TGZ" | cut -f1))..."
  ftp_put "$SITE_TGZ" "/scanner/scanner_sitepackages.tgz"
  echo "   Extraindo no servidor via io.php..."
  io_php "extract_sitepackages" || echo "   !! io.php extract_sitepackages falhou"
  rm -f "$SITE_TGZ"
  echo "$CURRENT_REQ_HASH" > "$REQ_MARKER"
  echo "   Site-packages atualizados localmente e no servidor."
else
  echo "   Requirements não mudaram. Pulando upload de site-packages."
fi

# ── 3. Upload app files only (never database) ────────────────────────────────
echo ""
echo "==> Subindo app para /scanner (código; DB excluído)..."
APP_MARKER="/tmp/scanner_app_marker"
CURRENT_APP_HASH=$(find app.py warming.py warm_cron.py warm_cron_status.py data_layer.py \
  passenger_wsgi.py scanners_core.py indicators.py symbol_store.py symbols_fallback.py \
  static/ -type f -exec sha1sum {} \; | sort | sha1sum | cut -d' ' -f1)
PREVIOUS_APP_HASH=""

if [ -f "$APP_MARKER" ]; then
  PREVIOUS_APP_HASH=$(cat "$APP_MARKER")
fi

if [ "$FORCE_DEPLOY" = true ] || [ "$CURRENT_APP_HASH" != "$PREVIOUS_APP_HASH" ]; then
  echo "   Compactando app em tarball..."
  APP_TGZ="/tmp/scanner_app.tgz"
  cd "$STAGE" && find . -mindepth 1 -maxdepth 1 | tar -czf "$APP_TGZ" -T - && cd - >/dev/null
  echo "   Enviando tarball ($(du -h "$APP_TGZ" | cut -f1))..."
  ftp_put "$APP_TGZ" "/scanner/scanner_app.tgz"
  echo "   Extraindo no servidor via io.php..."
  io_extract_app || echo "   !! io.php extract_app falhou"
  rm -f "$APP_TGZ"
  echo "$CURRENT_APP_HASH" > "$APP_MARKER"
  echo "   App files sincronizados (scanner.db intocado no servidor)."
else
  echo "   App files não mudaram, pulando sincronização."
fi

# ── 4. Verify (read-only HTTP — não mexe no DB) ──────────────────────────────
echo ""
echo "==> Verificando API (só leitura)..."
sleep 2
if ! curl -fsS --connect-timeout 10 "https://paulista.dev/scanner/api/status" 2>/dev/null | python3 -m json.tool 2>/dev/null; then
  echo "   ⚠️  Aviso: API não respondeu por HTTP (servidor offline ou bloqueio)."
  echo "      A transferência de ficheiros da app via FTP foi efetuada (sem DB)."
fi

echo ""
echo "Deploy concluído (aplicação apenas; sem sync de base de dados)."
