#!/bin/bash
# deploy.sh — sobe APENAS a aplicação (código + site-packages se build mudou).
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

# 0. (Build desacoplado) site-packages é construído por ./build.sh separadamente.
#    Rode `./build.sh` manualmente quando requirements-py39.txt mudar. O deploy
#    só re-sobe site-packages se o BUILD_DIR tiver sido reconstruído;
#    deploys só-de-código não tocam no build.
#    Pré-requisito: BUILD_DIR (/tmp/scanner_linux_sitepackages) deve existir.

# 1. Stage — lista explícita de ficheiros da app (sem DB, sem venv, sem dumps)
echo ""
echo "==> Montando stage (app only)..."
STAGE=$(mktemp -d)
mkdir -p "$STAGE/static" "$STAGE/tmp"

# Preserve original modification times (mtime) so LFTP doesn't think files changed.
cp -p app.py passenger_wsgi.py scanners_core.py warming.py indicators.py \
   data_layer.py symbol_store.py symbols_fallback.py warm_cron.py warm_cron_status.py "$STAGE/"
cp -p static/app.js static/index.html static/style.css "$STAGE/static/"
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

# 2. Upload site-packages to server virtualenv (only if build changed)
echo ""
echo "==> Subindo site-packages para virtualenv..."
BUILD_DIR="/tmp/scanner_linux_sitepackages"
BUILD_MARKER="/tmp/scanner_build_marker"
FORCE_DEPLOY=false

if [[ "${1:-}" == "--force" ]]; then
  FORCE_DEPLOY=true
  echo "   Modo force ativado — sobrescrevendo site-packages/app files (ainda sem DB)."
fi

if [ -d "$BUILD_DIR" ]; then
  CURRENT_HASH=$(find "$BUILD_DIR" -type f -exec sha1sum {} \; | sort | sha1sum | cut -d' ' -f1)
  PREVIOUS_HASH=""
  if [ -f "$BUILD_MARKER" ]; then
    PREVIOUS_HASH=$(cat "$BUILD_MARKER")
  fi

  if [ "$FORCE_DEPLOY" = true ] || [ "$CURRENT_HASH" != "$PREVIOUS_HASH" ]; then
    if [ "$FORCE_DEPLOY" = true ]; then
      echo "   Forçando upload de site-packages..."
    else
      echo "   Build mudou, subindo site-packages..."
    fi
    lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 120
set net:max-retries 3
mirror --reverse --ignore-time --parallel=4 $BUILD_DIR /virtualenv/scanner/3.9/lib/python3.9/site-packages
bye
EOF
    echo "$CURRENT_HASH" > "$BUILD_MARKER"
    echo "   Site-packages atualizado."
  else
    echo "   Build não mudou, pulando site-packages."
  fi
else
  echo "   ERRO: build directory not found. Run ./build.sh first."
  exit 1
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
mkdir -p /scanner/tmp
put $STAGE/tmp/restart.txt -o /scanner/tmp/restart.txt
bye
EOF
  echo "$CURRENT_APP_HASH" > "$APP_MARKER"
  echo "   App files sincronizados (scanner.db intocado no servidor)."
else
  echo "   App files não mudaram, pulando sincronização."
fi

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
