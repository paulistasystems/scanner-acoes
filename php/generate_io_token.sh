#!/usr/bin/env bash
# Generate a secure IO_PHP_TOKEN and update root .env
# Run from repo root: ./php/generate_io_token.sh
#
# Also updates php/io.php so the token is baked in at deploy time.
# (The PHP also reads getenv('IO_PHP_TOKEN') as fallback.)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

TOKEN=$(openssl rand -hex 32)

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy from .env.example first." >&2
  exit 1
fi

if grep -q '^IO_PHP_TOKEN=' "$ENV_FILE" 2>/dev/null; then
  sed -i "s/^IO_PHP_TOKEN=.*/IO_PHP_TOKEN=$TOKEN/" "$ENV_FILE"
else
  echo "" >> "$ENV_FILE"
  echo "# Token for php/io.php (server-side IO helper)" >> "$ENV_FILE"
  echo "IO_PHP_TOKEN=$TOKEN" >> "$ENV_FILE"
fi

echo "Generated token: $TOKEN"
echo "Updated $ENV_FILE"
echo ""
echo "IMPORTANT: Ensure IO_PHP_TOKEN is also set as an environment variable"
echo "on the server (DirectAdmin → PHP Selector → env vars, or .user.ini)."
echo "The php/io.php reads getenv('IO_PHP_TOKEN') at runtime."
