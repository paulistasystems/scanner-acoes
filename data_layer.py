# -*- coding: utf-8 -*-
"""
data_layer.py — Camada de acesso a dados (SQLite) para os scanners.

Fonte única de verdade: o banco. A API do yfinance só é usada para PREENCHER
dados ausentes. A decisão de buscar é "o dado já está preenchido?" — e não
"houve falha na última tentativa". Assim, uma vez preenchido para o pregão
corrente, o scanner lê do banco de forma determinística e não refaz centenas
de chamadas ao Yahoo a cada scan → elimina a oscilação (asset some/aparece)
causada por throttling/respostas truncadas.

Framework-agnostic: depende apenas de sqlite3, pandas, yfinance e zoneinfo
(sem streamlit, sem pandas_ta) — portável para o deploy Flask / Python 3.9.

Local do banco: ao lado deste script (scanner.db) por padrão; override via
variável de ambiente SCANNER_DB. No Streamlit Cloud (filesystem efêmero), aponte
SCANNER_DB para um caminho gravável fora do repo (ex.: /tmp/scanner.db) — dentro
de uma sessão a persistência elimina a oscilação; em cada redeploy o container é
recriado do zero e o banco volta vazio (re-fetch completo, igual ao primeiro scan
de hoje).

Modelo de dados: uma única tabela `bars` serve todos os scanners (Legacy,
Evolved e Abertura), pois todos consomem os mesmos candles OHLCV nos mesmos
intervalos (1d, 1h, 30m, 15m). A profundidade (period) varia por scanner e é
resolvida armazenando a profundidade máxima por intervalo e fatiando na leitura.
"""

import os
import time
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
    ZoneInfo = None

# ----------------------------- Config -----------------------------
_DB_PATH = os.environ.get(
    "SCANNER_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanner.db"),
)
# B3 está em UTC-3 fixo (DST abolido em 2019) → sem complicação de horário de verão.
B3_TZ = ZoneInfo("America/Sao_Paulo") if ZoneInfo else timezone(timedelta(hours=-3))

# Profundidade máxima a armazenar por intervalo (cobre todos os scanners):
#   1d: sempre 1y | 1h: 60d ou 75d | 30m: 15d/30d/45d | 15m: 5d
MAX_PERIOD = {"1d": "1y", "1h": "75d", "30m": "45d", "15m": "5d"}

# Janela de pregão da B3 (aproximada; sem calendário de feriados).
_SESSION_START_HOUR = 10   # 10:00
_SESSION_END_HOUR = 18     # 18:00

# Fatiamento na leitura (em dias corridos), equivalente ao `period` do yfinance.
_PERIOD_DAYS = {"1y": 365, "75d": 75, "60d": 60, "45d": 45, "30d": 30, "15d": 15, "5d": 5}

_INTERVAL_MIN = {"1h": 60, "30m": 30, "15m": 15}

_conn = None
_lock = threading.Lock()
_schema_ready = False


# ----------------------------- DB -----------------------------
def _connect():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL;")
        _conn.execute("PRAGMA busy_timeout=5000;")
    return _conn


def _ensure_schema():
    global _schema_ready
    if _schema_ready:
        return
    with _lock:
        if _schema_ready:
            return
        conn = _connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bars (
                symbol   TEXT NOT NULL,
                interval TEXT NOT NULL,
                ts       TEXT NOT NULL,   -- ISO8601 (abertura do candle, hora B3)
                open   REAL,
                high   REAL,
                low    REAL,
                close  REAL,
                volume REAL,
                PRIMARY KEY (symbol, interval, ts)
            );
            CREATE INDEX IF NOT EXISTS idx_bars_sym_int_ts ON bars(symbol, interval, ts);

            CREATE TABLE IF NOT EXISTS fill_state (
                symbol         TEXT NOT NULL,
                interval       TEXT NOT NULL,
                last_filled_at TEXT,
                PRIMARY KEY (symbol, interval)
            );

            CREATE TABLE IF NOT EXISTS fetch_failures (
                symbol          TEXT NOT NULL,
                interval        TEXT NOT NULL,
                attempts        INTEGER,
                last_error      TEXT,
                fail_count      INTEGER DEFAULT 1,
                last_attempt_at TEXT,
                PRIMARY KEY (symbol, interval)
            );
            """
        )
        conn.commit()
        _schema_ready = True


# ----------------------------- B3 freshness -----------------------------
def _now_brt():
    return datetime.now(B3_TZ)


def _session_open(now):
    """Pregão aberto? Seg-sex, 10:00–18:00 (feriados não considerados)."""
    if now.weekday() >= 5:  # sábado/domingo
        return False
    return _SESSION_START_HOUR <= now.hour < _SESSION_END_HOUR


def _last_trading_day(now):
    """Dia de pregão mais recente (date), ignorando feriados."""
    d = now.date()
    # Antes da abertura num dia útil → o pregão relevante é o anterior.
    if d.weekday() < 5 and now.hour < _SESSION_START_HOUR:
        d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def session_today(now=None):
    """Data (date, fuso B3) do pregão de HOJE se hoje for dia útil (seg–sex),
    ou None em fim de semana. Feriados não são rastreados (cf. CLAUDE.md).

    Diferente de `_last_trading_day`, NÃO recua para o pregão anterior: serve para
    travar análises estritamente no dia corrente — ex.: o scanner de abertura só
    deve avaliar a sessão de hoje, nunca a de ontem como fallback."""
    if now is None:
        now = _now_brt()
    if now.weekday() >= 5:
        return None
    return now.date()


def _floor_to_grid(dt, minutes):
    """Arredonda para baixo até o grid de `minutes` alinhado à meia-noite."""
    total = dt.hour * 60 + dt.minute
    floored = (total // minutes) * minutes
    return dt.replace(hour=floored // 60, minute=floored % 60, second=0, microsecond=0)


def _expected_last_completed_bar_ts(interval, now):
    """ISO8601 do candle mais recente que já deveria estar FECHADO agora."""
    if interval == "1d":
        day = _last_trading_day(now)
        return datetime(day.year, day.month, day.day, tzinfo=B3_TZ).isoformat()

    minutes = _INTERVAL_MIN[interval]
    if _session_open(now):
        # Último candle fechado = floor(now - 1 intervalo), clamp >= 10:00.
        cand = _floor_to_grid(now - timedelta(minutes=minutes), minutes)
        session_start = cand.replace(hour=_SESSION_START_HOUR, minute=0, second=0, microsecond=0)
        if cand < session_start:
            cand = session_start
        return cand.isoformat()

    # Pregão fechado: último candle do dia de pregão mais recente.
    day = _last_trading_day(now)
    last_open = _floor_to_grid(
        datetime(day.year, day.month, day.day, 17, 55, tzinfo=B3_TZ), minutes
    )
    return last_open.isoformat()


def _max_ts(symbol, interval):
    with _lock:
        row = _connect().execute(
            "SELECT MAX(ts) FROM bars WHERE symbol=? AND interval=?", (symbol, interval)
        ).fetchone()
    return row[0] if row else None


def _has_fill_state(symbol, interval):
    with _lock:
        row = _connect().execute(
            "SELECT 1 FROM fill_state WHERE symbol=? AND interval=?", (symbol, interval)
        ).fetchone()
    return row is not None


def _is_filled(symbol, interval, now):
    """Portão "está preenchido?". DB primeiro; yfinance só se não preenchido."""
    if not _has_fill_state(symbol, interval):
        return False
    max_ts = _max_ts(symbol, interval)
    if not max_ts:
        return False
    expected = _expected_last_completed_bar_ts(interval, now)
    if interval == "1d" or not _session_open(now):
        # Fora de pregão / diário: basta ter candles do último pregão (robusto a
        # pequenas diferenças no horário exato do último candle retornado).
        return max_ts[:10] >= expected[:10]
    # Intraday em pregão: avanço candle a candle (compara timestamp exato).
    return max_ts >= expected


def _set_fill_state(symbol, interval):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO fill_state(symbol, interval, last_filled_at) VALUES (?,?,?)",
            (symbol, interval, _now_brt().isoformat()),
        )
        conn.commit()


def _record_failure(symbol, interval, attempts, err):
    """Registra/incrementa uma falha de aquisição (base p/ blacklist e diagnóstico)."""
    with _lock:
        conn = _connect()
        conn.execute(
            """INSERT INTO fetch_failures(symbol, interval, attempts, last_error, fail_count, last_attempt_at)
               VALUES (?,?,?,?,1,?)
               ON CONFLICT(symbol, interval) DO UPDATE SET
                 attempts=excluded.attempts,
                 last_error=excluded.last_error,
                 fail_count=fetch_failures.fail_count+1,
                 last_attempt_at=excluded.last_attempt_at""",
            (symbol, interval, attempts, str(err)[:500], _now_brt().isoformat()),
        )
        conn.commit()


def _clear_failure(symbol, interval):
    """Símbolo voltou a preencher — limpa o histórico de falhas dele."""
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM fetch_failures WHERE symbol=? AND interval=?", (symbol, interval))
        conn.commit()


def invalidate():
    """Força a próxima leitura a rebuscar no yfinance (refresh manual).
    Limpa o fill_state; os candles em `bars` são atualizados via upsert no refill."""
    _ensure_schema()
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM fill_state")
        conn.commit()


# ----------------------------- Yahoo (fill) -----------------------------
def _fetch_from_yahoo(symbol, interval, period, attempts=3):
    """Baixa do yfinance com tratamento de MultiIndex e retry curto.
    Retorna (df, erro): df vazio + mensagem se todas as tentativas falharem."""
    delays = [0.5, 1.5]
    last_err = "empty/truncated response"
    for attempt in range(attempts):
        try:
            df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df = df.droplevel(1, axis=1)
            if df is not None and not df.empty:
                return df, None
        except Exception as e:
            last_err = repr(e)
        if attempt < attempts - 1:
            time.sleep(delays[min(attempt, len(delays) - 1)])
    return pd.DataFrame(), last_err


def _upsert_bars(symbol, interval, df):
    cols = ["Open", "High", "Low", "Close", "Volume"]
    if any(c not in df.columns for c in cols):
        return
    rows = []
    for ts, vals in zip(df.index, df[cols].itertuples(index=False, name=None)):
        o, h, l, c, v = vals
        rows.append((
            symbol, interval, ts.isoformat(),
            None if pd.isna(o) else float(o),
            None if pd.isna(h) else float(h),
            None if pd.isna(l) else float(l),
            None if pd.isna(c) else float(c),
            None if pd.isna(v) else float(v),
        ))
    if not rows:
        return
    with _lock:
        conn = _connect()
        conn.executemany(
            "INSERT OR REPLACE INTO bars(symbol, interval, ts, open, high, low, close, volume) "
            "VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()


def _read_bars(symbol, interval):
    with _lock:
        rows = _connect().execute(
            "SELECT ts, open, high, low, close, volume FROM bars "
            "WHERE symbol=? AND interval=? ORDER BY ts",
            (symbol, interval),
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"])
    df["ts"] = pd.to_datetime(df["ts"])  # diário tz-naive; intradiário tz-aware
    df = df.set_index("ts")
    df.index.name = None
    return df


# ----------------------------- API pública -----------------------------
def get_bars(symbol, interval, period):
    """Devolve candles OHLCV de (symbol, interval) fatiados por `period`.

    DB-first / fill-if-missing: só aciona o yfinance quando os dados do pregão
    corrente não estão preenchidos no banco. Em caso de falha pontual do fetch,
    devolve o que já existe no banco (degradação graciosa) em vez de dropar o
    ativo — ataca diretamente o falso-negativo que sumia ativos bons."""
    _ensure_schema()
    now = _now_brt()

    if not _is_filled(symbol, interval, now):
        df, _err = _fetch_from_yahoo(symbol, interval, MAX_PERIOD.get(interval, period))
        if df is not None and not df.empty:
            _upsert_bars(symbol, interval, df)
            _set_fill_state(symbol, interval)

    df = _read_bars(symbol, interval)
    if df is None or df.empty:
        return pd.DataFrame()

    days = _PERIOD_DAYS.get(period)
    if days:
        cutoff = now - timedelta(days=days)
        # yfinance entrega o índice diário tz-naive (meia-noite) e o intradiário
        # tz-aware; `now` é sempre tz-aware. Alinha o cutoff à awareness do índice
        # para a comparação funcionar nos dois casos (sem deslocar timestamps).
        if df.index.tz is None:
            cutoff = cutoff.replace(tzinfo=None)
        df = df[df.index >= cutoff]
    return df


# ----------------------------- Aquisição (prewarm) + log de falhas -----------------------------
def list_failures():
    """DataFrame com (symbol, interval) que falharam ao preencher, ordenado por
    frequência — base para blacklist e diagnóstico por ativo."""
    _ensure_schema()
    with _lock:
        rows = _connect().execute(
            "SELECT symbol, interval, fail_count, attempts, last_error, last_attempt_at "
            "FROM fetch_failures ORDER BY fail_count DESC, last_attempt_at DESC"
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(
        rows,
        columns=["symbol", "interval", "fail_count", "attempts", "last_error", "last_attempt_at"],
    )


def prewarm(symbols, intervals, attempts=3, progress=None):
    """Passo de AQUISIÇÃO: garante que todos os (symbol, interval) estejam
    preenchidos no banco ANTES da análise. Faz retry com backoff e registra em
    fetch_failures os que continuam falhando (retorna a lista deles).

    Deve ser chamado no início de cada scanner, antes do loop de análise — assim
    todo o download acontece antes de qualquer análise e os ativos que não
    puderam ser preenchidos ficam registrados (e são naturalmente pulados pelas
    checagens de comprimento do scanner).

    `progress(done, total, symbol, ok)` é um callback opcional para UI
    (framework-agnostic: data_layer não importa streamlit)."""
    _ensure_schema()
    now = _now_brt()
    failures = []
    items = [(s, i) for s in symbols for i in intervals]
    total = len(items)
    for idx, (symbol, interval) in enumerate(items):
        ok = True
        if not _is_filled(symbol, interval, now):
            df, err = _fetch_from_yahoo(symbol, interval, MAX_PERIOD.get(interval, "1y"), attempts)
            if df is not None and not df.empty:
                _upsert_bars(symbol, interval, df)
                _set_fill_state(symbol, interval)
                _clear_failure(symbol, interval)
            else:
                _record_failure(symbol, interval, attempts, err)
                failures.append((symbol, interval))
                ok = False
        if progress is not None:
            progress(idx + 1, total, symbol, ok)
    return failures
