#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_symbols.py — Popular o catálogo `symbols` do Supabase (seed única, idempotente).

Lê `symbols_fallback.build_seed_catalog()` (universo ativo) e faz upsert na
tabela `symbols`, registrando cada entrada em `symbol_status_log` (source='seed').

Pré-requisitos:
  1. Rodar `supabase_schema.sql` no SQL Editor do Supabase (cria as tabelas + RLS).
  2. Preencher `SUPABASE_SERVICE_KEY` no `.env` (service_role key do painel do Supabase).

Uso:
  venv313/bin/python seed_symbols.py             # upsert + log
  venv313/bin/python seed_symbols.py --dry-run   # só mostra o que faria (não escreve)

Nota: re-executar o seed **reseta** os status para o catálogo bundled (sobrescreve mudanças
manuais/automáticas). Use só para (re)inicializar; para ajustes pontuais use o painel 🧪.
"""

import sys

import symbol_store
import symbols_fallback

_BATCH = 100  # lotes p/ o upsert/insert ficar seguro no PostgREST


def main(dry_run=False):
    if not symbol_store.configured():
        print("❌ Supabase não configurado (SUPABASE_URL / SUPABASE_ANON_KEY no .env).")
        sys.exit(1)
    if not symbol_store.has_service_key():
        print("❌ SUPABASE_SERVICE_KEY ausente — o seed exige escrita (service_role).")
        sys.exit(1)

    catalog = symbols_fallback.build_seed_catalog()
    print(f"Seed: {len(catalog)} símbolos (todos listed).")

    if dry_run:
        print("--dry-run: primeiras 5 linhas que seriam upsert:")
        for r in catalog[:5]:
            print("  ", r)
        print("  ...")
        return

    client = symbol_store._get_client("service")
    now = symbol_store._now_iso()

    rows = []
    for r in catalog:
        rows.append({
            "symbol": r["symbol"],
            "name": r["name"],
            "category": r["category"],
            "asset_type": r["asset_type"],
            "liquidity_tier": "universal",
            "status": r["status"],
            "listed_at": now if r["status"] == "listed" else None,
        })

    n = 0
    for i in range(0, len(rows), _BATCH):
        client.table("symbols").upsert(rows[i:i + _BATCH], on_conflict="symbol").execute()
        n += len(rows[i:i + _BATCH])
    print(f"✅ {n} símbolos upsert em `symbols`.")

    log_rows = [{
        "symbol": r["symbol"], "from_status": None, "to_status": r["status"],
        "changed_at": now, "reason": "seed inicial", "source": "seed",
    } for r in catalog]
    nlog = 0
    for i in range(0, len(log_rows), _BATCH):
        client.table("symbol_status_log").insert(log_rows[i:i + _BATCH]).execute()
        nlog += len(log_rows[i:i + _BATCH])
    print(f"✅ {nlog} linhas em `symbol_status_log` (source='seed').")

    symbol_store.invalidate_cache()
    print("Seed concluído. O scanner agora lê o universo do Supabase.")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
