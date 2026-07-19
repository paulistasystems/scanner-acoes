#!/bin/bash
# deploy.sh — sobe aplicação e constrói dependências (site-packages) se necessário.
#
# NUNCA sincroniza scanner.db (nem upload nem download).
# O banco de produção fica no servidor; warm/DB é outro fluxo (cron / POST /api/warm).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load credentials
set -a; . ./.env; set +a
echo "Deploy -> $FTP_USER@$FTP_HOST"
echo "   Política: só aplicação. scanner.db NÃO é enviado nem baixado."

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

# 2. Build and Upload site-packages to server virtualenv (só se requirements mudarem)
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
  rm -rf "$BUILD_DIR" tmp_build_output
  mkdir -p "$BUILD_DIR"

  CONTAINER="scanner_build_$$"
  docker rm -f "$CONTAINER" >/dev/null 2>&1
  docker run -v "$PWD":/app -w /app --name "$CONTAINER" scanner_acoes-passenger:latest sh -c 'rm -rf /tmp/wheels && mkdir -p /tmp/wheels && pip install -r requirements-py39.txt --target /tmp/wheels --no-cache-dir && echo DONE'

  docker cp "$CONTAINER:/tmp/wheels/." "$BUILD_DIR/"
  docker rm -f "$CONTAINER" >/dev/null 2>&1

  echo "   Subindo novos site-packages para o servidor..."
  lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 120
set net:max-retries 3
mirror --reverse --ignore-time --parallel=4 $BUILD_DIR /virtualenv/scanner/3.9/lib/python3.9/site-packages
bye
EOF
  echo "$CURRENT_REQ_HASH" > "$REQ_MARKER"
  echo "   Site-packages atualizados localmente e no servidor."
else
  echo "   Requirements não mudaram. Pulando upload de site-packages."
fi

# 3. Upload app files only (never database)
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
  lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 60
set net:max-retries 3
# App only. NUNCA espelhar/apagar/subir o banco de runtime:
#   scanner.db, scanner.db-wal, scanner.db-shm, qualquer *.db
# tmp/ de runtime (logs, lock, status) também fica de fora do --delete.
mirror --reverse --delete --only-newer --parallel=4 --verbose \
  -X 'scanner.db' -X 'scanner.db-*' -X 'scanner.db*' \
  -X '*.db' -X '*.db-wal' -X '*.db-shm' \
  -X 'tmp' -X 'tmp/*' -X 'tmp/**' \
  -X '*.log' -X '*.lock' \
  -X 'remote_logs' -X 'remote_logs/**' \
  -X '__pycache__' -X '__pycache__/**' \
  $STAGE /scanner
# Passenger restart (só touch; não mexe no DB)
mkdir -f /scanner/tmp 2>/dev/null || true
put $STAGE/tmp/restart.txt -o /scanner/tmp/restart.txt
bye
EOF
  echo "$CURRENT_APP_HASH" > "$APP_MARKER"
  echo "   App files sincronizados (scanner.db intocado no servidor)."
else
  echo "   App files não mudaram, pulando sincronização."
fi

# 3b. Upload PHP proxies + symbols.json para o SUBPATH /scanner/ DO DOMÍNIO
#     (paulista.dev/scanner/): yahoo_chart.php, yahoo_bulk.php, yahoo_probe.php,
#     yahoo_snapshot.php, warm_cron_status.php e symbols.json (universo
#     autoritativo do egress). Estes vivem no subpath /scanner/ do docroot
#     (public_html/scanner/), servidos em https://paulista.dev/scanner/*.php.
#     O symbols.json DEVE acompanhar symbols_fallback.py: mudanças no universo
#     de ativos (ex.: delistar RBRF11.SA) exigem reupload deste ficheiro.
PHP_DEPLOY="/domains/paulista.dev/public_html/scanner"
echo ""
echo "==> Subindo PHP proxies + symbols.json para $PHP_DEPLOY ..."
lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 60
set net:max-retries 3
# Apenas os ficheiros conhecidos do subpath — NUNCA apagar o resto do docroot.
mkdir -p $PHP_DEPLOY
put php/yahoo_chart.php   -o $PHP_DEPLOY/yahoo_chart.php
put php/yahoo_bulk.php    -o $PHP_DEPLOY/yahoo_bulk.php
put php/yahoo_probe.php   -o $PHP_DEPLOY/yahoo_probe.php
put php/yahoo_snapshot.php -o $PHP_DEPLOY/yahoo_snapshot.php
put php/warm_cron_status.php -o $PHP_DEPLOY/warm_cron_status.php
put php/symbols.json      -o $PHP_DEPLOY/symbols.json
bye
EOF
echo "   PHP proxies + symbols.json sincronizados (docroot intacto)."

# 4. Verify (read-only HTTP — não mexe no DB)
echo ""
echo "==> Verificando API (só leitura)..."
sleep 2
if ! curl -fsS --connect-timeout 10 "https://paulista.dev/scanner/api/status" 2>/dev/null | python3 -m json.tool 2>/dev/null; then
  echo "   ⚠️  Aviso: API não respondeu por HTTP (servidor offline ou bloqueio)."
  echo "      A transferência de ficheiros da app via FTP foi efetuada (sem DB)."
fi

echo ""
echo "Deploy concluído (aplicação apenas; sem sync de base de dados)."
