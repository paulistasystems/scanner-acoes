#!/bin/bash
# Scanner web (Flask/WSGI) — branch master
# Sobe o servidor em $PORT (default 5001). Antes de iniciar, mata qualquer
# processo antigo que ainda esteja segurando a porta — resto de um Ctrl+C que
# não encerrou o processo filho do Flask (app.py roda com use_reloader=False).

cd "$(dirname "$0")" || exit 1

PORT="${PORT:-5001}"

echo "Iniciando Scanner (Versão Web/Vanilla - branch master)..."
echo "Usando venv39 (Python 3.9) na porta $PORT..."

# Libera a porta se já estiver ocupada por um servidor anterior
PIDS=$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null)
if [ -n "$PIDS" ]; then
  echo "Porta $PORT ocupada pelos PIDs: $(echo "$PIDS" | tr '\n' ' ')"
  echo "Encerrando..."
  echo "$PIDS" | xargs kill 2>/dev/null
  # aguarda até 5s por um encerramento limpo (SIGTERM)
  for _ in 1 2 3 4 5; do
    sleep 1
    [ -z "$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null)" ] && break
  done
  # se ainda assim não liberou, força com SIGKILL
  if [ -n "$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null)" ]; then
    echo "Não respondeu ao SIGTERM — forçando kill -9..."
    echo "$PIDS" | xargs kill -9 2>/dev/null
    sleep 1
  fi
  echo "Porta liberada."
fi

# --- Egress PHP (Yahoo Chart API) — mesmo recurso em local e remoto ----------
# O data_layer busca candles via SCANNER_CHART_URL (proxy PHP, php/yahoo_chart.php).
# Sobe o serviço local na porta 8008 se ainda não estiver no ar.
PHP_PORT="${PHP_PORT:-8008}"
export SCANNER_CHART_URL="http://127.0.0.1:${PHP_PORT}/yahoo_chart.php"
if ! lsof -tiTCP:"$PHP_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Subindo egress PHP na porta $PHP_PORT..."
  if command -v php >/dev/null 2>&1; then PHPBIN="php"
  else PHPBIN="$(brew --prefix php@8.3 2>/dev/null)/bin/php"; fi
  ( cd php && exec "$PHPBIN" -S 127.0.0.1:"$PHP_PORT" -t . ) &
  echo "  PHP egress PID $!  ->  $SCANNER_CHART_URL"
fi

source venv39/bin/activate
python app.py
