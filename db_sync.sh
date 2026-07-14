#!/usr/bin/env bash
# db_sync.sh — Warm no stack Docker (local) e anexa o DB ao scanner remoto via FTP.
#
# Arquitetura:
#   docker volume scanner_acoes_data  →  /data/scanner.db  (compose)
#   export → arquivo no host (default: scanner.docker.db, gitignored)
#   upload FTP → /scanner/scanner.db no Passenger (produção)
#
# O deploy.sh NUNCA sobe scanner.db (está em -X). Este script é o caminho
# explícito "warm local → anexar ao app remoto".
#
# Uso:
#   ./db_sync.sh warm [intervalos…]     # prewarm no volume compose
#   ./db_sync.sh export                 # volume → ./scanner.docker.db
#   ./db_sync.sh upload                 # ./scanner.docker.db → FTP remoto
#   ./db_sync.sh download               # FTP remoto → ./scanner.docker.db
#   ./db_sync.sh ship [intervalos…]     # warm + export + upload (pede confirmação)
#   ./db_sync.sh status                 # contagens no export local e/ou remoto (API)
#
set -euo pipefail
cd "$(dirname "$0")"

EXPORT_PATH="${SCANNER_EXPORT:-$PWD/scanner.docker.db}"
VOLUME_NAME="${SCANNER_VOLUME:-scanner_acoes_data}"
CONTAINER_DB="/data/scanner.db"

die() { echo "ERRO: $*" >&2; exit 1; }

need_docker() {
  command -v docker >/dev/null 2>&1 || die "docker não encontrado (OrbStack?)."
}

need_env_ftp() {
  [[ -f .env ]] || die ".env ausente (FTP_HOST/FTP_USER/FTP_PASS)."
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
  : "${FTP_HOST:?FTP_HOST no .env}"
  : "${FTP_USER:?FTP_USER no .env}"
  : "${FTP_PASS:?FTP_PASS no .env}"
}

cmd_warm() {
  need_docker
  echo "==> Warm no volume Docker ($VOLUME_NAME) via compose profile warm"
  echo "    (não toca o scanner.db do Mac nem o de produção até você dar upload)"
  if [[ $# -eq 0 ]]; then
    docker compose --profile warm run --rm warm
  else
    docker compose --profile warm run --rm warm "$@"
  fi
}

# Copia o SQLite do volume nomeado para o host (checkpoint WAL no container).
cmd_export() {
  need_docker
  echo "==> Export $VOLUME_NAME:$CONTAINER_DB → $EXPORT_PATH"
  # Container efêmero com o volume montado; checkpoint para um único ficheiro
  docker run --rm \
    -v "${VOLUME_NAME}:/data" \
    -v "$(dirname "$EXPORT_PATH"):/out" \
    python:3.9-slim-bookworm \
    bash -lc "
      set -e
      python - <<'PY'
import sqlite3, shutil, os
src = '/data/scanner.db'
dst = '/out/$(basename "$EXPORT_PATH")'
if not os.path.isfile(src):
    raise SystemExit('DB ainda não existe no volume — rode: ./db_sync.sh warm')
c = sqlite3.connect(src)
c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
c.close()
shutil.copy2(src, dst)
# remove sidecars no destino se o volume tiver gerado confusão
for s in (dst + '-wal', dst + '-shm'):
    if os.path.isfile(s):
        os.remove(s)
print('ok', dst, 'bytes', os.path.getsize(dst))
# resumo
c = sqlite3.connect(dst)
print('bars', c.execute('select count(*) from bars').fetchone()[0])
print('fill_state', c.execute('select count(*) from fill_state').fetchone()[0])
print('by_interval', c.execute('select interval, count(*) from fill_state group by 1').fetchall())
c.close()
PY
    "
  ls -lh "$EXPORT_PATH"
}

cmd_upload() {
  die "upload remoto desligado no fluxo de dev (working local first). Só warm/export locais."
  need_env_ftp
  [[ -f "$EXPORT_PATH" ]] || die "export não encontrado: $EXPORT_PATH (rode ./db_sync.sh export)"
  local bytes
  bytes=$(wc -c <"$EXPORT_PATH" | tr -d ' ')
  echo "==> Upload FTP → ftp://$FTP_HOST/scanner/scanner.db"
  if [[ "${ASSUME_YES:-}" != "1" ]]; then
    read -r -p "Confirma upload para produção? [y/N] " ans
    [[ "$ans" == "y" || "$ans" == "Y" ]] || die "cancelado"
  fi
  # Sobe o ficheiro principal; remove WAL/SHM remotos para o SQLite não misturar estados
  curl -fsS --user "$FTP_USER:$FTP_PASS" \
    -T "$EXPORT_PATH" "ftp://$FTP_HOST/scanner/scanner.db"
  # best-effort: apaga sidecars remotos (podem deixar o servidor a ler WAL velho)
  if command -v lftp >/dev/null 2>&1; then
    lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<LFTEOF
set ftp:passive-mode on
set cmd:fail-exit no
rm /scanner/scanner.db-wal
rm /scanner/scanner.db-shm
bye
LFTEOF
  fi
  echo "    upload ok. Verifique: curl -s https://paulista.dev/scanner/api/status"
}

cmd_download() {
  need_env_ftp
  echo "==> Download FTP /scanner/scanner.db → $EXPORT_PATH"
  curl -fsS --user "$FTP_USER:$FTP_PASS" \
    "ftp://$FTP_HOST/scanner/scanner.db" -o "$EXPORT_PATH"
  # sidecars opcionais
  curl -fsS --user "$FTP_USER:$FTP_PASS" \
    "ftp://$FTP_HOST/scanner/scanner.db-wal" -o "${EXPORT_PATH}-wal" 2>/dev/null || true
  curl -fsS --user "$FTP_USER:$FTP_PASS" \
    "ftp://$FTP_HOST/scanner/scanner.db-shm" -o "${EXPORT_PATH}-shm" 2>/dev/null || true
  ls -lh "$EXPORT_PATH"*
}

cmd_ship() {
  die "ship/upload desativado no fluxo normal. Use warm+export local; deploy de código é ./deploy.sh quando estiver pronto."
}

cmd_status() {
  if [[ -f "$EXPORT_PATH" ]]; then
    echo "==> Export local: $EXPORT_PATH"
    python3 - <<PY
import sqlite3
c=sqlite3.connect("$EXPORT_PATH")
print("  bars", c.execute("select count(*) from bars").fetchone()[0])
print("  fill", c.execute("select count(*) from fill_state").fetchone()[0])
print("  by_iv", c.execute("select interval,count(*) from fill_state group by 1").fetchall())
try:
  print("  last_filled_max", c.execute("select max(last_filled_at) from fill_state").fetchone()[0])
except Exception as e:
  print("  ", e)
c.close()
PY
  else
    echo "==> Export local: (ausente — $EXPORT_PATH)"
  fi
  echo "==> Compose local /api/status (se stack up)"
  curl -fsS --max-time 5 "http://localhost:8080/scanner/api/status" \
    | python3 -m json.tool 2>/dev/null || echo "  (stack down — ./run_docker.sh up)"
}


usage() {
  cat <<'USAGE'
db_sync.sh — warm / inspeção do DB **local** (volume Docker). Sem deploy/upload.

  ./db_sync.sh warm [iv…]   prewarm no volume compose
  ./db_sync.sh export       volume → ./scanner.docker.db (só no Mac, gitignored)
  ./db_sync.sh status       resumo do export local + API compose se up

Comandos remotes (só se você pedir explicitamente; default é local):
  ./db_sync.sh download     FTP → scanner.docker.db (leitura)
  ./db_sync.sh upload       NÃO usar no fluxo normal de dev
USAGE
}

cmd="${1:-}"
shift || true
case "$cmd" in
  warm)     cmd_warm "$@" ;;
  export)   cmd_export ;;
  upload)   cmd_upload ;;
  download) cmd_download ;;
  ship)     cmd_ship "$@" ;;
  status)   cmd_status ;;
  -h|--help|help|"") usage; [[ -n "$cmd" ]] || exit 2 ;;
  *) die "comando desconhecido: $cmd (veja --help)" ;;
esac
