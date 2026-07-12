#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load credentials
set -a; . ./.env; set +a
echo "Deploy -> $FTP_USER@$FTP_HOST"

# 1. Stage
STAGE=$(mktemp -d)
mkdir -p "$STAGE/static" "$STAGE/tmp"

cp app.py passenger_wsgi.py scanners_core.py warming.py indicators.py \
   data_layer.py symbol_store.py symbols_fallback.py "$STAGE/"
cp static/app.js static/index.html static/style.css "$STAGE/static/"
cp requirements-py39.txt .python-version .env "$STAGE/"
date > "$STAGE/tmp/restart.txt"

echo "Stage: $STAGE"
echo "Files: $(find "$STAGE" -type f | wc -l | tr -d ' ')"

# 2. Install deps on server (only if requirements changed or --full flag passed)
if [[ "${1:-}" == "--full" ]]; then
  echo ""
  echo "==> Installing deps on server..."
  ssh paulista@paulista.dev \
    '/home/paulista/virtualenv/scanner/3.9/bin/pip install -r ~/scanner/requirements-py39.txt'
fi

# 3. Upload via FTP (non-destructive mirror — preserves scanner_web.db)
echo ""
echo "==> Uploading to /scanner..."
lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 60
set net:max-retries 3
mirror --reverse --only-newer --verbose --parallel=6 $STAGE /scanner
bye
EOF

# 4. Verify
echo ""
echo "==> Verifying..."
sleep 2
curl -fsS "https://paulista.dev/scanner/api/status" | python3 -m json.tool

echo ""
echo "Deploy concluido."
