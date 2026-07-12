# -*- coding: utf-8 -*-
"""
symbol_store.py — Universo de ativos para os scanners (SQLite local, sem Supabase).

O catálogo vive em `symbols_fallback` (lista bundled). A camada de barras OHLCV
fica no SQLite via `data_layer`. Este módulo é framework-agnostic (sem streamlit).
"""

import time
import threading

import symbols_fallback
import data_layer

_CACHE_TTL = 300
_cache_lock = threading.Lock()
_universe_cache = {"symbols": None, "expires_at": 0.0}


def configured():
    return False


def has_service_key():
    return False


def invalidate_cache():
    with _cache_lock:
        _universe_cache["symbols"] = None
        _universe_cache["expires_at"] = 0.0


def load_universe():
    """Lista de símbolos ativos (bundled). Cache TTL ~5 min."""
    now = time.monotonic()
    with _cache_lock:
        cached = _universe_cache["symbols"]
        if cached is not None and now < _universe_cache["expires_at"]:
            return list(cached)
    syms = list(symbols_fallback.ATIVOS_B3_AMPLIADO)
    with _cache_lock:
        _universe_cache["symbols"] = syms
        _universe_cache["expires_at"] = now + _CACHE_TTL
    return syms


def load_universe_grouped():
    """{category: [symbols]} derivado do fallback bundled."""
    out = {}
    for row in symbols_fallback.build_seed_catalog():
        if row["status"] == "listed":
            out.setdefault(row["category"], []).append(row["symbol"])
    return out


def erroring_symbols():
    """Símbolos com falha recente no data_layer. Retorna lista de dicts {symbol, status}."""
    out = []
    try:
        df = data_layer.list_failures()
        if df is not None and not df.empty:
            for sym in sorted(df["symbol"].tolist()):
                out.append({"symbol": sym, "status": "listed (falha recente)"})
    except Exception:
        pass
    return out
