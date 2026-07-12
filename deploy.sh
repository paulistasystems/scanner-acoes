#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load credentials
set -a; . ./.env; set +a
echo "Deploy -> $FTP_USER@$FTP_HOST"

# 1. Stop local server if running
echo ""
echo "==> Parando servidor local (se rodando)..."
pkill -f "python app.py" 2>/dev/null && echo "   Servidor parado." || echo "   Nenhum servidor local rodando."

# 2. Sync DB: download remoto -> local (preserva dados aquecidos)
echo ""
echo "==> Sincronizando banco de dados..."
if curl -fs --user "$FTP_USER:$FTP_PASS" \
    "ftp://$FTP_HOST/scanner/scanner_web.db" -o scanner_web.db; then
  echo "   scanner_web.db baixado: $(ls -lh scanner_web.db | awk '{print $5}')"
else
  echo "   Banco remoto ausente ou inacessivel — continuando sem sync."
fi

# 3. Stage
echo ""
echo "==> Montando stage..."
STAGE=$(mktemp -d)
mkdir -p "$STAGE/static" "$STAGE/tmp"

cp app.py passenger_wsgi.py scanners_core.py warming.py indicators.py \
   data_layer.py symbol_store.py symbols_fallback.py "$STAGE/"
cp static/app.js static/index.html static/style.css "$STAGE/static/"
cp requirements-py39.txt .python-version .env "$STAGE/"
date > "$STAGE/tmp/restart.txt"

echo "   Stage: $STAGE"
echo "   Files: $(find "$STAGE" -type f | wc -l | tr -d ' ')"

# 4. Install deps on server (--full flag)
if [[ "${1:-}" == "--full" ]]; then
  echo ""
  echo "==> Instalando deps no servidor..."
  ssh paulista@paulista.dev \
    '/home/paulista/virtualenv/scanner/3.9/bin/pip install -r ~/scanner/requirements-py39.txt'
fi

# 5. Upload via FTP (non-destructive mirror — preserves scanner_web.db)
echo ""
echo "==> Subindo para /scanner..."
lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 60
set net:max-retries 3
mirror --reverse --only-newer --verbose --parallel=6 $STAGE /scanner
bye
EOF

# 6. Verify
echo ""
echo "==> Verificando..."
sleep 2
curl -fsS "https://paulista.dev/scanner/api/status" | python3 -m json.tool

echo ""
echo "Deploy concluido."
