# DEPLOY — scanner web (branch `vanilla-web-scanner`)

Procedimento de deploy da versão web (Flask/WSGI + HTML/JS vanilla) para o
servidor **Phusion Passenger (DirectAdmin)** em `paulista.dev/scanner`.

- **Local**: este repo, branch `vanilla-web-scanner`, Python 3.9 (`venv39/`).
- **Remoto**: app root `/home/paulista/scanner` ⇒ caminho FTP `/scanner`
  (relativo ao home do usuário `paulista`). Servido em `https://paulista.dev/scanner`.
- **Virtualenv remoto**: `/home/paulista/virtualenv/scanner/3.9/` (Python 3.9.19).
- **Entrada Passenger**: [`passenger_wsgi.py`](passenger_wsgi.py) → `application = app`
  (importa `app` de [`app.py`](app.py)).
- **Universo de ativos**: lista bundled em [`symbols_fallback.py`](symbols_fallback.py)
  (sem Supabase — o app não depende de serviço externo além do Yahoo Finance).

> **Ferramenta de FTP**: este procedimento usa o toolkit em `~/scripts`
> (atalho `~/_`). Veja `~/scripts/README.md` para o briefing completo. O script de
> upload é o **[`ftp_sync.sh`](~/scripts/ftp_sync.sh)**.
>
> **Credenciais**: host/usuário/senha FTP ficam em [`.env`](.env) (gitignored) —
> template versionável em [`.env.example`](.env.example). Os comandos `lftp`/`curl`
> deste doc leem `$FTP_HOST`/`$FTP_USER`/`$FTP_PASS` depois de
> `set -a; . ./.env; set +a` (passo 0).

---

## 0. Pré-requisitos (uma vez por máquina/deploys futuros)

O toolkit `~/scripts` roda `lftp` (uploads/mirror) e `curl` (listing/payload).
Instale se faltar:

```bash
brew install lftp curl        # macOS
```

> **Sem `lftp`**, os comandos `ftp_sync.sh` / mirror abaixo não funcionam. Os
> `curl -T` (upload de arquivo único) continuam funcionando.

Carregue as credenciais do `.env` antes dos comandos deste doc:

```bash
cp .env.example .env          # 1ª vez apenas; depois edite com valores reais
set -a; . ./.env; set +a      # exporta FTP_HOST/FTP_USER/FTP_PASS
echo "FTP -> $FTP_USER@$FTP_HOST"   # conferência rápida (NÃO exibe a senha)
```

---

## 1. Arquivos do deploy

### ✅ Subir (conjunto de runtime)

| Grupo | Arquivos |
|---|---|
| Backend Python | `app.py`, `passenger_wsgi.py`, `scanners_core.py`, `warming.py`, `indicators.py`, `data_layer.py`, `symbol_store.py`, `symbols_fallback.py` |
| Frontend | `static/` (`app.js`, `index.html`, `style.css`) |
| Config | `requirements-py39.txt`, `.python-version` |
| Secrets | `.env` (**gitignored**, suba manualmente via FTP) |

### 🚫 NÃO subir (artefatos de runtime / arquivos do master)

- `scanner_web.db`, `scanner_web.db-shm`, `scanner_web.db-wal` — banco SQLite
  gerado em runtime. **Deletá-lo no remoto obriga um re-warm de 5–15 min.** Preservar.
- `__pycache__/`, `*.pyc`, `venv39/`, `venv313/`
- `scanner_interface_Streamlit.py`, `scanner_abertura.py`, `painel_bd.py` —
  Streamlit dormentes neste branch.
- `*.txt` (transcrições de sessão), `tools/`, `scanner.db` (versão 3.13 do master)

---

## 2. (Primeiro deploy / mudança de deps) Instalar requirements no venv remoto

FTP **não consegue** rodar `pip`. Se for o primeiro deploy ou se
`requirements-py39.txt` mudou, instale as deps no virtualenv remoto via SSH:

```bash
ssh paulista@paulista.dev \
  '/home/paulista/virtualenv/scanner/3.9/bin/pip install -r ~/scanner/requirements-py39.txt'
```

> Em deploys só de código (sem mudar o `requirements`), **pule este passo**.

---

## 2b. (Opcional) Sincronizar o banco SQLite

O `scanner_web.db` fica no servidor e **não é versionado**. Para preservar os dados
aquecidos entre deploys, faça o download antes de um reset ou upload após um warm local.

### Download do banco remoto → local (preservar dados aquecidos)

```bash
set -a; . ./.env; set +a
curl -s --user "$FTP_USER:$FTP_PASS" \
  "ftp://$FTP_HOST/scanner/scanner_web.db" -o scanner_web.db
ls -lh scanner_web.db
```

### Upload do banco local → remoto (inicializar servidor com warm local)

```bash
set -a; . ./.env; set +a
curl -s --user "$FTP_USER:$FTP_PASS" \
  -T scanner_web.db "ftp://$FTP_HOST/scanner/scanner_web.db"
```

> Use o upload **somente** quando quiser pré-aquecer o servidor a partir de um warm
> feito localmente. Em deploys normais de código, o banco remoto já existe e não
> precisa ser sobrescrito.

---

## 3. Montar o conjunto de deploy (staging)

Monte uma pasta limpa só com o conjunto de runtime — assim o upload nunca toca
no DB remoto nem em lixo (`__pycache__`, `.txt`, etc.):

```bash
cd /Users/andersonnascimento/projects/scanner_acoes

STAGE=$(mktemp -d)                                    # ex.: /tmp/tmp.XXXXX
mkdir -p "$STAGE/static" "$STAGE/tmp"

# Backend
cp app.py passenger_wsgi.py scanners_core.py warming.py indicators.py \
   data_layer.py symbol_store.py symbols_fallback.py "$STAGE/"
# Frontend
cp static/app.js static/index.html static/style.css "$STAGE/static/"
# Config + secrets
cp requirements-py39.txt .python-version .env "$STAGE/"
# Gatilho de restart do Passenger (conteúdo novo a cada deploy → mtime muda)
date > "$STAGE/tmp/restart.txt"

echo "STAGE=$STAGE"; ls -laR "$STAGE"
```

> Guarde o caminho impresso em `STAGE=` — ele é usado no passo 4.

---

## 4. Subir via FTP para `/scanner`

### 4a. Recomendado: mirror **não-destrutivo** (preserva `scanner_web.db`)

Empurra só arquivos novos/mais novos, **sem** apagar nada no remoto. É o seguro
para um deploy de código que preserva o banco já aquecido:

```bash
STAGE=/tmp/tmp.XXXXX            # colar o caminho do passo 3

lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
set net:timeout 60
set net:max-retries 3
mirror --reverse --only-newer --verbose --parallel=6 "$STAGE" /scanner
bye
EOF
```

### 4b. Alternativa: `ftp_sync.sh` (mirror **com deleção**)

O [`~/scripts/ftp_sync.sh`](~/scripts/ftp_sync.sh) faz `lftp mirror --reverse
--delete`: **apaga no remoto tudo que não existir localmente**. Útil para um sync
limpo, mas vai **deletar `scanner_web.db` e `tmp/`** remotos se eles não estiverem
no `$STAGE` — então só use quando quiser zerar o estado (e aceitar o re-warm):

```bash
~/scripts/ftp_sync.sh "$STAGE" /scanner --parallel 6
```

> Em geral prefira **4a**. Reserve 4b para um reset deliberado.

---

## 5. Reiniciar o Passenger

O passo 3 já incluiu `tmp/restart.txt` no `$STAGE`, então o mirror (4a/4b) o subiu
para `/scanner/tmp/restart.txt`. O Passenger detecta mudança de **mtime** desse
arquivo e recarrega a app na próxima request — **nenhuma ação extra necessária**.

Se quiser forçar o restart à parte (ex.: só reiniciou deps sem subir código):

```bash
echo "$(date)" > /tmp/restart.txt
curl -s --user "$FTP_USER:$FTP_PASS" \
  -T /tmp/restart.txt "ftp://$FTP_HOST/scanner/tmp/restart.txt"
```

---

## 6. Verificar o deploy

```bash
# 1) App responde (HTML do index)
curl -fsS https://paulista.dev/scanner/ | head -5

# 2) API de status OK (JSON com summary + warming=false)
curl -fsS https://paulista.dev/scanner/api/status | python3 -m json.tool

# 3) Lista de scanners carrega
curl -fsS https://paulista.dev/scanner/api/scanners | python3 -m json.tool
```

Se a `/api/status` devolver **500 ou HTML de erro do Passenger**, veja
[Troubleshooting](#troubleshooting) — quase sempre é dep faltando (passo 2) ou
`.env` ausente/mal preenchido.

---

## 7. Aquecer o banco (pós-deploy com DB zerado)

Após um deploy com DB zerado (4b) ou o primeiro deploy, dispare o warm em
background e acompanhe o progresso pelo frontend (botão **Aquecer** no painel) ou
pela API:

```bash
# Dispara o warm (Universal = 220+ ativos × intervalos; roda em background)
curl -s -X POST https://paulista.dev/scanner/api/warm \
  -H 'Content-Type: application/json' \
  -d '{"intervals":"1d,1h,30m"}' | python3 -m json.tool

# Acompanhe o progresso (poll até "running": false)
curl -s https://paulista.dev/scanner/api/status | python3 -m json.tool
```

> Cada request HTTP só **lê** o banco (rápido, <2s); o warm roda em background
> ([`warming.py`](warming.py)) para não estourar o timeout do Passenger (~120s).
> Espere 5–15 min para o Universal ficar completo.
>
> **Alternativa mais rápida**: faça o warm localmente (`./run_web.sh` + botão
> Aquecer), depois suba o `scanner_web.db` via FTP (passo 2b).

---

## Resumo (colar e adaptar)

```bash
cd /Users/andersonnascimento/projects/scanner_acoes
set -a; . ./.env; set +a

STAGE=$(mktemp -d) && mkdir -p "$STAGE/static" "$STAGE/tmp"
cp app.py passenger_wsgi.py scanners_core.py warming.py indicators.py \
   data_layer.py symbol_store.py symbols_fallback.py "$STAGE/"
cp static/{app.js,index.html,style.css} "$STAGE/static/"
cp requirements-py39.txt .python-version .env "$STAGE/"
date > "$STAGE/tmp/restart.txt"

lftp -u "$FTP_USER","$FTP_PASS" "ftp://$FTP_HOST" <<EOF
set ftp:passive-mode on
mirror --reverse --only-newer --verbose --parallel=6 "$STAGE" /scanner
bye
EOF

curl -fsS https://paulista.dev/scanner/api/status | python3 -m json.tool
```

---

## Limpeza / inspeção remota (toolkit `~/scripts`)

| Tarefa | Comando |
|---|---|
| Uso de disco do `/scanner` | `~/scripts/ftp_du.sh /scanner` |
| Listar conteúdo de `/scanner` | `~/scripts/ftp_delete_dir.sh --list /scanner` |
| Deletar `__pycache__` remoto | `~/scripts/ftp_delete_dir.sh /scanner/__pycache__` |
| Download completo do servidor → `~/asura` | `~/scripts/ftp_mirror.sh` |

> Os scripts de **delete/list/du** rodam server-side via payload PHP (upload FTP
> → exec HTTP → self-delete) — instantâneos mesmo para árvores grandes. Detalhes
> em `~/scripts/CLAUDE.md`.

---

## Troubleshooting

- **500 / tela branca após deploy** — quase sempre `pip` (passo 2) ou `.env`
  faltando. Confirme que `/scanner/.env` tem `FTP_HOST`/`FTP_USER`/`FTP_PASS`
  preenchidos e que todas as deps de `requirements-py39.txt` estão no venv remoto.
- **Restart não pegou** — confirme que `/scanner/tmp/restart.txt` existe e teve o
  mtime atualizado neste deploy. Reenvie via curl do passo 5 se necessário.
- **Timeout no `/api/scan` (Universal)** — esperado no primeiro acesso frio.
  Dispare `/api/warm` (passo 7) e aguarde; as leituras seguintes só consultam o banco.
- **Mirror apagou o DB** — você usou `ftp_sync.sh` (4b, `--delete`). Dispare o
  warm novamente (passo 7) ou restaure via upload (passo 2b).
- **`421` / limite de conexões no lftp** — baixe o `--parallel` (ex.: `4`).

---

## Notas de segurança

- Este doc **não contém credenciais** — os comandos leem `FTP_HOST`/`FTP_USER`/
  `FTP_PASS` do [`.env`](.env) (gitignored).
- Já o toolkit `~/scripts/ftp_*.sh` ainda embute host/usuário/senha no topo de
  cada arquivo; em máquina compartilhada, `chmod 700` esses scripts.
- `.env` guarda a senha FTP — nunca commitar (`.gitignore` já cobre `.env`).
  O template [`.env.example`](.env.example) é versionável e leva só placeholders.
- Os scripts de delete publicam brevemente um PHP (nome aleatório + secret único)
  no docroot — só rode em host próprio e confirme `DOCROOT`/`WEB_URL` em
  `~/scripts/ftp_common.sh`.
