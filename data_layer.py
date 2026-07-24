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
from urllib.parse import quote

import pandas as pd
import requests
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

            -- Estado do warm em disco (nao em memoria): o Phusion Passenger roda varios
            -- processos; assim todos enxergam o mesmo running/done/total e o frontend
            -- pode esperar o aquecimento de forma confiavel. heartbeat_at permite
            -- detectar um worker morto (processo reciclado) e retomar.
            CREATE TABLE IF NOT EXISTS warm_state (
                id            INTEGER PRIMARY KEY CHECK (id = 1),
                running       INTEGER NOT NULL DEFAULT 0,
                done          INTEGER NOT NULL DEFAULT 0,
                total         INTEGER NOT NULL DEFAULT 0,
                last_symbol   TEXT    NOT NULL DEFAULT '',
                started_at    TEXT,
                finished_at   TEXT,
                heartbeat_at  TEXT
            );
            INSERT OR IGNORE INTO warm_state (id, running) VALUES (1, 0);

            -- Cache bruto do Yahoo Chart API, gravado pelo proxy PHP (write-through):
            -- yahoo_chart.php UPSERT aqui o JSON cru a cada fetch. O Python só LÊ
            -- (data_layer._fetch_chart_direct, cache-first) e faz a normalização —
            -- assim o PHP é quem "atualiza o banco direto", sem portar a normalização
            -- (auto-adjust/tz/índice) para o PHP. Sem risco de divergência dos indicadores.
            CREATE TABLE IF NOT EXISTS chart_cache (
                symbol     TEXT NOT NULL,
                interval   TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                payload    TEXT NOT NULL,   -- JSON cru do /v8/finance/chart
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
    """Registra/incrementa uma falha de aquisição (base p/ diagnóstico)."""
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
    Limpa o fill_state e o chart_cache (write-through do PHP); os candles em `bars`
    são atualizados via upsert no refill."""
    _ensure_schema()
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM fill_state")
        conn.execute("DELETE FROM chart_cache")
        conn.commit()


# ----------------------------- Yahoo (fill) -----------------------------
# Chart API v8 — endpoint publico de candles. No servidor paulista.dev o bootstrap
# cookie/crumb do yfinance recebe 401 ("Invalid Crumb"), mas este endpoint responde
# 200+dados com um User-Agent de browser, sem precisar de cookie/crumb. Por isso eh o
# caminho primario; o yf.download (que depende do crumb) fica como fallback.
_CHART_ENDPOINT = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_CHART_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Yahoo so aceita tokens de range fixos (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max) —
# "75d"/"45d" NAO sao aceitos. Mapeia o period pedido a um token valido e generoso;
# o excedente eh fatiado na leitura por _PERIOD_DAYS (profundidade maxima por intervalo).
_CHART_RANGE = {
    "1y": "1y", "2y": "2y",
    "75d": "6mo", "60d": "3mo", "45d": "3mo", "30d": "1mo", "15d": "5d", "5d": "5d",
}
# 30m/15m: Yahoo limita intradiário a <=60 dias; "3mo" (90d) => HTTP 422. "1mo" é seguro.
_INTERVAL_DEFAULT_RANGE = {"1d": "1y", "1h": "6mo", "30m": "1mo", "15m": "5d"}


def _read_chart_cache(symbol, interval):
    """Lê o payload cru do Yahoo gravado pelo proxy PHP (write-through em chart_cache).
    Retorna o dict (JSON parsed) ou None. Quem ESCREVE o cache é o PHP
    (yahoo_chart.php); o Python só lê."""
    _ensure_schema()
    with _lock:
        row = _connect().execute(
            "SELECT payload FROM chart_cache WHERE symbol=? AND interval=?",
            (symbol, interval),
        ).fetchone()
    if not row:
        return None
    try:
        import json
        return json.loads(row[0])
    except Exception:
        return None


def _parse_chart_payload(payload, symbol, interval):
    """Normaliza o JSON cru do /v8/finance/chart em DataFrame (Open/High/Low/Close/
    Volume) com convenção de tz idêntica ao yfinance (diário = índice tz-naive
    meia-noite; intradiário = tz-aware UTC). OHL reescalado pelo ratio
    adjclose/close (paridade com yf.download(auto_adjust=True)). Compartilhado entre
    o caminho live (proxy/Yahoo) e o cache (chart_cache gravado pelo PHP)."""
    chart = payload.get("chart") or {}
    results = chart.get("result")
    if not results:
        err = chart.get("error") or {}
        return pd.DataFrame(), f"chart no result: {err.get('description', 'unknown')}"
    r0 = results[0]
    ts = r0.get("timestamp") or []
    if not ts:
        return pd.DataFrame(), "chart empty timestamp"

    indicators = r0.get("indicators") or {}
    quote_obj = (indicators.get("quote") or [{}])[0]
    adjclose = ((indicators.get("adjclose") or [{}])[0]).get("adjclose")
    n = len(ts)

    # DatetimeIndex: diario tz-naive meia-noite (Yahoo entrega o epoch diario em 13:00 UTC
    # = abertura B3; normalizamos para 00:00 como o yfinance), intradiario tz-aware UTC.
    idx = pd.to_datetime(ts, unit="s", utc=True)
    if interval == "1d":
        idx = idx.normalize().tz_localize(None)

    def col(name):
        v = quote_obj.get(name)
        return v if v is not None else [None] * n

    df = pd.DataFrame(
        {"Open": col("open"), "High": col("high"), "Low": col("low"),
         "Close": col("close"), "Volume": col("volume")},
        index=idx,
    )
    df.index.name = None

    # auto_adjust: reescala OHL pelo ratio adjclose/close (paridade com yf.download).
    close = df["Close"]
    if adjclose is not None and len(adjclose) == n:
        adj = pd.Series(adjclose, index=df.index)
        ratio = adj.divide(close.replace(0, pd.NA))
        ratio = ratio.where(ratio.notna() & (ratio > 0), 1.0)
        for c in ("Open", "High", "Low"):
            df[c] = df[c] * ratio
        df["Close"] = adj

    df = df.dropna(how="all")
    if df.empty:
        return pd.DataFrame(), "chart all-nan"
    return df, None


def _fetch_chart_direct(symbol, interval, period, use_cache=True):
    """Baixa candles direto do Yahoo Chart API v8 (sem cookie/crumb).

    Retorna (df, erro): df com colunas Open/High/Low/Close/Volume e convencao de tz
    identica ao yfinance (diario = index tz-naive meia-noite; intradiario = index
    tz-aware UTC), para manter `_is_filled`/leitura compativeis com os dados ja no banco.
    OHL eh reescalado pelo ratio adjclose/close para paridade com `yf.download(auto_adjust=True)`."""
    # Cache-first: se use_cache e houver payload cru em chart_cache (gravado pelo
    # proxy PHP via write-through), normaliza a partir dele sem ir à rede. O passo de
    # aquisição (prewarm) passa use_cache=False para forçar refresh; a leitura sob
    # demanda usa o cache.
    if use_cache:
        cached = _read_chart_cache(symbol, interval)
        if cached is not None:
            dfc, _ = _parse_chart_payload(cached, symbol, interval)
            if dfc is not None and not dfc.empty:
                return dfc, None
        # cache ausente/ilegível -> cai para o fetch normal (refresca o cache via PHP)
    # period1/period2 (epocas) dao a janela exata em dias e respeitam o limite por
    # intervalo (1d=365, 1h=75<=730, 30m=45<=60, 15m=5<=60). range-token so cai como
    # fallback se o period nao for conhecido.
    days = _PERIOD_DAYS.get(period)
    if days:
        now = int(time.time())
        params = {"period1": now - days * 86400, "period2": now, "interval": interval}
    else:
        params = {"range": _INTERVAL_DEFAULT_RANGE.get(interval, "1mo"), "interval": interval}

    # Egress: por padrao, Yahoo direto. Se SCANNER_CHART_URL apontar para o proxy
    # PHP (php/yahoo_chart.php), a chamada passa por ele — mesmo recurso em local e
    # remoto, contornando o crumb 401 do yfinance no IP do servidor. O proxy
    # repassa symbol + (period1/period2|range) e devolve o corpo cru do Yahoo.
    egress = os.environ.get("SCANNER_CHART_URL", "").strip()
    if egress:
        url = egress
        params = dict(params, symbol=symbol)
        timeout = 25  # proxy PHP -> Yahoo adiciona um salto
    else:
        url = _CHART_ENDPOINT.format(symbol=quote(symbol, safe=""))
        timeout = 15
    try:
        resp = requests.get(
            url, params=params, headers={"User-Agent": _CHART_UA}, timeout=timeout,
        )
    except Exception as e:
        return pd.DataFrame(), f"chart request exc: {e!r}"
    if resp.status_code != 200:
        return pd.DataFrame(), f"chart http {resp.status_code}"
    try:
        payload = resp.json()
    except Exception as e:
        return pd.DataFrame(), f"chart json exc: {e!r}"

    return _parse_chart_payload(payload, symbol, interval)


def _fetch_from_yahoo(symbol, interval, period, attempts=3, use_cache=True):
    """Baixa candles do Yahoo. Caminho primario = Chart API v8 (direto, ou via proxy
    PHP quando SCANNER_CHART_URL esta setada). Fallback = yf.download — mas SO quando
    o egress NAO e o proxy PHP: no servidor o crumb do yfinance recebe 401 e o
    fallback so perde ~30-60s por simbolo, travando o warm. Com egress PHP ativo,
    devolve vazio rapido (prewarm registra e segue) em vez de martelar yfinance.
    Retorna (df, erro): df vazio + mensagem se todos os caminhos falharem."""
    df, err = _fetch_chart_direct(symbol, interval, period, use_cache=use_cache)
    if df is not None and not df.empty:
        return df, None

    # Egress PHP ativo => yfinance quebrado neste IP (crumb 401): pula o fallback
    # lento e falha rapido. Localmente (sem SCANNER_CHART_URL) mantem o fallback.
    if os.environ.get("SCANNER_CHART_URL", "").strip():
        return pd.DataFrame(), f"{err or 'chart empty'} (egress php; yfinance skipped)"

    last_err = err or "empty/truncated response"
    delays = [0.5, 1.5]
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

    # Remove trailing bar(s) com Close ausente ou Volume zero — Yahoo às vezes
    # devolve uma barra vazia para o último dia antes de o dado ser finalizado.
    # Isso quebraria scanners que leem df.iloc[-1] (Close=NaN, Volume=0).
    if len(df) > 1:
        last_idx = df.index[-1]
        last_close = df['Close'].iloc[-1]
        last_vol = df['Volume'].iloc[-1]
        if pd.isna(last_close) or last_vol == 0:
            df = df.iloc[:-1]

    days = _PERIOD_DAYS.get(period)
    if days:
        # Âncora o cutoff no timestamp mais recente disponível no banco para este
        # (symbol, interval), e NÃO no relógio vivo do servidor (`now`). Isso torna
        # a janela determinística e idêntica entre o servidor local e o remoto,
        # que de outro modo fatiariam janelas de calendário diferentes conforme o
        # relógio de cada máquina avança (causa raiz dos resultados divergentes).
        anchor = _db_max_ts(df, now)
        cutoff = anchor - timedelta(days=days)
        # yfinance entrega o índice diário tz-naive (meia-noite) e o intradiário
        # tz-aware; alinha o cutoff à awareness do índice para a comparação
        # funcionar nos dois casos (sem deslocar timestamps).
        if df.index.tz is None:
            cutoff = cutoff.replace(tzinfo=None)
        df = df[df.index >= cutoff]
    return df


def _db_max_ts(df, now):
    """Maior timestamp presente no DataFrame, ou `now` se vazio.

    Preserva a awareness (tz) do índice original: se o índice for tz-naive,
    devolve um instantâneo naive de `now`; se for tz-aware, devolve `now` c/tz.
    """
    if df is None or df.empty:
        return now
    last = df.index.max()
    if last.tzinfo is None and now.tzinfo is not None:
        return now.replace(tzinfo=None)
    if last.tzinfo is not None and now.tzinfo is None:
        return now.replace(tzinfo=last.tzinfo)
    return now


# ----------------------------- Warm state (compartilhado entre processos) -----------------------------
# Janela para considerar um worker "vivo". Acima disso sem heartbeat, presumemos
# que o processo Passenger foi reciclado e o warm pode ser retomado por outro processo.
WARM_STALE_SECONDS = 90


def get_warm_state():
    """Snapshot do estado de aquecimento lido do banco (compartilhado entre processos
    Passenger). Se running=1 mas o heartbeat esta estagnado, trata como parado (worker
    morto) para que o frontend nao espere infinitamente e outro processo possa retomar."""
    _ensure_schema()
    with _lock:
        row = _connect().execute(
            "SELECT running, done, total, last_symbol, started_at, finished_at, heartbeat_at "
            "FROM warm_state WHERE id=1"
        ).fetchone()
    if not row:
        return {"running": False, "done": 0, "total": 0, "last_symbol": "",
                "started_at": None, "finished_at": None, "intervals": []}
    running, done, total, last_symbol, started_at, finished_at, heartbeat_at = row
    stale = False
    if running and heartbeat_at:
        try:
            hb = datetime.fromisoformat(heartbeat_at)
            if (_now_brt() - hb).total_seconds() > WARM_STALE_SECONDS:
                stale = True
        except Exception:
            stale = True
    return {
        "running": bool(running) and not stale,
        "done": done, "total": total, "last_symbol": last_symbol,
        "started_at": started_at, "finished_at": finished_at, "intervals": [],
    }


def claim_warm(total, started_at, heartbeat_cutoff):
    """Tenta adquirir atomicamente o lock de aquecimento. Sucede (rowcount=1) apenas se
    o estado esta livre (running=0) ou o worker anterior morreu (heartbeat estagnado).
    Comparacao por string ISO funciona porque todos os ts usam o mesmo formato/tz."""
    _ensure_schema()
    with _lock:
        cur = _connect().execute(
            "UPDATE warm_state SET running=1, done=0, total=?, last_symbol='', "
            "started_at=?, finished_at=NULL, heartbeat_at=? "
            "WHERE id=1 AND (running=0 OR heartbeat_at IS NULL OR heartbeat_at < ?)",
            (total, started_at, started_at, heartbeat_cutoff),
        )
        _connect().commit()
        return cur.rowcount == 1


def tick_warm(done, last_symbol):
    """Atualiza progresso + heartbeat a cada item processado pelo worker."""
    _ensure_schema()
    with _lock:
        conn = _connect()
        conn.execute(
            "UPDATE warm_state SET done=?, last_symbol=?, heartbeat_at=? WHERE id=1",
            (done, last_symbol, _now_brt().isoformat()),
        )
        conn.commit()


def release_warm(finished_at):
    """Marca o aquecimento como concluido (worker saiu, com sucesso ou erro)."""
    _ensure_schema()
    with _lock:
        conn = _connect()
        conn.execute("UPDATE warm_state SET running=0, finished_at=? WHERE id=1", (finished_at,))
        conn.commit()


# ----------------------------- Aquisição (prewarm) + log de falhas -----------------------------
def list_failures():
    """DataFrame com (symbol, interval) que falharam ao preencher, ordenado por
    frequência — base para diagnóstico por ativo."""
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


def db_path():
    """Caminho absoluto do banco em uso (respeita SCANNER_DB)."""
    return _DB_PATH


def db_summary():
    """Estatísticas agregadas do banco para o painel de inspeção: contagens por
    tabela, contagem de candles por intervalo, símbolos distintos e janela
    temporal (min/max ts). Tudo em uma única travada do lock."""
    _ensure_schema()
    conn = _connect()
    with _lock:
        out = {
            "bars": conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0],
            "fill_state": conn.execute("SELECT COUNT(*) FROM fill_state").fetchone()[0],
            "fetch_failures": conn.execute("SELECT COUNT(*) FROM fetch_failures").fetchone()[0],
            "distinct_symbols": conn.execute("SELECT COUNT(DISTINCT symbol) FROM bars").fetchone()[0],
            "by_interval": conn.execute(
                "SELECT interval, COUNT(*) FROM bars GROUP BY interval ORDER BY interval"
            ).fetchall(),
            "ts_min": None,
            "ts_max": None,
        }
        rng = conn.execute("SELECT MIN(ts), MAX(ts) FROM bars").fetchone()
        out["ts_min"], out["ts_max"] = rng[0], rng[1]
    return out



def retry_symbol(symbol):
    """Limpa falha e fill_state de um único símbolo para retentar."""
    _ensure_schema()
    sym = (symbol or "").strip().upper()
    if not sym:
        return False
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM fetch_failures WHERE symbol=?", (sym,))
        conn.execute("DELETE FROM fill_state WHERE symbol=?", (sym,))
        conn.commit()
    return True


def retry_failures():
    """Limpa o registro de falhas e invalida o fill_state para que todos os
    símbolos que falharam sejam retentados na próxima aquisição."""
    _ensure_schema()
    with _lock:
        conn = _connect()
        symbols = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM fetch_failures").fetchall()]
        conn.execute("DELETE FROM fetch_failures")
        for s in symbols:
            conn.execute("DELETE FROM fill_state WHERE symbol=?", (s,))
        conn.commit()
    return len(symbols)


# Intervalos exigidos pelos scanners web (inclui Abertura 15m).
REQUIRED_INTERVALS = ("1d", "1h", "30m", "15m")


def data_ready(symbols=None, intervals=None, sample_missing=8, exclude_failures=False):
    """Pronto para rodar scanners? Todos os (symbol, interval) exigidos em fill_state.

    Idempotente com prewarm: só conta o que já está marcado como filled.
    Falhas em fetch_failures contam como "missing" (não liberam o gate) — o warm
    pode retentar.

    Retorna dict serializável em JSON (usado por /api/status e /api/scan).
    """
    from symbols_fallback import ATIVOS_B3_AMPLIADO

    # Quando nenhum símbolo é passado, usa ATIVOS_B3_AMPLIADO, MAS FILTRA APENAS
    # para os símbolos que já constam na tabela `fill_state` caso a tabela não
    # esteja 100% vazia (modo dinâmico de exclusão de ativos defeituosos/persistentes).
    base_symbols = list(symbols if symbols is not None else ATIVOS_B3_AMPLIADO)
    intervals = list(intervals if intervals is not None else REQUIRED_INTERVALS)

    _ensure_schema()
    with _lock:
        conn = _connect()
        filled = conn.execute(
            "SELECT symbol, interval FROM fill_state"
        ).fetchall()
        fail_rows = conn.execute(
            "SELECT symbol, interval, fail_count, last_error FROM fetch_failures"
        ).fetchall()

    filled_set = {(r[0], r[1]) for r in filled}

    n_sym = len(base_symbols)

    if n_sym == 0:
         return {
             "ready": True,
             "symbols": 0,
             "intervals": intervals,
             "expected_pairs": 0,
             "filled_pairs": 0,
             "missing_pairs": 0,
             "coverage_pct": 100.0,
             "by_interval": [],
             "missing_sample": [],
             "message": "Nenhum ativo verificado"
         }

    expected_total = n_sym * len(intervals)
    have_total = len([1 for s in base_symbols for iv in intervals if (s, iv) in filled_set])
    coverage_pct = round(100.0 * have_total / expected_total, 1) if expected_total else 0.0

    if coverage_pct > 80.0:
       # Filtra in-memory símbolos que faltam algum intervalo (warm parcial).
       missing_set = set(
           s for s in base_symbols
           if not all((s, iv) in filled_set for iv in intervals)
       )
       base_symbols = [s for s in base_symbols if s not in missing_set]
       n_sym = len(base_symbols)

    symbols = base_symbols
    expected_total = n_sym * len(intervals)

    fail_map = {(r[0], r[1]): {"fail_count": r[2], "last_error": r[3]} for r in fail_rows}

    by_interval = []
    missing_total = 0
    samples = []
    for iv in intervals:
        have = sum(1 for s in symbols if (s, iv) in filled_set)
        miss_syms = [s for s in symbols if (s, iv) not in filled_set]
        missing_total += len(miss_syms)
        by_interval.append({
            "interval": iv,
            "have": have,
            "expected": n_sym,
            "missing": len(miss_syms),
            "complete": len(miss_syms) == 0,
        })
        for s in miss_syms[: max(0, sample_missing // max(1, len(intervals)))]:
            info = fail_map.get((s, iv)) or {}
            samples.append({
                "symbol": s,
                "interval": iv,
                "fail_count": info.get("fail_count"),
                "last_error": (info.get("last_error") or "")[:200] or None,
            })

    ready = missing_total == 0 and n_sym > 0
    have_total = expected_total - missing_total
    return {
        "ready": ready,
        "symbols": n_sym,
        "intervals": intervals,
        "expected_pairs": expected_total,
        "filled_pairs": have_total,
        "missing_pairs": missing_total,
        "coverage_pct": round(100.0 * have_total / expected_total, 1) if expected_total else 0.0,
        "by_interval": by_interval,
        "missing_sample": samples[:sample_missing],
        "message": (
            "Dados completos — scanners liberados."
            if ready else
            f"Faltam {missing_total}/{expected_total} pares (symbol, interval). "
            "Scanners bloqueados até o warm completar."
        ),
    }


def read_bars(symbol=None, interval=None, start=None, end=None, limit=None):
    """Leitura SOMENTE LEITURA da tabela `bars` para o painel de inspeção.

    Filtros opcionais por `symbol`, `interval` e janela de timestamp (`start`/`end`
    em ISO8601 ou 'YYYY-MM-DD' — comparável como texto pois os ts são ISO8601).
    `limit` (int) limita o número de linhas; None/0 = sem limite. Retorna DataFrame
    ordenado por symbol, interval, ts. Não toca em fill_state nem aciona yfinance."""
    _ensure_schema()
    clauses, params = [], []
    if symbol:
        clauses.append("symbol=?"); params.append(symbol)
    if interval:
        clauses.append("interval=?"); params.append(interval)
    if start:
        clauses.append("ts>=?"); params.append(start)
    if end:
        clauses.append("ts<=?"); params.append(end)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = ("SELECT symbol, interval, ts, open, high, low, close, volume "
           "FROM bars" + where + " ORDER BY symbol, interval, ts")
    if limit:
        sql += " LIMIT ?"; params.append(int(limit))
    with _lock:
        rows = _connect().execute(sql, params).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=["symbol", "interval", "ts", "open", "high", "low", "close", "volume"])


def read_fill_state():
    """Snapshot SOMENTE LEITURA da tabela fill_state: quais (symbol, interval)
    já estão preenchidos e quando (last_filled_at)."""
    _ensure_schema()
    with _lock:
        rows = _connect().execute(
            "SELECT symbol, interval, last_filled_at FROM fill_state "
            "ORDER BY symbol, interval"
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=["symbol", "interval", "last_filled_at"])

def read_latest_bars_summary():
    """Retorna o candle mais recente (ts, close, volume) de cada par (symbol, interval)
    para uso em diagnóstico rápido (ex: /api/probe), sem carregar milhares de linhas."""
    _ensure_schema()
    with _lock:
        # SQLite garante que colunas não-agregadas vêm da mesma linha que satisfez o MAX()
        rows = _connect().execute(
            "SELECT symbol, interval, MAX(ts), close, volume FROM bars GROUP BY symbol, interval"
        ).fetchall()
    return {(r[0], r[1]): {"last_ts": r[2], "last_close": r[3], "last_volume": r[4]} for r in rows}

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

    def process_item(symbol, interval):
        if _is_filled(symbol, interval, now):
            return symbol, interval, True, None

        # use_cache=False: prewarm é aquisição — precisa de dados frescos (e
        # atualiza o chart_cache via proxy PHP como efeito colateral do fetch).
        df, err = _fetch_from_yahoo(symbol, interval, MAX_PERIOD.get(interval, "1y"),
                                    attempts, use_cache=False)
        if df is not None and not df.empty:
            _upsert_bars(symbol, interval, df)
            _set_fill_state(symbol, interval)
            _clear_failure(symbol, interval)
            return symbol, interval, True, None
        else:
            _record_failure(symbol, interval, attempts, err)
            return symbol, interval, False, err

    import concurrent.futures
    done = 0
    # Processamos com 5 workers paralelos para que ativos problemáticos
    # (timeouts) não congelem todo o aquecimento.
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_item, s, i): (s, i) for s, i in items}
        for future in concurrent.futures.as_completed(futures):
            s, i = futures[future]
            try:
                symbol, interval, ok, err = future.result()
            except Exception as e:
                # Catch-all se process_item quebrar por erro imprevisto
                _record_failure(s, i, attempts, repr(e))
                symbol, interval, ok, err = s, i, False, repr(e)

            if not ok:
                failures.append((symbol, interval))

            done += 1
            if progress is not None:
                progress(done, total, symbol, ok)

    return failures
