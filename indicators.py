# -*- coding: utf-8 -*-
"""
indicators.py — Indicadores técnicos em pandas puro (sem pandas_ta / numba).

Motivo: o deploy Passenger (DirectAdmin, paulista.dev/scanner) roda Python 3.9, onde
pandas_ta/numba não instalam. A análise dos scanners usa uma superfície mínima de
indicadores (EMA, RSI, ATR, ADX/DI, MACD), todos com suavização de Wilder via RMA =
``ewm(alpha=1/length, min_periods=length, adjust=False)`` — exatamente a convenção do
pandas_ta, de modo que os valores coincidem com a versão Streamlit (3.13 + pandas_ta).

Nomenclatura de colunas idêntica ao pandas_ta (ADX_14, DMP_14, DMN_14,
MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9) para que o código extraído dos scanners
permaneça inalterado. Paridade validada por tools/check_indicators.py.
"""

import numpy as np
import pandas as pd


def _rma(series, length):
    """Média móvel de Wilder (RMA): ewm(alpha=1/length, min_periods=length, adjust=False).
    Equivale ao ``ta.rma`` do pandas_ta — base de RSI/ATR/ADX/DI."""
    return series.ewm(alpha=1.0 / length, min_periods=length, adjust=False).mean()


def ema(close, length=None, offset=None):
    """Média móvel exponencial — compatível com ``ta.ema`` do pandas_ta (e TA-Lib):
    semente = SMA(length) no primeiro índice onde há janela completa, depois recursão
    ewm(adjust=False, alpha=2/(length+1)). Isso produz cabeça de NaN de tamanho
    ``length-1`` (igual ao pandas_ta) — diferentemente do ``ewm(adjust=False)`` puro,
    que semeia no índice 0.

    Robusta a cabeça de NaN na entrada (necessário quando aplicada sobre a linha do
    MACD, que já vem com NaN head), pois a semente via ``rolling`` pula os NaNs
    iniciais automaticamente."""
    length = int(length) if length and length > 0 else 10
    close = pd.Series(close, dtype="float64")
    alpha = 2.0 / (length + 1)
    sma = close.rolling(window=length, min_periods=length).mean()
    out = pd.Series(np.nan, index=close.index, dtype="float64")
    start_pos = sma.first_valid_index()
    if start_pos is None:
        return out
    start = close.index.get_loc(start_pos)
    out.iloc[start] = sma.iloc[start]
    vals = out.to_numpy()
    src = close.to_numpy()
    for i in range(start + 1, len(src)):
        if not np.isnan(src[i]) and not np.isnan(vals[i - 1]):
            vals[i] = (1.0 - alpha) * vals[i - 1] + alpha * src[i]
    return pd.Series(vals, index=close.index)


def rsi(close, length=14, scalar=100):
    """Índice de Força Relativa (Wilder). Coincide com ``ta.rsi(close, length=14)``."""
    delta = close.diff()
    positive = delta.clip(lower=0.0)
    negative = (-delta).clip(lower=0.0)  # perdas como números positivos
    pos_avg = _rma(positive, length)
    neg_avg = _rma(negative, length)
    rs = pos_avg / neg_avg
    rsi_ = scalar - (scalar / (1.0 + rs))
    # Casos degenerados (neg_avg == 0): RSI = 100; pos_avg == 0: RSI = 0.
    rsi_ = rsi_.where(neg_avg != 0, scalar)
    rsi_ = rsi_.where(pos_avg != 0, 0.0)
    return rsi_


def atr(high, low, close, length=14):
    """True Range médio (Wilder). Coincide com ``ta.atr(..., length=14)``."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return _rma(tr, length)


def adx(high, low, close, length=14):
    """ADX + DI+/DI- (Wilder). Retorna DataFrame com ADX_{length}, DMP_{length}, DMN_{length}
    (mesmas colunas do pandas_ta).

    Nota: o estado estacionário (barras recentes) coincide com o pandas_ta a ~1e-6; a
    janela de warmup do ADX é um pouco maior que a do pandas_ta (NaN head ~2*length vs
    ~length), mas os scanners exigem ``len(df) >= 100`` e leem só ``iloc[-1]``/``iloc[-5]``,
    então nunca tocam a região de warmup — a diferença é irrelevante na prática."""
    up = high.diff()
    down = -low.diff()

    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)

    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    atr_ = _rma(tr, length)
    plus_di = 100.0 * _rma(plus_dm, length) / atr_
    minus_di = 100.0 * _rma(minus_dm, length) / atr_

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx_val = _rma(dx, length)

    return pd.DataFrame(
        {
            f"ADX_{length}": adx_val,
            f"DMP_{length}": plus_di,
            f"DMN_{length}": minus_di,
        },
        index=high.index,
    )


def macd(close, fast=12, slow=26, signal=9):
    """MACD. Retorna DataFrame com MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
    (mesmas colunas do pandas_ta). Usa ``ema`` (semente SMA) para fast/slow/signal,
    igual ao pandas_ta — inclusive sobre a linha do MACD, que tem NaN head."""
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    suffix = f"{fast}_{slow}_{signal}"
    return pd.DataFrame(
        {
            f"MACD_{suffix}": macd_line,
            f"MACDs_{suffix}": signal_line,
            f"MACDh_{suffix}": hist,
        },
        index=close.index,
    )
