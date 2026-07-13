# Scanner de Ações B3 — Branch `vanilla-web-scanner`

Porte **full-parity** do scanner para **HTML/JS vanilla + Flask/WSGI**, deployável em
**Phusion Passenger (DirectAdmin)** com **Python 3.9**. O branch `master` continua sendo
a fonte de verdade Streamlit/3.13 — este branch **nunca deve ser mergeado ao master**.

## Stack

- **Backend:** Flask + `passenger_wsgi.py` (entry point do Passenger)
- **Frontend:** HTML/JS/CSS vanilla puro — sem build, sem framework
- **Python:** 3.9 (compatível com o servidor remoto 3.9.19)
- **Indicadores:** Reimplementados em pandas puro (`indicators.py`) — sem `pandas_ta`/`numba`
- **Dados:** `yfinance` → SQLite (`scanner.db`) via `data_layer.py`
- **Símbolos:** Fallback local e estático via `symbols_fallback.py` / `symbol_store.py` (Supabase removido)

## Desenvolvimento local

```bash
# 1. Criar virtualenv 3.9 (uma vez só)
python3.9 -m venv venv39
venv39/bin/pip install -r requirements-py39.txt

# 2. Copiar .env com as credenciais
cp .env.example .env   # preencher SUPABASE_URL e SUPABASE_ANON_KEY

# 3. Rodar
./run_web.sh
# ou diretamente:
venv39/bin/python app.py   # sobe em http://localhost:5001
```

O primeiro acesso dispara o warming em background (`warming.py`). Em **dev** (processo
Flask persistente) ele completa e o progresso aparece na barra de status. Em **produção**
o warming é por **cron** — a thread do `warming.py` morre no Passenger (ver seção Deploy).

## Variáveis de ambiente

| Variável | Descrição | Padrão |
|---|---|---|
| `SUPABASE_URL` | URL do projeto Supabase | — |
| `SUPABASE_ANON_KEY` | Chave anon do Supabase | — |
| `SCANNER_DB` | Caminho do SQLite | `scanner.db` (junto ao script) |
| `PORT` | Porta do servidor local | `5001` |

## Deploy no DirectAdmin / Phusion Passenger

### 1. Upload dos arquivos

Envie o conteúdo do branch para o app root do servidor (ex: `/home/paulista/scanner`).
Exclua:

```
venv*/
__pycache__/
*.db  *.db-shm  *.db-wal
.git/
tools/
```

### 2. Configurar o Python App no DirectAdmin

- **Application root:** `scanner`
- **Application URL:** `paulista.dev/scanner`
- **Application startup file:** `passenger_wsgi.py`
- **Application Entry point:** `application`
- **Python version:** `3.9`

### 3. Instalar dependências

```bash
source /home/paulista/virtualenv/scanner/3.9/bin/activate
pip install -r requirements-py39.txt
```

### 4. Variáveis de ambiente

Configure via painel DirectAdmin **ou** crie `.env` na raiz da aplicação:

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SCANNER_DB=/home/paulista/scanner.db
```

### 5. Reiniciar e verificar

Reinicie a aplicação no painel e acesse `https://paulista.dev/scanner`.

**Atenção — warming em produção é via cron, não pelo frontend.** O `POST /api/warm`
(disparado pelo frontend na primeira visita) roda numa thread daemon que **morre no
Passenger**: o processo é reciclado logo após a request, a thread recebe `ReadTimeout`
no egress e o `scanner.db` fica vazio (`bars=0`). Por isso, em produção, agende
`warm_cron.py` no cron do DirectAdmin — processo autônomo que chama
`data_layer.prewarm()` direto no `scanner.db` compartilhado (`warm_cron.py` tem lock
`fcntl`, não precisa de `flock` no shell):

```
*/10 10-17 * * 1-5  cd /home/paulista/scanner && \
    /home/paulista/virtualenv/scanner/3.9/bin/python warm_cron.py \
    >> /home/paulista/scanner/tmp/warm_cron.log 2>&1
```

Logo após o deploy/restart, rode `warm_cron.py` uma vez manualmente para bootstrap.
Acompanhe pelo log (`tmp/warm_cron.log`) e pelo painel `/api/failures`.

## Scanners disponíveis

| Scanner | Perfil? | Intervalos usados |
|---|---|---|
| Legacy Profissional | não | 1d, 1h, 30m |
| Legacy Intraday Swing | não | 1d, 1h, 30m |
| Legacy Expandida | não | 1d, 1h, 30m |
| Swing Híbrido | sim | 1d, 1h, 30m |
| Swing Risk/Reward | sim | 1d, 1h, 30m |
| Swing Profissional | sim | 1d, 1h, 30m |
| Swing Expandido | sim | 1d, 1h, 30m |
| Trade Fusion | sim | 1d, 1h, 30m |
| Abertura — Candidatos 15m | não | 15m |
| Abertura — Confluência 15m/30m | não | 15m, 30m |

## Paridade de indicadores

```bash
# Computar referência (pandas_ta, venv313)
venv313/bin/python tools/check_indicators.py ref tools/_ref.json

# Computar com indicators.py (venv39)
venv39/bin/python tools/check_indicators.py new tools/_new.json

# Comparar (deve imprimir PASS ✅)
venv39/bin/python tools/check_indicators.py compare tools/_ref.json tools/_new.json
```

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/scanners` | Lista os scanners disponíveis |
| GET | `/api/scan?scanner=&adx_min=&rsi_min=&rsi_max=&vol_ratio_min=&vol_medio_min=` | Executa um scanner |
| GET | `/api/status` | Status do warming + resumo do banco |
| POST | `/api/warm` | Inicia warming em background — **só funciona em dev** (no Passenger a thread morre; em produção use `warm_cron.py` via cron) |
| POST | `/api/refresh` | Invalida o fill state (força re-fetch na próxima execução) |
| GET | `/api/fill_state` | Estado de preenchimento por símbolo/intervalo |
| GET | `/api/failures` | Símbolos que falharam no última warm |
| GET | `/api/bars?symbol=&interval=` | Últimas 50 barras de um símbolo (painel BD) |
