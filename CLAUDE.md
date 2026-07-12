# CLAUDE.md

Guidance for Claude Code working in this repository.

## Arquitetura (`master` — app web Flask/WSGI)

O `master` é o scanner em **HTML/JS vanilla + backend Flask/WSGI**, para deploy em
**Phusion Passenger (DirectAdmin)** em `paulista.dev/scanner`, que roda **Python 3.9.19**
(virtualenv `/home/paulista/virtualenv/scanner/3.9/`, app root
`/home/paulista/scanner`). A interface Streamlit (Python 3.13 / `pandas_ta`) é legado
dormente: os arquivos `scanner_interface_Streamlit.py`, `scanner_abertura.py`,
`painel_bd.py` permanecem no repo mas **não rodam em 3.9** e não são usados pelo app web;
a linhagem Streamlit viva sobrevive no branch `streamlit-legacy` / `origin/master`.

- **Python 3.9** (pinned em `.python-version` = `3.9`). Use o `venv39/` virtualenv:
  `venv39/bin/python`, `venv39/bin/python app.py`. Deps em `requirements-py39.txt`
  (Flask, yfinance, pandas, supabase, python-dotenv — **sem pandas_ta/numba/streamlit**).
- **Sem `pandas_ta`** (não instala em 3.9). Os indicadores são reimplementados em pandas
  puro em [`indicators.py`](indicators.py) (EMA, RSI, ATR, ADX/DI, MACD — suavização de
  Wilder via RMA = `ewm(alpha=1/length, min_periods=length, adjust=False)`, mesma
  convenção do pandas_ta; paridade validada por `tools/check_indicators.py`).
- **Backend Flask** ([`app.py`](app.py)) serve `static/index.html` + uma API JSON
  (`/api/scanners`, `/api/scan`, `/api/status`, `/api/warm`, `/api/refresh`,
  `/api/bars`, `/api/fill_state`, `/api/failures`, `/api/symbols`). Entrada Passenger em
  [`passenger_wsgi.py`](passenger_wsgi.py) (`application = app`).
- **`scanners_core.py`**: lógica dos 8 scanners + Abertura extraída dos arquivos
  Streamlit, **sem** acoplamento a streamlit/pandas_ta (usa `indicators` + `data_layer`).
- **`warming.py`**: worker em background que roda `data_layer.prewarm()` (fetches lentos
  do Yahoo). Cada request HTTP só **lê o banco** (rápido, <2s) e reporta progresso; o
  frontend faz poll. Isso evita timeout do Passenger (Universal = 220+ ativos ×
  intervalos = 5–15 min, bem acima do limite de ~120s por request).
- **Frontend vanilla** (`static/index.html`, `static/app.js`, `static/style.css`): sem
  build, sem framework — `fetch` + render de tabelas genérico. Montado em subpath
  `/scanner`: URLs derivadas de `window.location.pathname` (mount-agnostic).
- **Módulos framework-agnostic**: [`data_layer.py`](data_layer.py),
  [`symbol_store.py`](symbol_store.py), [`symbols_fallback.py`](symbols_fallback.py)
  — compartilhados com o legado Streamlit, portáveis a 3.9.
- Deploy: ver [`passenger_README.md`](passenger_README.md). Local: `./run_web.sh` ou
  `venv39/bin/python app.py`.

## What this is

A scanner for B3 (Brazilian) equities. The active app on `master` is the **Flask/WSGI
web scanner** (vanilla JS frontend); a **Streamlit** UI exists as dormant legacy (see
`streamlit-legacy`). It screens ~300+ tickers (stocks, BDRs, ETFs, FIIs) across four
timeframes (1d, 1h, 30m, 15m) using momentum/trend/volume filters, producing candidates
for manual or downstream-AI analysis. Market data comes from `yfinance` (tickers use the
`.SA` suffix). See `DELISTED_SYMBOLS.md` for tickers removed from Yahoo.

## Running

Web app (`master`, Python 3.9):

```
./run_web.sh                  # ou: venv39/bin/python app.py
```

Legacy Streamlit (branch `streamlit-legacy`, Python 3.13 — `pandas_ta` required):

```
venv313/bin/streamlit run scanner_interface_Streamlit.py   # 8 scanners (Legacy + Evolved)
venv313/bin/streamlit run scanner_abertura.py               # 15m opening scanner
```

`scanner_interface_Streamlit.py` has 8 scanners (Legacy + Evolved), each triggered from
the UI; `scanner_abertura.py` auto-runs its 15m scan on render. Both scanner apps embed
a **read-only** DB panel (`painel_bd.render_db_panel()`) at the bottom — see below.

## Architecture: data layer (`data_layer.py`)

The SQLite database (`scanner.db`, gitignored) is the **single source of truth**.
`yfinance` is used only to **fill missing data** — the fetch decision is "is this
(symbol, interval) already filled?", never "did the last fetch fail?". Once filled for
the current session, scans read the DB deterministically and never re-hit Yahoo. This
eliminates the asset flicker (assets appearing/vanishing between runs minutes apart)
that throttled/truncated Yahoo responses used to cause.

- `data_layer.get_bars(symbol, interval, period)` — single read/fill entry point.
  `baixar_dados` / `baixar_dados_15m` delegate to it (signatures preserved).
- `data_layer.prewarm(symbols, intervals)` — acquisition pass (retry + failure log)
  run before each scanner's analysis loop, so all data is downloaded **before** analysis.
- `data_layer.list_failures()` — symbols that failed to fill (blacklist candidates),
  shown in the app's failures panel.
- `data_layer.invalidate()` — clears fill state; the refresh buttons call it.
- `data_layer.db_summary()` / `read_bars()` / `read_fill_state()` — **read-only**
  introspection helpers used by `painel_bd.py`; they never fetch or write.
- **DB panel** (`painel_bd.render_db_panel()`): a read-only browser over `scanner.db`
  (bars/fill_state/fetch_failures). It is **embedded at the bottom of both scanner
  apps**, not deployed as a separate app — on Streamlit Cloud each app runs in its own
  ephemeral container/filesystem, so a standalone panel app would see an empty DB.
  `painel_bd.py` is a library module imported by both apps (not a standalone app).
- All scanners share one `bars` table across 1d/1h/30m/15m; lookback depth varies per
  scanner and is resolved by storing max depth and slicing on read.
- **DB location**: `scanner.db` next to the script by default; override via the
  `SCANNER_DB` env var. On Streamlit Cloud (ephemeral filesystem), point it at a
  writable path (e.g. `/tmp/scanner.db`); persistence is within-session — a redeploy
  re-fetches.
- B3 is UTC-3 (no DST); the data layer is market-state-aware (B3 session 10:00–18:00,
  weekdays) for freshness.

## Conventions

- User-facing text and code comments are in Portuguese (pt-BR).
- When editing scanners, preserve `baixar_dados` / `baixar_dados_15m` signatures —
  they have ~22 call sites that must stay unchanged.
