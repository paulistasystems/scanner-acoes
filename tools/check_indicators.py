# -*- coding: utf-8 -*-
"""
check_indicators.py — Portão de paridade: compara indicators.py (pandas puro) contra
pandas_ta, sobre candles REAIS do scanner.db (somente leitura).

Como pandas_ta só existe no venv313 e indicators.py roda no venv39, rode em DOIS
interpretadores e depois compare:

    venv313/bin/python tools/check_indicators.py ref   tools/_ref.json
    venv39/bin/python  tools/check_indicators.py new   tools/_new.json
    venv39/bin/python  tools/check_indicators.py compare tools/_ref.json tools/_new.json

Saída do compare: diff máx (abs e rel) por indicador. PASS se tudo < 1e-6 (abs) —
ambos usam a mesma suavização de Wilder (RMA = ewm(alpha=1/length, adjust=False)), logo
devem coincidir a ~1e-12 fora do warmup.
"""

import argparse
import json
import math
import os
import sys

import pandas as pd

# Garante que importa do repo (não de tools/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data_layer  # noqa: E402  — read-only: read_bars nunca aciona yfinance

SYMBOLS = ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "MGLU3.SA"]
INTERVALS = ["1d", "1h", "30m"]
TAIL = 60  # últimas N linhas — bem além do warmup de qualquer indicador


def _tail_values(series):
    s = pd.Series(series).astype(float).tail(TAIL)
    return [None if math.isnan(v) else float(v) for v in s.tolist()]


def compute_all(df, impl):
    """Devolve dict {indicator: [values]} usando impl ('ref'=pandas_ta | 'new'=indicators)."""
    out = {}
    if impl == "ref":
        import pandas_ta as ta
        out["ema20"] = _tail_values(ta.ema(df["Close"], length=20))
        out["ema50"] = _tail_values(ta.ema(df["Close"], length=50))
        out["rsi14"] = _tail_values(ta.rsi(df["Close"], length=14))
        out["atr14"] = _tail_values(ta.atr(df["High"], df["Low"], df["Close"], length=14))
        adx = ta.adx(df["High"], df["Low"], df["Close"], length=14)
        out["adx14"] = _tail_values(adx["ADX_14"])
        out["dmp14"] = _tail_values(adx["DMP_14"])
        out["dmn14"] = _tail_values(adx["DMN_14"])
        macd = ta.macd(df["Close"])
        out["macd"] = _tail_values(macd["MACD_12_26_9"])
        out["macds"] = _tail_values(macd["MACDs_12_26_9"])
        out["macdh"] = _tail_values(macd["MACDh_12_26_9"])
    else:
        import indicators as ind
        out["ema20"] = _tail_values(ind.ema(df["Close"], length=20))
        out["ema50"] = _tail_values(ind.ema(df["Close"], length=50))
        out["rsi14"] = _tail_values(ind.rsi(df["Close"], length=14))
        out["atr14"] = _tail_values(ind.atr(df["High"], df["Low"], df["Close"], length=14))
        adx = ind.adx(df["High"], df["Low"], df["Close"], length=14)
        out["adx14"] = _tail_values(adx["ADX_14"])
        out["dmp14"] = _tail_values(adx["DMP_14"])
        out["dmn14"] = _tail_values(adx["DMN_14"])
        macd = ind.macd(df["Close"])
        out["macd"] = _tail_values(macd["MACD_12_26_9"])
        out["macds"] = _tail_values(macd["MACDs_12_26_9"])
        out["macdh"] = _tail_values(macd["MACDh_12_26_9"])
    return out


def _ohlcv(sym, iv):
    """read_bars devolve colunas minúsculas + symbol/interval/ts. Converte para o
    DataFrame OHLCV esperado pelos indicadores (Open/High/Low/Close/Volume, índice ts)."""
    df = data_layer.read_bars(sym, iv)
    if df is None or df.empty:
        return None
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    return df.set_index("ts")[["Open", "High", "Low", "Close", "Volume"]]


def cmd_compute(impl, out_path):
    result = {}
    for sym in SYMBOLS:
        for iv in INTERVALS:
            df = _ohlcv(sym, iv)
            if df is None:
                print(f"  skip {sym} {iv}: sem dados no DB")
                continue
            result[f"{sym}|{iv}"] = compute_all(df, impl)
            print(f"  computed {sym} {iv} ({len(df)} bars) [{impl}]")
    with open(out_path, "w") as f:
        json.dump(result, f)
    print(f"OK -> {out_path} ({len(result)} séries)")


def cmd_compare(ref_path, new_path):
    with open(ref_path) as f:
        ref = json.load(f)
    with open(new_path) as f:
        new = json.load(f)

    # Os scanners só lêem barras recentes (iloc[-1]/iloc[-5]) e exigem len>=100, então
    # a paridade que importa é nas ÚLTIMAS K barras (fora do warmup). Medimos também o
    # máximo global só para transparência. Tolerância de equivalência prática: 1e-4
    # (filtros usam limiares inteiros; diferenças < 1e-4 nunca viram um filtro/display).
    LAST_K = 10
    tol_abs = 1e-4
    worst_recent = {}   # indicator -> (max_abs_lastK, where)
    worst_global = {}   # indicator -> (max_abs_all, where)
    for key in ref:
        if key not in new:
            print(f"!! faltando em new: {key}")
            continue
        for ind_name in ref[key]:
            r = ref[key][ind_name]
            n = new[key].get(ind_name)
            if n is None or len(r) != len(n):
                print(f"!! tamanho divergente em {key}/{ind_name}")
                continue
            for i, (a, b) in enumerate(zip(r, n)):
                if a is None or b is None:
                    continue
                d = abs(a - b)
                where = f"{key}[{i}]"
                gcur = worst_global.get(ind_name, (0.0, ""))
                if d > gcur[0]:
                    worst_global[ind_name] = (d, where)
                if i >= len(r) - LAST_K:  # dentro das últimas K
                    rcur = worst_recent.get(ind_name, (0.0, ""))
                    if d > rcur[0]:
                        worst_recent[ind_name] = (d, where)

    print(f"\n=== Paridade indicators.py vs pandas_ta (tolerância abs < {tol_abs:g}) ===")
    print(f"{'indicador':<10} {'max_abs últ.K':>16} {'max_abs global':>16}  (onde últ.K)")
    all_pass = True
    for ind_name in sorted(worst_recent):
        d_rec, w_rec = worst_recent.get(ind_name, (0.0, ""))
        d_glo = worst_global.get(ind_name, (0.0, ""))[0]
        flag = "OK" if d_rec < tol_abs else "FAIL"
        if d_rec >= tol_abs:
            all_pass = False
        print(f"{ind_name:<10} {d_rec:>16.3e} {d_glo:>16.3e}  {w_rec}  [{flag}]")

    print(f"\nresultado (últimas {LAST_K} barras, tolerância {tol_abs:g}) -> "
          f"{'PASS ✅' if all_pass else 'FAIL ❌'}")
    sys.exit(0 if all_pass else 1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_ref = sub.add_parser("ref"); p_ref.add_argument("out")
    p_new = sub.add_parser("new"); p_new.add_argument("out")
    p_cmp = sub.add_parser("compare"); p_cmp.add_argument("ref"); p_cmp.add_argument("new")
    args = ap.parse_args()
    if args.cmd in ("ref", "new"):
        cmd_compute(args.cmd, args.out)
    elif args.cmd == "compare":
        cmd_compare(args.ref, args.new)


if __name__ == "__main__":
    main()
