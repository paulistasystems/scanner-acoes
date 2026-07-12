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

source venv39/bin/activate
python app.py
