# DEPLOY — scanner web (`master`)

Procedimento de deploy da versão web (Flask/WSGI + HTML/JS vanilla) para o
servidor **Phusion Passenger (DirectAdmin)** em `paulista.dev/scanner`.

- **Local**: este repo, branch `master`, Python 3.9 (`venv39/`).
- **Remoto**: app root `/home/paulista/scanner` ⇒ caminho FTP `/scanner`
  (relativo ao home do usuário `paulista`). Servido em `https://paulista.dev/scanner`.
- **Virtualenv remoto**: `/home/paulista/virtualenv/scanner/3.9/` (Python 3.9.19).
- **Entrada Passenger**: [`passenger_wsgi.py`](passenger_wsgi.py) → `application = app`
  (importa `app` de [`app.py`](app.py)).
- **Universo de ativos**: lista bundled em [`symbols_fallback.py`](symbols_fallback.py)
  (sem Supabase — o app não depende de serviço externo além do Yahoo Finance).

> **Credenciais**: host/usuário/senha FTP ficam em [`.env`](.env) (gitignored) —
> template versionável em [`.env.example`](.env.example).

---

## Fluxo normal de deploy

```
1. git commit + git push
2. ./deploy.sh
```

### 1. Commit e push

```bash
git add <arquivos>
git commit -m "feat: ..."
git push origin master
```

### 2. Deploy para o servidor

```bash
./deploy.sh
```

O script faz tudo: monta o stage, sobe via FTP (mirror não-destrutivo, preserva
`scanner_web.db`) e verifica a API no final.

Se `requirements-py39.txt` mudou (nova/removida dependência), use `--full` para
instalar as deps no venv remoto via SSH antes do upload:

```bash
./deploy.sh --full
```

---

## Pré-requisitos (uma vez por máquina)

```bash
brew install lftp curl        # macOS
cp .env.example .env          # preencha FTP_HOST / FTP_USER / FTP_PASS
```

---

## Arquivos do deploy

### ✅ Subir (gerenciado pelo `deploy.sh`)

| Grupo | Arquivos |
|---|---|
| Backend Python | `app.py`, `passenger_wsgi.py`, `scanners_core.py`, `warming.py`, `indicators.py`, `data_layer.py`, `symbol_store.py`, `symbols_fallback.py` |
| Frontend | `static/` (`app.js`, `index.html`, `style.css`) |
| Config | `requirements-py39.txt`, `.python-version` |
| Secrets | `.env` (**gitignored**, incluído pelo script automaticamente) |

### 🚫 NÃO subir (o script já ignora)

- `scanner_web.db` — banco SQLite gerado em runtime. O mirror não-destrutivo preserva o remoto.
- `__pycache__/`, `*.pyc`, `venv39/`, `venv313/`
- `scanner_interface_Streamlit.py`, `scanner_abertura.py`, `painel_bd.py` — Streamlit dormentes.
- `*.txt` (transcrições), `tools/`, `scanner.db` (versão 3.13 do `streamlit-legacy`)

---

## Sincronizar o banco SQLite (opcional)

O `scanner_web.db` **não é versionado**. Para preservar dados aquecidos:

### Download remoto → local

```bash
set -a; . ./.env; set +a
curl -s --user "$FTP_USER:$FTP_PASS" \
  "ftp://$FTP_HOST/scanner/scanner_web.db" -o scanner_web.db
ls -lh scanner_web.db
```

### Upload local → remoto (pré-aquecer servidor a partir do warm local)

```bash
set -a; . ./.env; set +a
curl -s --user "$FTP_USER:$FTP_PASS" \
  -T scanner_web.db "ftp://$FTP_HOST/scanner/scanner_web.db"
```

---

## Restart manual do Passenger

O `deploy.sh` já inclui `tmp/restart.txt` no stage — o Passenger recarrega
automaticamente na próxima request. Para forçar à parte:

```bash
set -a; . ./.env; set +a
echo "$(date)" > /tmp/restart.txt
curl -s --user "$FTP_USER:$FTP_PASS" \
  -T /tmp/restart.txt "ftp://$FTP_HOST/scanner/tmp/restart.txt"
```

---

## Aquecer o banco (pós-deploy com DB zerado)

```bash
# Dispara o warm em background
curl -s -X POST https://paulista.dev/scanner/api/warm \
  -H 'Content-Type: application/json' \
  -d '{"intervals":"1d,1h,30m"}' | python3 -m json.tool

# Acompanha o progresso (poll até "running": false)
curl -s https://paulista.dev/scanner/api/status | python3 -m json.tool
```

> Universal = 220+ ativos × intervalos. Espere 5–15 min.
> **Alternativa**: warm local (`./run_web.sh`) + upload do DB (seção acima).

---

## Limpeza / inspeção remota (toolkit `~/scripts`)

| Tarefa | Comando |
|---|---|
| Uso de disco do `/scanner` | `~/scripts/ftp_du.sh /scanner` |
| Listar conteúdo de `/scanner` | `~/scripts/ftp_delete_dir.sh --list /scanner` |
| Deletar `__pycache__` remoto | `~/scripts/ftp_delete_dir.sh /scanner/__pycache__` |
| Download completo do servidor → `~/asura` | `~/scripts/ftp_mirror.sh` |

---

## Troubleshooting

- **500 / tela branca após deploy** — dep faltando (rode `./deploy.sh --full`) ou
  `.env` ausente no servidor.
- **Restart não pegou** — reenvie `tmp/restart.txt` (seção acima).
- **Timeout no `/api/scan`** — dispare `/api/warm` e aguarde.
- **Mirror apagou o DB** — você usou `ftp_sync.sh --delete`. Dispare o warm ou restaure via upload.
- **`421` / limite de conexões no lftp** — reduza `--parallel` (ex.: `4`).

---

## Notas de segurança

- `.env` guarda a senha FTP — nunca commitar (`.gitignore` já cobre).
- O toolkit `~/scripts/ftp_*.sh` embute credenciais no topo — `chmod 700` em máquina compartilhada.
