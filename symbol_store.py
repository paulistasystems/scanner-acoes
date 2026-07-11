# -*- coding: utf-8 -*-
"""
symbol_store.py — Camada de gestão dinâmica de símbolos (Supabase) para os scanners.

Fonte única de verdade do UNIVERSO de ativos e do seu CICLO DE VIDA (list/watch/delist):
o catálogo vive no Supabase (Postgres), remoto e persistente — sobrevive a redeploys do
Streamlit Cloud e é compartilhado por todos os scanners/containeres. As listas hardcoded
(`symbols_fallback`) continuam presentes como **fallback** (Supabase indisponível) e como
**seed** inicial.

Escopo ( ROADMAP.md → "Supabase"):
  - Leitura  (anon, RLS): universo ativo para os scans + navegação no painel de BD.
  - Escrita  (service_role): job de teste (botão in-app) grava `symbol_tests` + probe HTTP.
  - Regras   (service_role): motor K/D/M transiciona `symbols.status` + `symbol_status_log`.

Framework-agnostic (como o data_layer): só depende de sqlite3-free stdlib + pandas +
supabase + python-dotenv. **Não importa streamlit** — o path quente lê `os.environ`
(populado por `load_dotenv()` localmente; no Cloud, cada app chama
`bridge_streamlit_secrets()` uma vez para copiar `st.secrets` → `os.environ`).

Contrato com o data_layer: as BARRAS (OHLCV) continuam no SQLite — este módulo afeta só a
camada de universo. `load_universe()` é a única chamada no path quente; tem cache TTL e
fallback silencioso, então o scan **nunca** quebra por falta de Supabase.
"""

import os
import time
import threading
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd
from dotenv import load_dotenv

import symbols_fallback
import data_layer

load_dotenv()  # local: carrega .env; no-op se ausente

# ----------------------------- Config -----------------------------
_URL_ENV = "SUPABASE_URL"
_ANON_ENV = "SUPABASE_ANON_KEY"
_SERVICE_ENV = "SUPABASE_SERVICE_KEY"

# Sinal forte de delisting no HTML da página de quote do Yahoo (hardcoded — sem tabela).
_DELIST_MARKER = "No results for"
_QUOTE_URL = "https://finance.yahoo.com/quote/{symbol}"

# Limiares do motor de regras (configuráveis via apply_rules).
K_WATCH = 3        # falhas consecutivas → listed vira watch
D_DELIST_DAYS = 7  # dias em watch falhando → delisted
M_RELIST = 3       # sucessos consecutivos → relista

_CACHE_TTL = 300  # 5 min — espelha o TTL histórico do yfinance
_cache_lock = threading.Lock()
_universe_cache = {"symbols": None, "expires_at": 0.0}
_client_cache = {}  # (role, url, key) -> Client


def _cfg(key):
    return os.environ.get(key)


def configured():
    """Há URL + anon key? Decide usa-Supabase (True) vs fallback bundled (False)."""
    return bool(_cfg(_URL_ENV) and _cfg(_ANON_ENV))


def has_service_key():
    """Há service_role key? Habilita escrita (job de teste + motor de regras)."""
    return bool(_cfg(_SERVICE_ENV))


def bridge_streamlit_secrets():
    """Copia `st.secrets` → `os.environ` (para o Streamlit Cloud). Chamar no topo dos apps.
    Localmente o `.env` (via load_dotenv) já populou o ambiente; isto é só para o Cloud."""
    try:
        import streamlit as st
        secrets = st.secrets
    except Exception:
        return
    for key in (_URL_ENV, _ANON_ENV, _SERVICE_ENV):
        val = secrets.get(key)
        if val and not os.environ.get(key):
            os.environ[key] = val


def _get_client(role="anon"):
    """Client Supabase (anon p/ leitura; service p/ escrita). Cacheado por credencial."""
    if role == "service":
        key = _cfg(_SERVICE_ENV)
        if not key:
            raise RuntimeError("SUPABASE_SERVICE_KEY ausente — escrita desabilitada.")
    else:
        key = _cfg(_ANON_ENV)
    url = _cfg(_URL_ENV)
    if not (url and key):
        raise RuntimeError("Supabase não configurado (SUPABASE_URL/ANON_KEY ausentes).")
    cache_key = (role, url, key)
    client = _client_cache.get(cache_key)
    if client is None:
        from supabase import create_client
        client = create_client(url, key)
        _client_cache[cache_key] = client
    return client


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def invalidate_cache():
    """Limpa o cache do universo ativo (chamar após mudanças de status manuais/automáticas)."""
    with _cache_lock:
        _universe_cache["symbols"] = None
        _universe_cache["expires_at"] = 0.0


# ----------------------------- Leitura (anon) -----------------------------
def load_universe():
    """Lista de símbolos ATIVOS (status='listed') do Supabase, na ordem alfabética.

    Cache TTL (~5 min) + fallback silencioso ao `symbols_fallback.ATIVOS_B3_AMPLIADO`
    (Supabase ausente/vazio/erro). O scan nunca quebra por falta de Supabase."""
    if not configured():
        return list(symbols_fallback.ATIVOS_B3_AMPLIADO)

    now = time.monotonic()
    with _cache_lock:
        cached = _universe_cache["symbols"]
        if cached is not None and now < _universe_cache["expires_at"]:
            return list(cached)

    try:
        resp = _get_client("anon").table("symbols").select("symbol").eq(
            "status", "listed"
        ).order("symbol", desc=False).execute()
        syms = [r["symbol"] for r in (resp.data or [])]
    except Exception:
        return list(symbols_fallback.ATIVOS_B3_AMPLIADO)

    if not syms:  # Supabase configurado mas vazio (ainda não fez seed) → fallback
        return list(symbols_fallback.ATIVOS_B3_AMPLIADO)

    with _cache_lock:
        _universe_cache["symbols"] = list(syms)
        _universe_cache["expires_at"] = now + _CACHE_TTL
    return syms


def load_universe_grouped():
    """{category: [symbols]} considerando só 'listed'. Para painel/contagens ao vivo.
    Em fallback, deriva do `symbols_fallback` (status unknown → assume listed)."""
    if not configured():
        return _grouped_from_fallback()
    try:
        resp = _get_client("anon").table("symbols").select(
            "symbol,category"
        ).eq("status", "listed").execute()
        out = {}
        for r in (resp.data or []):
            out.setdefault(r.get("category") or "—", []).append(r["symbol"])
        return out
    except Exception:
        return _grouped_from_fallback()


def _grouped_from_fallback():
    out = {}
    for row in symbols_fallback.build_seed_catalog():
        if row["status"] == "listed":
            out.setdefault(row["category"], []).append(row["symbol"])
    return out


_SYMBOL_COLS = [
    "symbol", "name", "category", "asset_type", "liquidity_tier", "status",
    "prior_symbols", "listed_at", "delisted_at", "delist_reason", "notes",
]


def read_symbols(status=None):
    """DataFrame do catálogo completo (anon, somente leitura). Filtro opcional de status."""
    if not configured():
        return pd.DataFrame()
    try:
        q = _get_client("anon").table("symbols").select(",".join(_SYMBOL_COLS))
        if status:
            q = q.eq("status", status)
        resp = q.order("symbol", desc=False).execute()
        return pd.DataFrame(resp.data or [], columns=_SYMBOL_COLS)
    except Exception:
        return pd.DataFrame()


def read_tests(symbol=None, limit=200):
    """DataFrame com o histórico de testes (anon), mais recentes primeiro."""
    if not configured():
        return pd.DataFrame()
    try:
        q = _get_client("anon").table("symbol_tests").select(
            "symbol,interval,tested_at,bars,ok,error,delist_signal"
        )
        if symbol:
            q = q.eq("symbol", symbol)
        resp = q.order("tested_at", desc=True).limit(limit).execute()
        return pd.DataFrame(
            resp.data or [],
            columns=["symbol", "interval", "tested_at", "bars", "ok", "error", "delist_signal"],
        )
    except Exception:
        return pd.DataFrame()


def status_log(limit=100):
    """DataFrame com a trilha de transições de status (anon), mais recentes primeiro."""
    if not configured():
        return pd.DataFrame()
    try:
        resp = _get_client("anon").table("symbol_status_log").select(
            "symbol,from_status,to_status,changed_at,reason,source"
        ).order("changed_at", desc=True).limit(limit).execute()
        return pd.DataFrame(
            resp.data or [],
            columns=["symbol", "from_status", "to_status", "changed_at", "reason", "source"],
        )
    except Exception:
        return pd.DataFrame()


def erroring_symbols():
    """Símbolos candidatos ao teste rápido (escopo default do job): watch + delisted +
    falhas recentes no data_layer. Retorna lista de dicts {symbol, status}."""
    if not configured():
        return []
    out = []
    try:
        resp = _get_client("anon").table("symbols").select("symbol,status").in_(
            "status", ["watch", "delisted"]
        ).order("symbol", desc=False).execute()
        out.extend({"symbol": r["symbol"], "status": r["status"]} for r in (resp.data or []))
    except Exception:
        pass
    # acrescenta símbolos com falha recente no SQLite (ainda 'listed' mas com problema)
    try:
        df = data_layer.list_failures()
        if df is not None and not df.empty:
            known = {r["symbol"] for r in out}
            for sym in sorted(set(df["symbol"].tolist()) - known):
                out.append({"symbol": sym, "status": "listed (falha recente)"})
    except Exception:
        pass
    return out


# ----------------------------- Escrita (service_role) -----------------------------
def _probe_yahoo(symbol):
    """GET na página de quote do Yahoo → (delist_signal, note).

    A página renderiza literalmente ``No results for '<symbol>'`` quando o ticker é
    inválido/delistado. Procuramos a string ``"No results for"`` (hardcoded) no corpo;
    achou → sinal forte de delisting. Erro de rede NÃO é sinal (pode ser throttling)."""
    url = _QUOTE_URL.format(symbol=symbol)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        if _DELIST_MARKER in body:
            return True, "Yahoo: 'No results for'"
        return False, ""
    except Exception as e:  # rede/timeout → sem sinal (não confundir com delist)
        return False, f"http_error: {e!r}"


def record_test(symbol, interval, bars, ok, error, delist_signal):
    """Insere uma linha em `symbol_tests` (service_role). Best-effort: no-op se sem service
    key ou em erro — o scan nunca quebra por falha de gravação de auditoria."""
    if not (configured() and has_service_key()):
        return
    try:
        _get_client("service").table("symbol_tests").insert({
            "symbol": symbol,
            "interval": interval,
            "bars": int(bars) if bars else 0,
            "ok": bool(ok),
            "error": (str(error) or "")[:500],
            "delist_signal": bool(delist_signal),
        }).execute()
    except Exception:
        pass


def run_test(symbol, interval, period=None):
    """Executa UM teste de download (+ probe HTTP se falhou) e grava em `symbol_tests`.

    Reutiliza o `data_layer._fetch_from_yahoo` (mesma filosofia empty/truncated + retry) —
    resposta vazia NÃO vira delist imediato; precisa de sequência K/D (apply_rules).
    Retorna dict {symbol, interval, bars, ok, error, delist_signal}."""
    period = period or data_layer.MAX_PERIOD.get(interval, "1y")
    df, err = data_layer._fetch_from_yahoo(symbol, interval, period)
    ok = df is not None and not df.empty
    bars = len(df) if ok else 0
    if ok:
        delist_signal, note = False, ""
        error = ""
    else:
        delist_signal, note = _probe_yahoo(symbol)
        error = err or note or "empty/truncated response"
    record_test(symbol, interval, bars, ok, error, delist_signal)
    return {
        "symbol": symbol, "interval": interval, "bars": bars, "ok": ok,
        "error": error, "delist_signal": delist_signal,
    }


def set_status(symbol, status, reason="manual", source="ui"):
    """Override manual de status (service_role). Atualiza symbols + symbol_status_log e
    invalida o cache do universo. Retorna True se mudou."""
    if not (configured() and has_service_key()):
        return False
    if status not in ("listed", "watch", "delisted"):
        raise ValueError(f"status inválido: {status}")
    client = _get_client("service")
    try:
        cur = client.table("symbols").select("status").eq("symbol", symbol).single().execute().data
    except Exception:
        cur = None
    from_status = cur.get("status") if cur else None
    if from_status == status:
        return False
    update = {"status": status}
    if status == "delisted":
        update["delisted_at"] = _now_iso()
    elif status == "listed":
        update["delisted_at"] = None
    try:
        client.table("symbols").update(update).eq("symbol", symbol).execute()
        client.table("symbol_status_log").insert({
            "symbol": symbol, "from_status": from_status, "to_status": status,
            "reason": reason, "source": source,
        }).execute()
    except Exception:
        return False
    invalidate_cache()
    return True


# ----------------------------- Motor de regras (service_role) -----------------------------
def _fetch_rule_inputs():
    """Traz, em 3 queries, tudo que o motor precisa: statuses atuais, testes recentes
    (últimos 60d) e últimas transições para 'watch'. Retorna (statuses, tests, watch_since)."""
    client = _get_client("service")
    since = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    statuses = {r["symbol"]: r for r in (
        client.table("symbols").select("symbol,status,delisted_at").execute().data or []
    )}
    tests = {}
    for r in (client.table("symbol_tests").select("symbol,tested_at,ok").gte(
        "tested_at", since
    ).order("tested_at", desc=False).execute().data or []):
        tests.setdefault(r["symbol"], []).append(bool(r["ok"]))
    # watch_since: última vez que virou 'watch' (mais recente por changed_at)
    watch_since = {}
    for r in (client.table("symbol_status_log").select("symbol,changed_at").eq(
        "to_status", "watch"
    ).order("changed_at", desc=True).execute().data or []):
        watch_since.setdefault(r["symbol"], r["changed_at"])
    return statuses, tests, watch_since


def _trailing_run(seq, value):
    """Tamanho da sequência final (trailing) de `value` em `seq` (seq cronológica)."""
    run = 0
    for v in reversed(seq):
        if v == value:
            run += 1
        else:
            break
    return run


def apply_rules(now=None, k=K_WATCH, d_days=D_DELIST_DAYS, m=M_RELIST):
    """Motor K/D/M: transiciona symbols.status com base nos testes recentes.

      listed  → watch     : k falhas consecutivas.
      watch   → delisted  : ainda falhando há ≥ d_days desde que virou watch.
      watch/delisted → listed : m sucessos consecutivos (relist automático).

    Cada transição atualiza `symbols` + insere em `symbol_status_log` e retorna a lista de
    mudanças [{symbol, from, to, reason}]. No-op (retorna []) se sem service key."""
    if not (configured() and has_service_key()):
        return []
    try:
        statuses, tests, watch_since = _fetch_rule_inputs()
    except Exception:
        return []

    now_dt = now or datetime.now(timezone.utc)
    client = _get_client("service")
    changes = []

    def transition(symbol, to_status, reason, update_extra=None):
        from_status = statuses[symbol]["status"]
        update = {"status": to_status}
        if to_status == "delisted":
            update["delisted_at"] = now_dt.isoformat()
        elif to_status == "listed":
            update["delisted_at"] = None
        if update_extra:
            update.update(update_extra)
        client.table("symbols").update(update).eq("symbol", symbol).execute()
        client.table("symbol_status_log").insert({
            "symbol": symbol, "from_status": from_status, "to_status": to_status,
            "reason": reason, "source": "rule-engine",
        }).execute()
        changes.append({"symbol": symbol, "from": from_status, "to": to_status, "reason": reason})

    for symbol, info in statuses.items():
        status = info.get("status")
        seq = tests.get(symbol, [])
        fails = _trailing_run(seq, False)
        succs = _trailing_run(seq, True)

        if status == "listed" and fails >= k:
            transition(symbol, "watch", f"auto: {fails} falhas consecutivas")
        elif status == "watch":
            if succs >= m:
                transition(symbol, "listed", f"auto: {succs} sucessos consecutivos (relist)")
            elif fails >= 1:
                since_str = watch_since.get(symbol)
                if since_str:
                    try:
                        since_dt = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
                        if (now_dt - since_dt).days >= d_days:
                            transition(symbol, "delisted",
                                       f"auto: falhando há ≥{d_days}d em watch")
                    except Exception:
                        pass
        elif status == "delisted":
            if succs >= m:
                transition(symbol, "listed", f"auto: {succs} sucessos consecutivos (relist)")

    if changes:
        invalidate_cache()
    return changes
