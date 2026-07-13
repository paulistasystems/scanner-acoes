#!/bin/bash
# php/run_php_server.sh — sobe o serviço PHP local (egress do Yahoo Chart API).
#
# O scanner local (data_layer via SCANNER_CHART_URL) aponta para cá, assim o
# ambiente local e o remoto usam exatamente o mesmo recurso (yahoo_chart.php) —
# único caminho de aquisição de candles. Requer PHP 8.3+ (`brew install php@8.3`).
#
#   ./php/run_php_server.sh          # 127.0.0.1:8008
#   PHP_PORT=8090 ./php/run_php_server.sh

cd "$(dirname "$0")" || exit 1

HOST="${PHP_HOST:-127.0.0.1}"
PORT="${PHP_PORT:-8008}"

if ! command -v php >/dev/null 2>&1; then
  PHPBIN="$(brew --prefix php@8.3 2>/dev/null)/bin/php"
  [ -x "$PHPBIN" ] || { echo "PHP não encontrado. Rode: brew install php@8.3"; exit 1; }
  PHP="$PHPBIN"
else
  PHP="php"
fi

echo "PHP chart egress em http://$HOST:$PORT/yahoo_chart.php ..."
exec "$PHP" -S "$HOST:$PORT" -t .
