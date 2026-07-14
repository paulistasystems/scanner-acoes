#!/usr/bin/env bash
# remote_logs.sh — baixa logs do app remoto (FTP) para ./remote_logs/ (local).
#
# Principal: log do cron de warm
#   cd /home/paulista/scanner && \
#     .../python warm_cron.py >> /home/paulista/scanner/tmp/warm_cron.log 2>&1
#   ⇒ FTP: /scanner/tmp/warm_cron.log  →  ./remote_logs/tmp/warm_cron.log
#
# Também tenta stderr.log (Passenger) na raiz do app.
# Destino local: ./remote_logs/  — gitignored e fora do stage do deploy.sh.
#
# Uso:
#   ./remote_logs.sh
#   ./remote_logs.sh --list
#
# Pré-requisitos: lftp, .env com FTP_HOST / FTP_USER / FTP_PASS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOCAL_DIR="$SCRIPT_DIR/remote_logs"
REMOTE_WARM_LOG="/scanner/tmp/warm_cron.log"
LOCAL_WARM_LOG="$LOCAL_DIR/tmp/warm_cron.log"
REMOTE_STDERR_LOG="/scanner/stderr.log"
LOCAL_STDERR_LOG="$LOCAL_DIR/stderr.log"
LIST_ONLY=false

usage() {
  cat <<EOF
Uso: $(basename "$0") [--list] [-h|--help]

Baixa logs do servidor (FTP /scanner) para ./remote_logs/.

Foco: $REMOTE_WARM_LOG
  (cron: warm_cron.py >> .../tmp/warm_cron.log 2>&1)

  --list     lista logs remotos conhecidos (não baixa)
  -h, --help esta ajuda

Credenciais: .env (FTP_HOST, FTP_USER, FTP_PASS) — mesmo padrão do deploy.sh.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --list) LIST_ONLY=true ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Argumento desconhecido: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -f .env ]]; then
  echo "ERRO: .env não encontrado. cp .env.example .env e preencha FTP_*." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

: "${FTP_HOST:?FTP_HOST não definido no .env}"
: "${FTP_USER:?FTP_USER não definido no .env}"
: "${FTP_PASS:?FTP_PASS não definido no .env}"

if ! command -v lftp >/dev/null 2>&1; then
  echo "ERRO: lftp não instalado (brew install lftp)." >&2
  exit 1
fi

if [[ "$LIST_ONLY" == true ]]; then
  echo "Listando logs em ftp://$FTP_HOST ..."
  lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 30
set net:max-retries 2
set cmd:fail-exit no
echo "--- $REMOTE_WARM_LOG ---"
cls -l $REMOTE_WARM_LOG
echo "--- $REMOTE_STDERR_LOG ---"
cls -l $REMOTE_STDERR_LOG
echo "--- /scanner/tmp/ ---"
cls -la /scanner/tmp/
bye
EOF
  exit 0
fi

mkdir -p "$LOCAL_DIR/tmp"

echo "Baixando logs remotos -> $LOCAL_DIR"
echo "  $FTP_USER@$FTP_HOST"
echo "  principal: $REMOTE_WARM_LOG"

# gets explícitos (sem mirror/mget glob — evita hang do lftp em wildcards vazios)
lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 30
set net:max-retries 2
set cmd:fail-exit no
get -c $REMOTE_WARM_LOG -o $LOCAL_WARM_LOG
get -c $REMOTE_STDERR_LOG -o $LOCAL_STDERR_LOG
get -c /scanner/tmp/warm_cron_status.json -o $LOCAL_DIR/tmp/warm_cron_status.json
bye
EOF

echo ""
echo "Logs salvos em: $LOCAL_DIR"

if [[ -f "$LOCAL_WARM_LOG" ]]; then
  size=$(wc -c <"$LOCAL_WARM_LOG" | tr -d ' ')
  printf '  ✓ warm_cron.log  %s B  ->  tmp/warm_cron.log\n' "$size"
else
  echo "  ✗ warm_cron.log AUSENTE no servidor ($REMOTE_WARM_LOG)"
  echo "    O cron ainda não criou o arquivo (redirect só grava na 1ª execução)."
  echo "    No DirectAdmin, confira o cron e rode uma vez à mão:"
  echo "      cd /home/paulista/scanner && \\"
  echo "        /home/paulista/virtualenv/scanner/3.9/bin/python warm_cron.py \\"
  echo "        >> /home/paulista/scanner/tmp/warm_cron.log 2>&1"
fi

if [[ -f "$LOCAL_STDERR_LOG" ]]; then
  size=$(wc -c <"$LOCAL_STDERR_LOG" | tr -d ' ')
  printf '  + stderr.log     %s B\n' "$size"
fi

echo ""
echo "Pasta local é gitignored e não entra no stage do deploy.sh."
