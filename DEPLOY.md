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
```

---

## Como funciona: build.sh + deploy.sh

### `build.sh` - Build de packages Linux

Compila packages compatíveis com Python 3.9 Linux (manylinux x86_64):
- Download wheels para Python 3.9 Linux
- Instala em `/tmp/scanner_linux_sitepackages/`
- Cacheia wheels em `/tmp/scanner_wheels/` (reúso em builds seguintes)

**Resultado**: ~128MB de packages prontos para deploy.

### `deploy.sh` - Smart deploy

Hash-based comparison para evitar uploads desnecessários:
- **Hash do build** - Só sobe site-packages se o build mudou
- **Hash dos arquivos** - Só sobe app files se mudaram
- **`--only-newer`** - FTP só sobe arquivos mais recentes
- **`--delete`** - Remove arquivos órfãos no servidor

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

- **500 / Internal Server Error** —_deps incompatíveis ou `.env` ausente.
- **Restart não pegou** — reenvie `tmp/restart.txt` (seção acima).
- **Timeout no `/api/scan`** — dispare `/api/warm` e aguarde.
- **Mirror apagou o DB** — use sync DB (seção acima).
- **Build lento** — wheels são cacheados, builds seguintes são rápidos.
- **Deploy re-upando tudo** — use `--force` apenas se necessário.

---

## Notas de segurança

- `.env` guarda a senha FTP — nunca commitar (`.gitignore` já cobre).

---

## Arquitetura do branch `vanilla-web-scanner`

Este branch é um **paralelo** ao `master`:
- **Python 3.9** (pinned em `.python-version`)
- **Flask/WSGI** (sem Streamlit)
- **Deploy automático** via `build.sh` + `deploy.sh`
- **Sem pandas_ta/numba** (indicadores reimplementados em pandas puro)

