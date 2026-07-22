# DEPLOY — scanner web (`master`)

Procedimento de deploy da versão web (Flask/WSGI + HTML/JS vanilla) para o
servidor **Phusion Passenger (DirectAdmin)** em `paulista.dev/scanner`.

- **Local**: este repo, branch `master`, Python 3.9 (`venv39/`).
- **Remoto**: app root `/home/paulista/scanner` ⇒ caminho FTP `/scanner`. 
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
./deploy.sh
```

O script `deploy.sh` sobe **só a aplicação** (código / static / `.env` / site-packages se o build mudou).

**Não** baixa nem envia `scanner.db` (exclusão explícita no mirror + stage sem DB).
Warm e dados ficam no servidor (cron / `POST /api/warm`).

### Deploy forçado (se necessário)

```bash
./deploy.sh --force
```

Força upload completo mesmo que nada mudou (útil após problemas).

---

## Pré-requisitos (uma vez por máquina)

```bash
brew install lftp curl trash-cli  # macOS
cp .env.example .env            # preencha FTP_HOST / FTP_USER / FTP_PASS
./php/generate_io_token.sh      # gera IO_PHP_TOKEN e atualiza .env
```

---

## Como funciona: deploy.sh

### `deploy.sh` - Smart deploy

Hash-based comparison para evitar uploads desnecessários, e **tarball + PHP
extraction** no lugar do lento `mirror --reverse` FTP:

- **Site-packages**: build Docker → `tar -czf` → `ftp_put` (1 ficheiro) →
  `php/io.php?op=extract_sitepackages` (PharData extract no venv remoto).
- **App files**: stage (cp) → `tar -czf` → `ftp_put` (1 ficheiro) →
  `php/io.php?op=extract_app` (rmrf de static/ + __pycache__, depois extract).
- **PHP proxies + symbols.json + io.php**: individual `put` via FTP (são poucos).
- **Hashes SHA1** de conteúdo para saltar passos quando nada mudou.

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

- `scanner.db` — banco SQLite de runtime. **Fora do deploy** (nunca sync).
- `__pycache__/`, `*.pyc`, `venv39/`, `venv313/`
- `scanner_interface_Streamlit.py`, `scanner_abertura.py`, `painel_bd.py` — Streamlit dormentes.
- `*.txt` (transcrições), `tools/`

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

## Troubleshooting

- **500 / Internal Server Error** — deps incompatíveis ou `.env` ausente.
- **Restart não pegou** — reenvie `tmp/restart.txt` (seção acima).
- **Timeout no `/api/scan`** — dispare `/api/warm` e aguarde.
- **Tarball extract falhou (`io.php`)** — verifique se `IO_PHP_TOKEN` está
  configurado no servidor (DirectAdmin → PHP Selector → env vars) e no `.env`
  local. Execute `./php/generate_io_token.sh` para regenerar.
- **io.php devolve 403** — token incorreto ou não definido no servidor.
- **Build lento** — wheels são cacheados, builds seguintes são rápidos.
- **Deploy re-upando tudo** — use `--force` apenas se necessário.

---

## Notas de segurança

- `.env` guarda a senha FTP — nunca commitar (`.gitignore` já cobre).

---

## Arquitetura

- **Python 3.9** (pinned em `.python-version`)
- **Flask/WSGI** (sem Streamlit)
- **Deploy automático** via `deploy.sh` + helpers em `php/io.php`
- **Sem pandas_ta/numba** (indicadores reimplementados em pandas puro)

