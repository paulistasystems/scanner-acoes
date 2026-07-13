#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load credentials
set -a; . ./.env; set +a
echo "Deploy -> $FTP_USER@$FTP_HOST"

# 0. (Build desacoplado) site-packages é construído por ./build.sh separadamente.
#    Rode `./build.sh` manualmente quando requirements-py39.txt mudar. O deploy
#    só re-sobe site-packages se o BUILD_DIR tiver sido reconstruído (passo 4);
#    deploys só-de-código não tocam no build.
#    Pré-requisito: BUILD_DIR (/tmp/scanner_linux_sitepackages) deve existir.

# 1+2. Sync DB: download remoto -> local (preserva dados aquecidos).
#      Só derruba o app local SE o sync trouxer dados de fato — baixar nada
#      não justifica parar o servidor local.
echo ""
echo "==> Sincronizando banco de dados..."
DB_TMP="scanner.db.tmp"
if curl -fs --user "$FTP_USER:$FTP_PASS" \
    "ftp://$FTP_HOST/scanner/scanner.db" -o "$DB_TMP"; then
  if [ -s "$DB_TMP" ]; then
    echo "   Banco remoto baixado: $(ls -lh "$DB_TMP" | awk '{print $5}')"
    echo "==> Parando servidor local (para troca do banco)..."
    pkill -f "python app.py" 2>/dev/null && echo "   Servidor parado." || echo "   Nenhum servidor local rodando."
    mv -f "$DB_TMP" scanner.db
    echo "   scanner.db atualizado."
  else
    rm -f "$DB_TMP"
    echo "   Banco remoto vazio — nada a sincronizar. Servidor local intocado."
  fi
else
  rm -f "$DB_TMP" 2>/dev/null || true
  echo "   Banco remoto ausente ou inacessivel — continuando sem sync. Servidor local intocado."
fi

# 3. Stage
echo ""
echo "==> Montando stage..."
STAGE=$(mktemp -d)
mkdir -p "$STAGE/static" "$STAGE/tmp"

# Preserve original modification times (mtime) so LFTP doesn't think files changed
cp -p app.py passenger_wsgi.py scanners_core.py warming.py indicators.py \
   data_layer.py symbol_store.py symbols_fallback.py "$STAGE/"
cp -p static/app.js static/index.html static/style.css "$STAGE/static/"
cp -p requirements-py39.txt .python-version .env "$STAGE/"
date > "$STAGE/tmp/restart.txt"

echo "   Stage: $STAGE"
echo "   Files: $(find "$STAGE" -type f | wc -l | tr -d ' ')"

# 4. Upload site-packages to server virtualenv (only if build changed)
echo ""
echo "==> Subindo site-packages para virtualenv..."
BUILD_DIR="/tmp/scanner_linux_sitepackages"
BUILD_MARKER="/tmp/scanner_build_marker"
FORCE_DEPLOY=false

if [[ "${1:-}" == "--force" ]]; then
  FORCE_DEPLOY=true
  echo "   Modo force ativado — sobrescrevendo tudo."
fi

if [ -d "$BUILD_DIR" ]; then
  # Check if build actually changed by comparing markers
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

# 5. Upload via FTP (smart sync — only uploads changed files)
echo ""
echo "==> Subindo para /scanner (apenas arquivos mudados)..."
APP_MARKER="/tmp/scanner_app_marker"
CURRENT_APP_HASH=$(find app.py static/ -type f -exec sha1sum {} \; | sort | sha1sum | cut -d' ' -f1)
PREVIOUS_APP_HASH=""

if [ -f "$APP_MARKER" ]; then
  PREVIOUS_APP_HASH=$(cat "$APP_MARKER")
fi

if [ "$FORCE_DEPLOY" = true ] || [ "$CURRENT_APP_HASH" != "$PREVIOUS_APP_HASH" ]; then
  lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 60
set net:max-retries 3
mirror --reverse --delete --only-newer --parallel=4 --verbose $STAGE /scanner
bye
EOF
  echo "$CURRENT_APP_HASH" > "$APP_MARKER"
  echo "   App files sincronizados."
else
  echo "   App files não mudaram, pulando sincronização."
fi

# 6. Verify
echo ""
echo "==> Verificando..."
sleep 2
curl -fsS "https://paulista.dev/scanner/api/status" | python3 -m json.tool

echo ""
echo "Deploy concluido."
