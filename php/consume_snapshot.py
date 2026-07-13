#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consome o snapshot gerado por ``yahoo_snapshot.php`` (100% PHP ao vivo).

Fluxo:
  1. dispara ``yahoo_snapshot.php?json=1`` — o PHP busca todos os símbolos × TFs no
     Yahoo (curl_multi concorrente) e grava ``all_data.csv`` (longo/tidy) e
     ``all_data.json`` (aninhado);
  2. baixa ``all_data.csv`` (DB friendly);
  3. carrega (pandas, se disponível; senão stdlib ``csv``) e reporta cobertura.

Uso::

    venv39/bin/python php/consume_snapshot.py                 # paulista.dev
    venv39/bin/python php/consume_snapshot.py https://outro.host

CSV (``all_data.csv``): ``symbol,interval,ts,open,high,low,close,volume`` — uma linha
por candle, ``ts`` em ISO8601 UTC. Direto pra pandas / SQLite / SQL ``LOAD DATA``.
"""
import csv
import json
import sys
import urllib.request
from collections import Counter

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://paulista.dev"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15"


def get(url, timeout=300):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main():
    print(f"[1/3] disparando build: {BASE}/yahoo_snapshot.php?json=1 ...")
    summary = json.loads(get(f"{BASE}/yahoo_snapshot.php?json=1", timeout=300))
    print("      sumário:", json.dumps(summary, indent=2)[:900])

    if summary.get("status") != "ok":
        sys.exit(f"      build não concluiu: {summary.get('status')}")

    csv_url = summary["files"]["csv"]["url"]
    print(f"\n[2/3] baixando {csv_url} ({summary['files']['csv']['bytes']} bytes) ...")
    raw = get(csv_url, timeout=180).decode("utf-8")

    print("\n[3/3] cobertura (lendo o CSV):")
    try:
        import pandas as pd  # noqa
        import io
        df = pd.read_csv(io.StringIO(raw))
        print(f"      linhas (candles): {len(df)} | colunas: {list(df.columns)}")
        cnt = df.groupby("interval")["symbol"].nunique()
        print("      séries OK por intervalo:")
        for iv, n in cnt.items():
            print(f"        {iv}: {n} símbolos")
        probe = df[df["symbol"] == "PETR4.SA"].sort_values("ts")
        if len(probe):
            print("      exemplo PETR4.SA 1d (última):",
                  probe[probe["interval"] == "1d"].tail(1).to_dict("records")[0])
    except ImportError:
        rows = list(csv.DictReader(raw.splitlines()))
        by_iv = Counter(r["interval"] for r in rows)
        print(f"      linhas (candles): {len(rows)}")
        print("      candles por intervalo:", dict(by_iv))


if __name__ == "__main__":
    main()
