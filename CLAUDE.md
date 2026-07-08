# CLAUDE.md

Guidance for Claude Code working in this repository.

## Environment

- **Python 3.13** (pinned in `.python-version`). Use the `venv313/` virtualenv:
  `venv313/bin/python`, `venv313/bin/streamlit`, etc.
- Do **not** assume Python 3.9 or a Flask/WSGI server — that was an abandoned approach
  and is no longer accurate. The app is **Streamlit**, running on 3.13, on the `master`
  branch (the only branch).
- `pandas_ta` **is** installed and is used by the scanners
  (e.g. `import pandas_ta as ta` in `scanner_interface_Streamlit.py`).

## What this is

A Streamlit scanner for B3 (Brazilian) equities. It screens ~300+ tickers (stocks,
BDRs, ETFs, FIIs) across four timeframes (1d, 1h, 30m, 15m) using momentum/trend/volume
filters, producing candidates for manual or downstream-AI analysis. Market data comes
from `yfinance` (tickers use the `.SA` suffix). See `DELISTED_SYMBOLS.md` for tickers
removed from Yahoo.

## Running

```
venv313/bin/streamlit run scanner_interface_Streamlit.py   # 8 scanners (Legacy + Evolved)
venv313/bin/streamlit run scanner_abertura.py               # 15m opening scanner
venv313/bin/streamlit run painel_bd.py                      # read-only DB browser (bars/fill_state/fetch_failures)
```

`scanner_interface_Streamlit.py` has 8 scanners (Legacy + Evolved), each triggered from
the UI; `scanner_abertura.py` auto-runs its 15m scan on render; `painel_bd.py` is a
**read-only** browser over `scanner.db` (no fetches, no writes).

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
