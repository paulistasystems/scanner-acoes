# -*- coding: utf-8 -*-
"""
Core dos Scanners (sem streamlit, sem pandas_ta).
"""

import pandas as pd
import numpy as np
import indicators as ta
import data_layer
from symbols_fallback import ATIVOS_B3_AMPLIADO

ADX_RISING_PERIODS = 5

def baixar_dados(symbol, interval, period):
    return data_layer.get_bars(symbol, interval, period)

def baixar_dados_15m(symbol):
    return data_layer.get_bars(symbol, '15m', '5d')

def baixar_dados_30m(symbol):
    return data_layer.get_bars(symbol, '30m', '10d')

def _prewarm_com_progresso(ativos, intervals, rotulo=''):
    pass  # Pre-warming é feito no background worker na versão web

def safe_float(x, default=0.0):
    """Converte valor para float com tratamento de erros."""
    try:
        if pd.isna(x) or x is None:
            return default
        return float(x)
    except Exception:
        return default

def analisar_ativo_completo(df, adx_min, rsi_min, rsi_max, vol_ratio_min):
    """
    Análise completa de um ativo com todos os indicadores.
    Retorna dict com todos os valores ou None se não passar nos filtros.
    """
    if len(df) < 100:
        return None

    last = df.iloc[-1]
    preco = safe_float(last['Close'])

    # EMAs
    df['EMA20'] = ta.ema(df['Close'], length=20)
    df['EMA50'] = ta.ema(df['Close'], length=50)
    ema20 = safe_float(df['EMA20'].iloc[-1])
    ema50 = safe_float(df['EMA50'].iloc[-1])

    # RSI
    df['RSI'] = ta.rsi(df['Close'], length=14)
    rsi = safe_float(df['RSI'].iloc[-1])

    # ADX com +DI / -DI
    adx_df = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    adx_val = safe_float(adx_df['ADX_14'].iloc[-1])
    plus_di = safe_float(adx_df['DMP_14'].iloc[-1])
    minus_di = safe_float(adx_df['DMN_14'].iloc[-1])

    # ADX Rising (current > 5 periods ago)
    adx_current = safe_float(adx_df['ADX_14'].iloc[-1])
    adx_past = safe_float(adx_df['ADX_14'].iloc[-ADX_RISING_PERIODS]) if len(adx_df) > ADX_RISING_PERIODS else adx_current
    adx_rising = adx_current > adx_past

    # ATR
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    atr_val = safe_float(df['ATR'].iloc[-1])

    # Volume Ratio
    vol20 = df['Volume'].rolling(20).mean()
    vol_medio = safe_float(vol20.iloc[-1])
    vol_ratio = safe_float(last['Volume']) / vol_medio if vol_medio > 0 else 0

    # Tríade: ADX + RSI + Volume todos na zona ideal
    triade_adx = adx_val >= adx_min
    triade_rsi = rsi_min <= rsi <= rsi_max
    triade_vol = vol_ratio >= vol_ratio_min
    triade_ok = triade_adx and triade_rsi and triade_vol
    triade_status = "✅ Completa" if triade_ok else "⚠️ Parcial"

    # Exit signals
    sinais_saida = []
    if not adx_rising:
        sinais_saida.append("⚠️ ADX↓")
    if rsi > rsi_max:
        sinais_saida.append("⚠️ RSI↑")
    sinal_saida = " | ".join(sinais_saida) if sinais_saida else "✅"

    # Score (normalizado para 0-100)
    score_raw = 0
    if preco > ema20:
        score_raw += 20
    if preco > ema50:
        score_raw += 15
    if triade_adx:
        score_raw += 20
    if triade_rsi:
        score_raw += 20
    if triade_vol:
        score_raw += 15
    if adx_rising:
        score_raw += 10
    if plus_di > minus_di:
        score_raw += 10
    score = round((score_raw / 110) * 100)

    return {
        'preco': preco,
        'ema20': ema20,
        'ema50': ema50,
        'rsi': rsi,
        'adx': adx_val,
        'adx_rising': adx_rising,
        'plus_di': plus_di,
        'minus_di': minus_di,
        'vol_ratio': vol_ratio,
        'vol_medio': vol_medio,
        'atr': atr_val,
        'triade_ok': triade_ok,
        'triade_status': triade_status,
        'sinal_saida': sinal_saida,
        'score': score,
    }

def analisar_tendencia_tf(df):
    """Analisa tendência de um timeframe auxiliar (1H ou 30M). Retorna string de tendência."""
    if df is None or len(df) < 50:
        return "Sem dados"
    try:
        preco = safe_float(df['Close'].iloc[-1])
        ema20 = safe_float(ta.ema(df['Close'], length=20).iloc[-1])
        rsi = safe_float(ta.rsi(df['Close'], length=14).iloc[-1])
        if preco > ema20 and rsi > 50:
            return "✅ Alta"
        elif preco > ema20:
            return "⚠️ Neutra"
        else:
            return "❌ Baixa"
    except Exception:
        return "Erro"

def legacy_profissional(ativos):
    """
    Legacy Scanner Profissional (Final Corrigida)
    - Multi-timeframe: Daily + 1H + 30M
    - Filters: Vol >1.5x, Above EMA20/50, ADX>20, RSI 45-75
    - Simple scoring system per timeframe
    """
    resultados = []
    _prewarm_com_progresso(ativos, ['1d', '1h', '30m'])
    for symbol in ativos:
        try:
            # ===================== DAILY =====================
            df_daily = baixar_dados(symbol, '1d', '1y')
            if len(df_daily) < 120:
                continue

            last_daily = df_daily.iloc[-1]
            preco = safe_float(last_daily['Close'])

            # Indicators
            df_daily['EMA9'] = ta.ema(df_daily['Close'], length=9)
            df_daily['EMA20'] = ta.ema(df_daily['Close'], length=20)
            df_daily['EMA50'] = ta.ema(df_daily['Close'], length=50)
            df_daily['RSI'] = ta.rsi(df_daily['Close'], length=14)
            df_daily['ATR'] = ta.atr(df_daily['High'], df_daily['Low'], df_daily['Close'], length=14)

            macd_daily = ta.macd(df_daily['Close'])
            adx_daily = ta.adx(df_daily['High'], df_daily['Low'], df_daily['Close'], length=14)

            vol20_daily = df_daily['Volume'].rolling(20).mean()
            vol_ratio_daily = safe_float(last_daily['Volume']) / safe_float(vol20_daily.iloc[-1])

            rsi_daily = safe_float(df_daily['RSI'].iloc[-1])
            adx_val_daily = safe_float(adx_daily['ADX_14'].iloc[-1])
            macd_val_daily = safe_float(macd_daily['MACD_12_26_9'].iloc[-1])

            # Daily Score
            daily_score = 0
            if preco > safe_float(df_daily['EMA9'].iloc[-1]): daily_score += 25
            if preco > safe_float(df_daily['EMA20'].iloc[-1]): daily_score += 20
            if macd_val_daily > 0: daily_score += 20
            if adx_val_daily > 25: daily_score += 15
            if 52 < rsi_daily < 73: daily_score += 20

            # Main filters
            if vol_ratio_daily < 1.5: continue
            if preco <= safe_float(df_daily['EMA20'].iloc[-1]): continue
            if preco <= safe_float(df_daily['EMA50'].iloc[-1]): continue
            if adx_val_daily < 20: continue
            if not (45 < rsi_daily < 75): continue

            # ===================== 1H =====================
            df_1h = baixar_dados(symbol, '1h', '60d')
            if len(df_1h) < 50:
                continue

            last_1h = df_1h.iloc[-1]
            close_1h = safe_float(last_1h['Close'])

            df_1h['EMA9'] = ta.ema(df_1h['Close'], length=9)
            df_1h['EMA20'] = ta.ema(df_1h['Close'], length=20)
            df_1h['EMA50'] = ta.ema(df_1h['Close'], length=50)
            df_1h['RSI'] = ta.rsi(df_1h['Close'], length=14)

            macd_1h = ta.macd(df_1h['Close'])
            adx_1h = ta.adx(df_1h['High'], df_1h['Low'], df_1h['Close'], length=14)

            rsi_1h = safe_float(df_1h['RSI'].iloc[-1])
            adx_val_1h = safe_float(adx_1h['ADX_14'].iloc[-1])
            macd_val_1h = safe_float(macd_1h['MACD_12_26_9'].iloc[-1])

            # 1H Score
            h1_score = 0
            if close_1h > safe_float(df_1h['EMA9'].iloc[-1]): h1_score += 25
            if close_1h > safe_float(df_1h['EMA20'].iloc[-1]): h1_score += 20
            if macd_val_1h > 0: h1_score += 20
            if adx_val_1h > 25: h1_score += 15
            if 52 < rsi_1h < 73: h1_score += 20

            # ===================== 30M =====================
            df_30m = baixar_dados(symbol, '30m', '15d')
            if len(df_30m) < 50:
                continue

            last_30m = df_30m.iloc[-1]
            close_30m = safe_float(last_30m['Close'])

            df_30m['EMA9'] = ta.ema(df_30m['Close'], length=9)
            df_30m['EMA20'] = ta.ema(df_30m['Close'], length=20)
            df_30m['EMA50'] = ta.ema(df_30m['Close'], length=50)
            df_30m['RSI'] = ta.rsi(df_30m['Close'], length=14)

            macd_30m = ta.macd(df_30m['Close'])
            adx_30m = ta.adx(df_30m['High'], df_30m['Low'], df_30m['Close'], length=14)

            rsi_30m = safe_float(df_30m['RSI'].iloc[-1])
            adx_val_30m = safe_float(adx_30m['ADX_14'].iloc[-1])
            macd_val_30m = safe_float(macd_30m['MACD_12_26_9'].iloc[-1])

            # 30M Score
            m30_score = 0
            if close_30m > safe_float(df_30m['EMA9'].iloc[-1]): m30_score += 25
            if close_30m > safe_float(df_30m['EMA20'].iloc[-1]): m30_score += 20
            if macd_val_30m > 0: m30_score += 20
            if adx_val_30m > 25: m30_score += 15
            if 52 < rsi_30m < 73: m30_score += 20

            # Total Score
            score_total = daily_score + h1_score + m30_score

            # Alignment check
            daily_tend = "✅ ALTA" if preco > safe_float(df_daily['EMA20'].iloc[-1]) else "❌ BAIXA"
            h1_tend = "✅ ALTA" if close_1h > safe_float(df_1h['EMA20'].iloc[-1]) else "❌ BAIXA"
            m30_tend = "✅ ALTA" if close_30m > safe_float(df_30m['EMA20'].iloc[-1]) else "❌ BAIXA"

            alinhamento = "✅ FORTE" if (h1_tend == m30_tend == daily_tend == "✅ ALTA") else "⚠️ PARCIAL"

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço': round(preco, 2),
                'Vol Ratio': round(vol_ratio_daily, 2),
                'RSI Daily': round(rsi_daily, 1),
                'ADX Daily': round(adx_val_daily, 1),
                'RSI 1H': round(rsi_1h, 1),
                'ADX 1H': round(adx_val_1h, 1),
                'RSI 30M': round(rsi_30m, 1),
                'ADX 30M': round(adx_val_30m, 1),
                'Score Daily': daily_score,
                'Score 1H': h1_score,
                'Score 30M': m30_score,
                'Score Total': score_total,
                'Alinhamento': alinhamento,
            })
        except Exception:
            continue
    return pd.DataFrame(resultados)

def legacy_intraday_swing(ativos):
    """
    Legacy Intraday/Swing Curto Prazo
    - More rigorous filters: Daily vol >1.7x, liquidity >8M, ADX≥22, RSI 47-73
    - Weighted score: daily * 1.6 + 1H + 30M
    - EMA9-based analysis
    """
    resultados = []
    _prewarm_com_progresso(ativos, ['1d', '1h', '30m'])
    for symbol in ativos:
        try:
            # ===================== DAILY (Base) =====================
            df_d = baixar_dados(symbol, '1d', '1y')
            if len(df_d) < 150:
                continue

            last_d = df_d.iloc[-1]
            preco = safe_float(last_d['Close'])

            df_d['EMA9'] = ta.ema(df_d['Close'], length=9)
            df_d['EMA20'] = ta.ema(df_d['Close'], length=20)
            df_d['EMA50'] = ta.ema(df_d['Close'], length=50)
            df_d['RSI'] = ta.rsi(df_d['Close'], length=14)
            df_d['ATR'] = ta.atr(df_d['High'], df_d['Low'], df_d['Close'], length=14)

            macd_d = ta.macd(df_d['Close'])
            adx_d = ta.adx(df_d['High'], df_d['Low'], df_d['Close'], length=14)

            vol20_d = df_d['Volume'].rolling(20).mean()
            vol_ratio_d = safe_float(last_d['Volume']) / safe_float(vol20_d.iloc[-1])
            vol_medio_d = safe_float(vol20_d.iloc[-1])

            rsi_d = safe_float(df_d['RSI'].iloc[-1])
            adx_d_val = safe_float(adx_d['ADX_14'].iloc[-1])
            macd_d_val = safe_float(macd_d['MACD_12_26_9'].iloc[-1])

            # Rigorous filters
            if vol_ratio_d < 1.7: continue
            if vol_medio_d < 8_000_000: continue
            if adx_d_val < 22: continue
            if not (47 < rsi_d < 73): continue
            if preco <= safe_float(df_d['EMA50'].iloc[-1]): continue

            # Daily Score
            daily_score = 0
            if preco > safe_float(df_d['EMA9'].iloc[-1]): daily_score += 25
            if preco > safe_float(df_d['EMA20'].iloc[-1]): daily_score += 25
            if macd_d_val > 0: daily_score += 15
            if adx_d_val > 25: daily_score += 20
            if 48 < rsi_d < 74: daily_score += 15

            # ===================== 1H (Main Setup) =====================
            df_h = baixar_dados(symbol, '1h', '60d')
            if len(df_h) < 100:
                continue

            last_h = df_h.iloc[-1]
            close_h = safe_float(last_h['Close'])

            df_h['EMA9'] = ta.ema(df_h['Close'], length=9)
            df_h['EMA20'] = ta.ema(df_h['Close'], length=20)
            df_h['EMA50'] = ta.ema(df_h['Close'], length=50)
            df_h['RSI'] = ta.rsi(df_h['Close'], length=14)

            macd_h = ta.macd(df_h['Close'])
            adx_h = ta.adx(df_h['High'], df_h['Low'], df_h['Close'], length=14)

            vol20_h = df_h['Volume'].rolling(20).mean()
            vol_ratio_h = safe_float(last_h['Volume']) / safe_float(vol20_h.iloc[-1])

            rsi_h = safe_float(df_h['RSI'].iloc[-1])
            adx_h_val = safe_float(adx_h['ADX_14'].iloc[-1])
            macd_h_val = safe_float(macd_h['MACD_12_26_9'].iloc[-1])

            # 1H Score
            h_score = 0
            if close_h > safe_float(df_h['EMA9'].iloc[-1]): h_score += 25
            if close_h > safe_float(df_h['EMA20'].iloc[-1]): h_score += 25
            if macd_h_val > 0: h_score += 15
            if adx_h_val > 25: h_score += 20
            if 48 < rsi_h < 74: h_score += 15

            # ===================== 30M (Timing) =====================
            df_30 = baixar_dados(symbol, '30m', '15d')
            score_30 = 0
            if len(df_30) > 200:
                df_30['EMA9'] = ta.ema(df_30['Close'], length=9)
                df_30['RSI'] = ta.rsi(df_30['Close'], length=14)
                if preco > safe_float(df_30['EMA9'].iloc[-1]): score_30 += 25
                if safe_float(df_30['RSI'].iloc[-1]) > 52: score_30 += 20

            # Weighted Total Score
            score_total = (daily_score * 1.6) + h_score + score_30

            alinhamento = "✅ FORTE" if (adx_d_val > 25 and adx_h_val > 23) else "⚠️ PARCIAL"

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço': round(preco, 2),
                'Vol Ratio D': round(vol_ratio_d, 2),
                'Vol Ratio H': round(vol_ratio_h, 2),
                'RSI Daily': round(rsi_d, 1),
                'ADX Daily': round(adx_d_val, 1),
                'RSI 1H': round(rsi_h, 1),
                'ADX 1H': round(adx_h_val, 1),
                'Score 30M': score_30,
                'Score Total': round(score_total, 0),
                'Alinhamento': alinhamento,
            })
        except Exception:
            continue
    return pd.DataFrame(resultados)

def legacy_expandida(ativos):
    """
    Legacy Expandida (Mid + Small Caps Voláteis)
    - Expanded asset list with relaxed volume filter (≥2.5M)
    - Multi-timeframe confluência analysis
    - Confluência status: Fraca/Parcial/Boa/Excelente
    """
    resultados = []
    # Usa a lista de ativos fornecida
    ativos_exp = ativos
    _prewarm_com_progresso(ativos_exp, ['1d', '1h', '30m'])

    for symbol in ativos_exp:
        try:
            # ===================== DAILY =====================
            df = baixar_dados(symbol, '1d', '1y')
            if len(df) < 120:
                continue

            last = df.iloc[-1]
            prev = df.iloc[-2]
            preco = safe_float(last['Close'])

            df['EMA9'] = ta.ema(df['Close'], length=9)
            df['EMA20'] = ta.ema(df['Close'], length=20)
            df['EMA50'] = ta.ema(df['Close'], length=50)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

            macd = ta.macd(df['Close'])
            adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)

            df['Vol20'] = df['Volume'].rolling(20).mean()
            vol_ratio = safe_float(last['Volume']) / safe_float(df['Vol20'].iloc[-1])
            vol_medio = safe_float(df['Vol20'].iloc[-1])

            # Relaxed filters for expanded version
            if vol_ratio < 1.5: continue
            if vol_medio < 2_500_000: continue
            if preco <= safe_float(df['EMA20'].iloc[-1]): continue
            if preco <= safe_float(df['EMA50'].iloc[-1]): continue

            adx_val = safe_float(adx['ADX_14'].iloc[-1])
            if adx_val < 20: continue

            rsi = safe_float(df['RSI'].iloc[-1])
            if rsi > 75 or rsi < 45: continue

            # Daily Score
            score = 0
            if preco > safe_float(df['EMA9'].iloc[-1]): score += 20
            if safe_float(macd['MACD_12_26_9'].iloc[-1]) > 0: score += 20
            if vol_ratio > 2.5: score += 20
            if adx_val > 25: score += 15
            if 55 < rsi < 72: score += 15
            if safe_float(df['ATR'].iloc[-1]) / preco < 0.045: score += 10

            # ===================== 1H (Principal) =====================
            df_1h = baixar_dados(symbol, '1h', '75d')
            if len(df_1h) < 80:
                continue

            df_1h['EMA20'] = ta.ema(df_1h['Close'], length=20)
            df_1h['EMA50'] = ta.ema(df_1h['Close'], length=50)
            df_1h['RSI'] = ta.rsi(df_1h['Close'], length=14)
            macd_1h_df = ta.macd(df_1h['Close'])
            adx_1h_df = ta.adx(df_1h['High'], df_1h['Low'], df_1h['Close'], length=14)

            last_1h = df_1h.iloc[-1]
            close_1h = safe_float(last_1h['Close'])
            ema20_1h = safe_float(df_1h['EMA20'].iloc[-1])
            ema50_1h = safe_float(df_1h['EMA50'].iloc[-1])

            acima_ema20_50_1h = close_1h > ema20_1h and close_1h > ema50_1h
            rsi_1h = safe_float(df_1h['RSI'].iloc[-1])
            macd_1h = safe_float(macd_1h_df['MACD_12_26_9'].iloc[-1])
            adx_1h = safe_float(adx_1h_df['ADX_14'].iloc[-1])

            # Confluência 1H
            if acima_ema20_50_1h and adx_1h > 20 and 50 < rsi_1h < 75 and macd_1h > 0:
                confluencia_1h = "Boa ✅"
                tendencia_1h = "Alta forte"
            elif acima_ema20_50_1h:
                confluencia_1h = "Parcial"
                tendencia_1h = "Alta moderada"
            else:
                tendencia_1h = "Consolidação / Baixa"
                confluencia_1h = "Fraca"

            # ===================== 30M (Auxiliar) =====================
            df_30m = baixar_dados(symbol, '30m', '45d')
            if len(df_30m) < 150:
                continue

            df_30m['EMA20'] = ta.ema(df_30m['Close'], length=20)
            df_30m['EMA50'] = ta.ema(df_30m['Close'], length=50)
            df_30m['RSI'] = ta.rsi(df_30m['Close'], length=14)
            macd_30m_df = ta.macd(df_30m['Close'])
            adx_30m_df = ta.adx(df_30m['High'], df_30m['Low'], df_30m['Close'], length=14)

            last_30m = df_30m.iloc[-1]
            close_30m = safe_float(last_30m['Close'])
            ema20_30m = safe_float(df_30m['EMA20'].iloc[-1])
            ema50_30m = safe_float(df_30m['EMA50'].iloc[-1])

            acima_ema20_50_30m = close_30m > ema20_30m and close_30m > ema50_30m
            rsi_30m = safe_float(df_30m['RSI'].iloc[-1])
            macd_30m = safe_float(macd_30m_df['MACD_12_26_9'].iloc[-1])
            adx_30m = safe_float(adx_30m_df['ADX_14'].iloc[-1])

            # Confluência 30M
            if acima_ema20_50_30m and adx_30m > 20 and 50 < rsi_30m < 75 and macd_30m > 0:
                confluencia_30m = "Boa ✅"
                tendencia_30m = "Alta forte"
            elif acima_ema20_50_30m:
                confluencia_30m = "Parcial"
                tendencia_30m = "Alta moderada"
            else:
                tendencia_30m = "Consolidação / Baixa"
                confluencia_30m = "Fraca"

            # Confluência Geral
            if confluencia_1h == "Boa ✅" and confluencia_30m == "Boa ✅":
                confluencia_geral = "Excelente ✅✅"
            elif confluencia_1h == "Boa ✅" or confluencia_30m == "Boa ✅":
                confluencia_geral = "Boa ✅"
            elif confluencia_1h == "Parcial" and confluencia_30m == "Parcial":
                confluencia_geral = "Parcial"
            else:
                confluencia_geral = "Fraca / Sem confluência"

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço': round(preco, 2),
                'Vol Ratio': round(vol_ratio, 2),
                'Vol Médio (M)': round(vol_medio / 1_000_000, 1),
                'RSI Daily': round(rsi, 1),
                'ADX Daily': round(adx_val, 1),
                'RSI 1H': round(rsi_1h, 1),
                'ADX 1H': round(adx_1h, 1),
                'RSI 30M': round(rsi_30m, 1),
                'ADX 30M': round(adx_30m, 1),
                'Confluência 1H': confluencia_1h,
                'Confluência 30M': confluencia_30m,
                'Confluência Geral': confluencia_geral,
                'Score Diário': score,
                'Tendência 1H': tendencia_1h,
                'Tendência 30M': tendencia_30m,
            })
        except Exception:
            continue
    return pd.DataFrame(resultados)

def scanner_swing_hibrido(ativos, adx_min, rsi_min, rsi_max, vol_ratio_min, vol_medio_min=300_000):
    """
    Scanner Swing Híbrido (Daily + 1H)
    - Análise Daily com thresholds dos sliders
    - Confirmação de tendência 1H
    - Tríade básica
    """
    resultados = []
    _prewarm_com_progresso(ativos, ['1d', '1h', '30m'])
    for symbol in ativos:
        try:
            df = baixar_dados(symbol, '1d', '1y')
            if len(df) < 120:
                continue

            analise = analisar_ativo_completo(df, adx_min, rsi_min, rsi_max, vol_ratio_min)
            if analise is None:
                continue

            # Filtros Daily
            if analise['preco'] <= analise['ema20']:
                continue
            if analise['adx'] < adx_min:
                continue
            if not (rsi_min <= analise['rsi'] <= rsi_max):
                continue
            if analise['vol_ratio'] < vol_ratio_min:
                continue
            if analise['vol_medio'] < vol_medio_min:
                continue
            if not analise['adx_rising']:
                continue

            # Confirmação 1H
            df_1h = baixar_dados(symbol, '1h', '60d')
            tendencia_1h = analisar_tendencia_tf(df_1h)

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço': round(analise['preco'], 2),
                'Vol Ratio': round(analise['vol_ratio'], 2),
                'RSI': round(analise['rsi'], 1),
                'ADX': round(analise['adx'], 1),
                'ADX Rising': '✅' if analise['adx_rising'] else '❌',
                '+DI': round(analise['plus_di'], 1),
                '-DI': round(analise['minus_di'], 1),
                'Tríade': analise['triade_status'],
                'Saída': analise['sinal_saida'],
                'Score': analise['score'],
            })
        except Exception:
            continue
    return pd.DataFrame(resultados)

def scanner_swing_rr(ativos, adx_min, rsi_min, rsi_max, vol_ratio_min, vol_medio_min=300_000):
    """
    Scanner Swing RR (Daily + ATR targets)
    - Mesma base do Híbrido
    - Stop Loss = Preço - ATR * 1.8
    - Alvo 1:2 e 1:3 com ATR
    - Colunas de risco/retorno
    """
    resultados = []
    _prewarm_com_progresso(ativos, ['1d', '1h', '30m'])
    for symbol in ativos:
        try:
            df = baixar_dados(symbol, '1d', '1y')
            if len(df) < 120:
                continue

            analise = analisar_ativo_completo(df, adx_min, rsi_min, rsi_max, vol_ratio_min)
            if analise is None:
                continue

            # Filtros Daily
            if analise['preco'] <= analise['ema20']:
                continue
            if analise['adx'] < adx_min:
                continue
            if not (rsi_min <= analise['rsi'] <= rsi_max):
                continue
            if analise['vol_ratio'] < vol_ratio_min:
                continue
            if analise['vol_medio'] < vol_medio_min:
                continue
            if not analise['adx_rising']:
                continue

            # Cálculos de RR
            preco = analise['preco']
            atr = analise['atr']
            stop = preco - (atr * 1.8)
            risco = preco - stop
            alvo_2 = preco + (risco * 2)
            alvo_3 = preco + (risco * 3)
            rr_ratio = round((alvo_2 - preco) / risco, 1) if risco > 0 else 0

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço': round(preco, 2),
                'Vol Ratio': round(analise['vol_ratio'], 2),
                'RSI': round(analise['rsi'], 1),
                'ADX': round(analise['adx'], 1),
                'ADX Rising': '✅' if analise['adx_rising'] else '❌',
                '+DI': round(analise['plus_di'], 1),
                '-DI': round(analise['minus_di'], 1),
                'Tríade': analise['triade_status'],
                'Stop': round(stop, 2),
                'Alvo 1:2': round(alvo_2, 2),
                'Alvo 1:3': round(alvo_3, 2),
                'RR': rr_ratio,
                'Saída': analise['sinal_saida'],
                'Score': analise['score'],
            })
        except Exception:
            continue
    return pd.DataFrame(resultados)

def scanner_swing_profissional(ativos, adx_min, rsi_min, rsi_max, vol_ratio_min, vol_medio_min=300_000):
    """
    Scanner Swing Profissional (Daily + 1H + 30M)
    - Análise multi-timeframe completa
    - ADX Rising obrigatório
    - +DI > -DI obrigatório
    - Tríade completa exigida
    - Filtros mais rigorosos
    """
    resultados = []
    _prewarm_com_progresso(ativos, ['1d', '1h', '30m'])
    for symbol in ativos:
        try:
            df = baixar_dados(symbol, '1d', '1y')
            if len(df) < 120:
                continue

            analise = analisar_ativo_completo(df, adx_min, rsi_min, rsi_max, vol_ratio_min)
            if analise is None:
                continue

            # Filtros Daily (mais rigorosos)
            if analise['preco'] <= analise['ema50']:
                continue
            if analise['adx'] < adx_min:
                continue
            if not (rsi_min <= analise['rsi'] <= rsi_max):
                continue
            if analise['vol_ratio'] < vol_ratio_min:
                continue
            if analise['vol_medio'] < vol_medio_min:
                continue

            # ADX Rising obrigatório
            if not analise['adx_rising']:
                continue

            # +DI > -DI obrigatório
            if analise['plus_di'] <= analise['minus_di']:
                continue

            # Tríade completa obrigatória
            if not analise['triade_ok']:
                continue

            # Análise 1H
            df_1h = baixar_dados(symbol, '1h', '60d')
            tendencia_1h = analisar_tendencia_tf(df_1h)

            # Análise 30M
            df_30m = baixar_dados(symbol, '30m', '15d')
            tendencia_30m = analisar_tendencia_tf(df_30m)

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço': round(analise['preco'], 2),
                'Vol Ratio': round(analise['vol_ratio'], 2),
                'RSI': round(analise['rsi'], 1),
                'ADX': round(analise['adx'], 1),
                'ADX Rising': '✅',
                '+DI': round(analise['plus_di'], 1),
                '-DI': round(analise['minus_di'], 1),
                'Tríade': analise['triade_status'],
                'Tendência 1H': tendencia_1h,
                'Tendência 30M': tendencia_30m,
                'Saída': analise['sinal_saida'],
                'Score': analise['score'],
            })
        except Exception:
            continue
    return pd.DataFrame(resultados)

def scanner_swing_expandido(adx_min, rsi_min, rsi_max, vol_ratio_min, vol_medio_min=300_000, ativos=None):
    """
    Scanner Swing Expandido (Mid + Small Caps)
    - Usa lista universal por padrão (ou lista fornecida)
    - Volume médio mínimo controlado pelo perfil (vol_medio_min)
    - Tríade completa
    """
    resultados = []
    # Usa a lista fornecida ou a lista universal completa
    if ativos is None:
        ativos = ATIVOS_B3_AMPLIADO
    _prewarm_com_progresso(ativos, ['1d', '1h', '30m'])

    for symbol in ativos:
        try:
            df = baixar_dados(symbol, '1d', '1y')
            if len(df) < 120:
                continue

            analise = analisar_ativo_completo(df, adx_min, rsi_min, rsi_max, vol_ratio_min)
            if analise is None:
                continue

            # Filtros Daily
            if analise['preco'] <= analise['ema20']:
                continue
            if analise['adx'] < adx_min:
                continue
            if not (rsi_min <= analise['rsi'] <= rsi_max):
                continue
            if analise['vol_ratio'] < vol_ratio_min:
                continue
            if not analise['adx_rising']:
                continue

            # Vol medio mínimo controlado pelo perfil
            if analise['vol_medio'] < vol_medio_min:
                continue

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço': round(analise['preco'], 2),
                'Vol Ratio': round(analise['vol_ratio'], 2),
                'RSI': round(analise['rsi'], 1),
                'ADX': round(analise['adx'], 1),
                'ADX Rising': '✅' if analise['adx_rising'] else '❌',
                '+DI': round(analise['plus_di'], 1),
                '-DI': round(analise['minus_di'], 1),
                'Tríade': analise['triade_status'],
                'Saída': analise['sinal_saida'],
                'Score': analise['score'],
            })
        except Exception:
            continue
    return pd.DataFrame(resultados)

def scanner_swing_trade_fusion(ativos, adx_min, rsi_min, rsi_max, vol_ratio_min, vol_medio_min=300_000):
    """
    🔥 Swing Trade Fusion Scanner
    Combines Legacy's granular multi-timeframe analysis (RSI/ADX/MACD per D/1H/30M,
    per-TF scoring, 4-level confluence) with Evolved's advanced features (Tríade,
    DI+/DI-, ADX Rising, ATR Stop/Targets, exit signals, slider control).

    Weighted Score: Daily×0.30 + 1H×0.40 + 30M×0.30 (1H = main TF)
    """
    resultados = []
    _prewarm_com_progresso(ativos, ['1d', '1h', '30m'])
    for symbol in ativos:
        try:
            # ===================== DAILY =====================
            df_d = baixar_dados(symbol, '1d', '1y')
            if len(df_d) < 120:
                continue

            last_d = df_d.iloc[-1]
            preco = safe_float(last_d['Close'])

            # Indicators
            df_d['EMA9'] = ta.ema(df_d['Close'], length=9)
            df_d['EMA20'] = ta.ema(df_d['Close'], length=20)
            df_d['EMA50'] = ta.ema(df_d['Close'], length=50)
            df_d['RSI'] = ta.rsi(df_d['Close'], length=14)
            df_d['ATR'] = ta.atr(df_d['High'], df_d['Low'], df_d['Close'], length=14)

            macd_d = ta.macd(df_d['Close'])
            adx_d = ta.adx(df_d['High'], df_d['Low'], df_d['Close'], length=14)

            vol20_d = df_d['Volume'].rolling(20).mean()
            vol_ratio_d = safe_float(last_d['Volume']) / safe_float(vol20_d.iloc[-1]) if safe_float(vol20_d.iloc[-1]) > 0 else 0
            vol_medio_d = safe_float(vol20_d.iloc[-1])

            rsi_d = safe_float(df_d['RSI'].iloc[-1])
            adx_d_val = safe_float(adx_d['ADX_14'].iloc[-1])
            plus_di_d = safe_float(adx_d['DMP_14'].iloc[-1])
            minus_di_d = safe_float(adx_d['DMN_14'].iloc[-1])
            macd_d_val = safe_float(macd_d['MACD_12_26_9'].iloc[-1])
            atr_d = safe_float(df_d['ATR'].iloc[-1])

            # ADX Rising (Daily)
            adx_d_past = safe_float(adx_d['ADX_14'].iloc[-ADX_RISING_PERIODS]) if len(adx_d) > ADX_RISING_PERIODS else adx_d_val
            adx_rising_d = adx_d_val > adx_d_past

            # ---- DAILY FILTERS ----
            if preco <= safe_float(df_d['EMA20'].iloc[-1]):
                continue
            if preco <= safe_float(df_d['EMA50'].iloc[-1]):
                continue
            if adx_d_val < adx_min:
                continue
            if not (rsi_min <= rsi_d <= rsi_max):
                continue
            if vol_ratio_d < vol_ratio_min:
                continue
            if vol_medio_d < vol_medio_min:
                continue

            # ---- DAILY SCORE (max 100) ----
            score_d = 0
            if preco > safe_float(df_d['EMA9'].iloc[-1]): score_d += 15
            if preco > safe_float(df_d['EMA20'].iloc[-1]): score_d += 15
            if preco > safe_float(df_d['EMA50'].iloc[-1]): score_d += 10
            if macd_d_val > 0: score_d += 15
            if adx_d_val >= adx_min: score_d += 15
            if rsi_min <= rsi_d <= rsi_max: score_d += 15
            if adx_rising_d: score_d += 10
            if plus_di_d > minus_di_d: score_d += 5

            # Tríade Daily
            triade_d = (adx_d_val >= adx_min) and (rsi_min <= rsi_d <= rsi_max) and (vol_ratio_d >= vol_ratio_min)

            # ===================== 1H (Main Timeframe) =====================
            df_h = baixar_dados(symbol, '1h', '60d')
            if len(df_h) < 50:
                continue

            last_h = df_h.iloc[-1]
            close_h = safe_float(last_h['Close'])

            df_h['EMA9'] = ta.ema(df_h['Close'], length=9)
            df_h['EMA20'] = ta.ema(df_h['Close'], length=20)
            df_h['EMA50'] = ta.ema(df_h['Close'], length=50)
            df_h['RSI'] = ta.rsi(df_h['Close'], length=14)

            macd_h = ta.macd(df_h['Close'])
            adx_h = ta.adx(df_h['High'], df_h['Low'], df_h['Close'], length=14)

            vol20_h = df_h['Volume'].rolling(20).mean()
            vol_ratio_h = safe_float(last_h['Volume']) / safe_float(vol20_h.iloc[-1]) if safe_float(vol20_h.iloc[-1]) > 0 else 0

            rsi_h = safe_float(df_h['RSI'].iloc[-1])
            adx_h_val = safe_float(adx_h['ADX_14'].iloc[-1])
            plus_di_h = safe_float(adx_h['DMP_14'].iloc[-1])
            minus_di_h = safe_float(adx_h['DMN_14'].iloc[-1])
            macd_h_val = safe_float(macd_h['MACD_12_26_9'].iloc[-1])

            # ADX Rising (1H)
            adx_h_past = safe_float(adx_h['ADX_14'].iloc[-ADX_RISING_PERIODS]) if len(adx_h) > ADX_RISING_PERIODS else adx_h_val
            adx_rising_h = adx_h_val > adx_h_past

            # ---- 1H SCORE (max 100) ----
            score_h = 0
            if close_h > safe_float(df_h['EMA9'].iloc[-1]): score_h += 15
            if close_h > safe_float(df_h['EMA20'].iloc[-1]): score_h += 15
            if close_h > safe_float(df_h['EMA50'].iloc[-1]): score_h += 10
            if macd_h_val > 0: score_h += 15
            if adx_h_val >= adx_min: score_h += 15
            if rsi_min <= rsi_h <= rsi_max: score_h += 15
            if adx_rising_h: score_h += 10
            if plus_di_h > minus_di_h: score_h += 5

            # Tríade 1H
            triade_h = (adx_h_val >= adx_min) and (rsi_min <= rsi_h <= rsi_max) and (vol_ratio_h >= vol_ratio_min)

            # ===================== 30M (Timing Timeframe) =====================
            df_30 = baixar_dados(symbol, '30m', '30d')
            if len(df_30) < 50:
                continue

            last_30 = df_30.iloc[-1]
            close_30 = safe_float(last_30['Close'])

            df_30['EMA9'] = ta.ema(df_30['Close'], length=9)
            df_30['EMA20'] = ta.ema(df_30['Close'], length=20)
            df_30['EMA50'] = ta.ema(df_30['Close'], length=50)
            df_30['RSI'] = ta.rsi(df_30['Close'], length=14)

            macd_30 = ta.macd(df_30['Close'])
            adx_30 = ta.adx(df_30['High'], df_30['Low'], df_30['Close'], length=14)

            rsi_30 = safe_float(df_30['RSI'].iloc[-1])
            adx_30_val = safe_float(adx_30['ADX_14'].iloc[-1])
            macd_30_val = safe_float(macd_30['MACD_12_26_9'].iloc[-1])

            # ---- 30M SCORE (max 70) ----
            score_30 = 0
            if close_30 > safe_float(df_30['EMA9'].iloc[-1]): score_30 += 15
            if close_30 > safe_float(df_30['EMA20'].iloc[-1]): score_30 += 15
            if close_30 > safe_float(df_30['EMA50'].iloc[-1]): score_30 += 10
            if macd_30_val > 0: score_30 += 15
            if adx_30_val >= adx_min: score_30 += 15

            # ===================== CONFLUENCE (4-level) =====================
            # Check per-TF alignment (price > EMA20, ADX > threshold, RSI in zone, MACD > 0)
            def tf_aligned(price, ema20, adx_val, rsi_val, macd_val):
                return price > ema20 and adx_val > 20 and rsi_min <= rsi_val <= rsi_max and macd_val > 0

            aligned_h = tf_aligned(close_h, safe_float(df_h['EMA20'].iloc[-1]), adx_h_val, rsi_h, macd_h_val)
            aligned_30 = tf_aligned(close_30, safe_float(df_30['EMA20'].iloc[-1]), adx_30_val, rsi_30, macd_30_val)
            aligned_d = tf_aligned(preco, safe_float(df_d['EMA20'].iloc[-1]), adx_d_val, rsi_d, macd_d_val)

            if aligned_d and aligned_h and aligned_30:
                confluencia = "Excelente ✅✅"
            elif aligned_h and aligned_30:
                confluencia = "Boa ✅"
            elif aligned_h or aligned_30:
                confluencia = "Parcial ⚠️"
            else:
                confluencia = "Fraca ❌"

            # ===================== WEIGHTED TOTAL SCORE =====================
            # Normalize: D max=100, H max=100, 30M max=70→scaled to 100
            score_30_normalized = (score_30 / 70) * 100 if score_30 > 0 else 0
            score_total = round((score_d * 0.30) + (score_h * 0.40) + (score_30_normalized * 0.30))

            # ===================== RISK MANAGEMENT (ATR-based) =====================
            stop = preco - (atr_d * 1.8)
            risco = preco - stop
            alvo_2 = preco + (risco * 2)
            alvo_3 = preco + (risco * 3)

            # ===================== EXIT SIGNALS =====================
            sinais_saida = []
            if not adx_rising_d:
                sinais_saida.append("⚠️ ADX↓D")
            if not adx_rising_h:
                sinais_saida.append("⚠️ ADX↓1H")
            if rsi_d > rsi_max:
                sinais_saida.append("⚠️ RSI↑D")
            if rsi_h > rsi_max:
                sinais_saida.append("⚠️ RSI↑1H")
            sinal_saida = " | ".join(sinais_saida) if sinais_saida else "✅"

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço': round(preco, 2),
                'Stop': round(stop, 2),
                'Alvo 1:2': round(alvo_2, 2),
                'Alvo 1:3': round(alvo_3, 2),
                'Vol Ratio': round(vol_ratio_d, 2),
                'RSI D': round(rsi_d, 1),
                'RSI 1H': round(rsi_h, 1),
                'RSI 30M': round(rsi_30, 1),
                'ADX D': round(adx_d_val, 1),
                'ADX 1H': round(adx_h_val, 1),
                'ADX 30M': round(adx_30_val, 1),
                'ADX Rising D': '✅' if adx_rising_d else '❌',
                'ADX Rising 1H': '✅' if adx_rising_h else '❌',
                '+DI': round(plus_di_d, 1),
                '-DI': round(minus_di_d, 1),
                'Tríade D': '✅' if triade_d else '⚠️',
                'Tríade 1H': '✅' if triade_h else '⚠️',
                'Score D': score_d,
                'Score 1H': score_h,
                'Score 30M': score_30,
                'Score Total': score_total,
                'Confluência': confluencia,
                'Saída': sinal_saida,
            })
        except Exception:
            continue
    return pd.DataFrame(resultados)

# === ABERTURA ===

def _candle_por_hora(df_dia, hora, minuto):
    """Retorna o último candle do dia cuja ABERTURA seja hora:minuto (hora B3),
    ou None se não existir.

    Substitui o acesso posicional (iloc[0]/iloc[1]): em vez de *assumir* que o
    primeiro candle do dia é a abertura das 10:00, TRAVA de fato no horário real
    da B3 — robusto a gaps, candles de leilão ou respostas truncadas do Yahoo.
    Assim o pico de volume (RVOL) é sempre medido no verdadeiro candle de abertura."""
    if df_dia is None or df_dia.empty:
        return None
    sub = df_dia[(df_dia.index.hour == hora) & (df_dia.index.minute == minuto)]
    return sub.iloc[-1] if not sub.empty else None

def coletar_candidatos(ativos, min_ratio, max_ratio):
    """Baixa os dados UMA única vez e calcula todas as métricas dos ativos que
    passam no filtro de estabilização (Decay Ratio) e na tendência de alta.

    Usa os limites mais permissivos (perfil Agressivo: RVOL >= 0.8 e Vol >= R$ 300 mil)
    apenas para reunir todos os candidatos possíveis. A classificação por perfil de
    risco (cascata Conservador > Moderado > Agressivo) fica a cargo de
    `classificar_perfil`, evitando baixar os mesmos dados 3x."""
    hoje = data_layer.session_today()
    if hoje is None:
        return pd.DataFrame()   # fim de semana — sem pregão para analisar hoje

    resultados = []

    # Progresso gerenciado pelo worker

    # Limite mais permissivo (Agressivo) -> não descarta candidatos antes da filtragem por perfil
    min_vol_fin_floor = 300_000
    min_rvol_floor = 0.8

    _prewarm_com_progresso(ativos, ['15m'])

    total = len(ativos)
    for i, symbol in enumerate(ativos):

        df = baixar_dados_15m(symbol)
        if df is None or df.empty or len(df) < 10:
            continue

        try:
            # ESTRITAMENTE o dia de HOJE (pregão corrente). Se a sessão de hoje ainda
            # não gerou candles (antes da abertura / dados defasados), df_hoje fica
            # vazio e o ativo é pulado — nunca cai para o pregão anterior.
            df_hoje = df[df.index.date == hoje]

            # Precisamos de pelo menos 2 candles hoje (10:00 e 10:15)
            if len(df_hoje) < 2:
                continue

            # Trava nos candles de abertura por HORÁRIO REAL (10:00 e 10:15), e não
            # por posição. Garante que o pico de volume seja medido sempre no candle
            # de abertura da B3, mesmo se o Yahoo devolver gaps/leilão no início.
            c1 = _candle_por_hora(df_hoje, 10, 0)   # abertura (10:00)
            c2 = _candle_por_hora(df_hoje, 10, 15)  # 10:15
            if c1 is None or c2 is None:
                # Pregão cedo demais: ainda não fechou o candle das 10:15.
                continue
            atual = df_hoje.iloc[-1]  # candle mais recente do dia

            # Volume Financeiro do C1 (Preço Fechamento * Quantidade)
            vol_fin_c1 = c1['Close'] * c1['Volume']

            if vol_fin_c1 < min_vol_fin_floor:
                continue

            vol_c1 = float(c1['Volume'])
            vol_c2 = float(c2['Volume'])

            if vol_c1 == 0:
                continue

            decay_ratio = vol_c2 / vol_c1

            # RVOL do C1 (abertura) — confirmador institucional de pico de volume.
            # A média-base é lida NA LINHA da abertura (e não no último candle, que
            # mudaria conforme o horário em que o scanner é rodado). Assim o RVOL e o
            # perfil de risco ficam TRAVADOS no pregão: só dependem do dia.
            df['Vol_Media_20'] = df['Volume'].rolling(20).mean()
            pos_c1 = df.index.get_loc(c1.name)
            # candle imediatamente ANTERIOR à abertura → média do volume "normal" pré-abertura
            vol_media = float(df['Vol_Media_20'].iloc[pos_c1 - 1]) if pos_c1 > 0 else 0.0
            rvol = vol_c1 / vol_media if vol_media > 0 else 0

            if not (min_ratio <= decay_ratio <= max_ratio and rvol >= min_rvol_floor):
                continue

            # Calcula tendência usando os dados dos 5 dias inteiros
            df['EMA9'] = ta.ema(df['Close'], length=9)
            df['EMA20'] = ta.ema(df['Close'], length=20)

            close_atual = float(atual['Close'])
            ema9 = float(df['EMA9'].iloc[-1])
            ema20 = float(df['EMA20'].iloc[-1])

            tendencia = "✅ ALTA" if close_atual > ema9 else "❌ BAIXA"

            # O usuário solicitou ver APENAS movimentos de alta
            if tendencia == "❌ BAIXA":
                continue

            # Variação do dia (do fechamento do C1 pro Atual, pra saber se andou)
            var_percentual = ((close_atual - c1['Close']) / c1['Close']) * 100

            # Cálculo da VWAP Intraday do dia atual
            df_hoje_calc = df_hoje.copy()
            df_hoje_calc['Typical_Price'] = (df_hoje_calc['High'] + df_hoje_calc['Low'] + df_hoje_calc['Close']) / 3
            df_hoje_calc['Vol_x_TP'] = df_hoje_calc['Typical_Price'] * df_hoje_calc['Volume']
            vol_total_dia = df_hoje_calc['Volume'].sum()
            vwap = df_hoje_calc['Vol_x_TP'].sum() / vol_total_dia if vol_total_dia > 0 else close_atual

            # Definir Setup sugerido (Proximidade das médias = Pullback, Longe = Rompimento)
            # Consideramos "perto" se o preço estiver a menos de 0.5% da VWAP ou da EMA9
            dist_vwap = abs(close_atual - vwap) / close_atual
            dist_ema9 = abs(close_atual - ema9) / close_atual

            if dist_vwap <= 0.005 or dist_ema9 <= 0.005:
                setup = "🧲 Pullback (Média/VWAP)"
            else:
                setup = "🚀 Rompimento (Máxima)"

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço Atual': round(close_atual, 2),
                'Setup / Gatilho': setup,
                'Tendência (15m)': tendencia,
                'Volume Ratio (RVOL)': round(rvol, 2),
                'Ratio Queda (10:15/10:00)': round(decay_ratio, 2),
                'Vol Financeiro C1 (R$ Mi)': round(vol_fin_c1 / 1_000_000, 2),
                'Var. desde Abertura (%)': round(var_percentual, 2),
                'Hora Últ. Candle': df_hoje.index[-1].strftime('%H:%M')
            })
        except Exception:
            continue

    return pd.DataFrame(resultados)

def classificar_perfil(df, perfis):
    """Atribui cada ativo ao perfil MAIS restritivo que ele atende (cascata).
    Conservador > Moderado > Agressivo. Cada ativo recebe exatamente um perfil,
    eliminando a repetição entre blocos. `min_vol` vem em R$ e a coluna está em
    R$ Mi, por isso a conversão."""
    if df.empty:
        return df
    df = df.copy()

    def qual(row):
        for p in perfis:  # perfis ordenado do mais restritivo ao mais brandoso
            if (row['Volume Ratio (RVOL)'] >= p['min_rvol'] and
                    row['Vol Financeiro C1 (R$ Mi)'] >= p['min_vol'] / 1_000_000):
                return p['nome']
        return None  # não atende nem ao Agressivo (candidato coletado só pelo floor de RVOL)

    df['perfil'] = df.apply(qual, axis=1)
    return df

def _e_vela_alta_forte(vela):
    """Vela de alta FORTE: verde (close > open) E fecha no terço superior do próprio
    range ((close-low) >= 0.67*(high-low)) — pouca sombra superior, corpo dominante,
    compradores no controle."""
    if vela is None:
        return False
    o, h, l, c = vela['Open'], vela['High'], vela['Low'], vela['Close']
    if pd.isna(o) or pd.isna(c) or pd.isna(h) or pd.isna(l):
        return False
    if c <= o:
        return False
    rng = h - l
    if rng <= 0:
        return False
    return (c - l) >= 0.67 * rng

def _rvol_na_vela(df, vela):
    """RVOL da VELA DE ABERTURA: volume da vela / média-20 do candle imediatamente
    ANTERIOR (linha de volume 'normal' pré-abertura). Mesma convenção do scan de
    estabilização: a média NÃO inclui o pico da abertura, então o RVOL reflete quantas
    vezes maior é o volume de abertura vs. o volume normal."""
    if vela is None:
        return 0.0
    try:
        vol_media = df['Volume'].rolling(20).mean()
        pos = df.index.get_loc(vela.name)
        if pos <= 0:
            return 0.0
        media = float(vol_media.iloc[pos - 1])
        return float(vela['Volume']) / media if media > 0 else 0.0
    except Exception:
        return 0.0

def _tendencia_30m(df_30m):
    """Tendência no 30m (INFORMATIVA — não é filtro): close vs EMA20."""
    try:
        close = float(df_30m['Close'].iloc[-1])
        ema20 = float(ta.ema(df_30m['Close'], length=20).iloc[-1])
        return "✅ Alta" if close > ema20 else "❌ Baixa"
    except Exception:
        return "—"

def coletar_confluencia_15m_30m(ativos, rvol_min):
    """Detecta ativos cuja PRIMEIRA vela do dia — a de ABERTURA (10:00) — é de alta FORTE
    em AMBOS os timeframes (15m E 30m), com confirmação de VOLUME (RVOL >= rvol_min) na
    vela de abertura de cada timeframe. Confluência multi-timeframe de compradores na
    abertura. A âncora é a vela de abertura (mesmo helper do scan de estabilização), NÃO
    a última vela fechada — apenas detecta e confirma o movimento (sem plano de posição)."""
    hoje = data_layer.session_today()
    if hoje is None:
        return pd.DataFrame()  # fim de semana — sem pregão para analisar hoje

    resultados = []
    # Progresso gerenciado pelo worker

    _prewarm_com_progresso(ativos, ['15m', '30m'])

    total = len(ativos)
    for i, symbol in enumerate(ativos):
        try:
            df_15m = baixar_dados_15m(symbol)
            df_30m = baixar_dados_30m(symbol)
            if df_15m is None or df_15m.empty or len(df_15m) < 25:
                continue
            if df_30m is None or df_30m.empty or len(df_30m) < 25:
                continue

            # Estritamente o pregão de HOJE
            df_hoje_15m = df_15m[df_15m.index.date == hoje]
            df_hoje_30m = df_30m[df_30m.index.date == hoje]

            # Vela de ABERTURA de hoje (10:00) — primeira vela do dia — travada no horário
            # real da B3 (robusto a gaps/leilão), mesmo helper do scan de estabilização.
            abertura_15 = _candle_por_hora(df_hoje_15m, 10, 0)
            abertura_30 = _candle_por_hora(df_hoje_30m, 10, 0)
            if abertura_15 is None or abertura_30 is None:
                continue  # pregão cedo demais: ainda não chegou o candle das 10:00

            # Gatilho: vela de abertura de alta forte nos DOIS timeframes
            if not (_e_vela_alta_forte(abertura_15) and _e_vela_alta_forte(abertura_30)):
                continue

            # Confirmação de volume (RVOL) na vela de abertura de cada timeframe
            rvol15 = _rvol_na_vela(df_15m, abertura_15)
            rvol30 = _rvol_na_vela(df_30m, abertura_30)
            if rvol15 < rvol_min or rvol30 < rvol_min:
                continue

            preco = float(df_hoje_15m['Close'].iloc[-1])  # preço atual do dia

            def _fech_pct(v):
                rng = v['High'] - v['Low']
                return round((v['Close'] - v['Low']) / rng * 100, 1) if rng > 0 else 0.0

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço': round(preco, 2),
                'Confirmação': "30m ✅ / 15m ✅",
                'RVOL 30m': round(rvol30, 2),
                'RVOL 15m': round(rvol15, 2),
                'Fech. 30m (%)': _fech_pct(abertura_30),
                'Fech. 15m (%)': _fech_pct(abertura_15),
                'Var. Abertura 30m (%)': round((abertura_30['Close'] - abertura_30['Open']) / abertura_30['Open'] * 100, 2),
                'Tendência 30m': _tendencia_30m(df_30m),
            })
        except Exception:
            continue

    return pd.DataFrame(resultados)

def monitoramento_intraday(ativos):
    """
    Monitoramento Intraday (10:00 - 16:30)
    Entrada prioritária: rompimento da máxima anterior com volume ou pullback na VWAP/EMA9/20 no 30m.
    Descarta após 14:30 se sem confluência.
    """
    hoje = data_layer.session_today()
    if hoje is None:
        return pd.DataFrame()

    resultados = []
    _prewarm_com_progresso(ativos, ['1d', '30m'])

    # Horário atual (BRT)
    now = data_layer._now_brt()
    is_late = now.hour > 14 or (now.hour == 14 and now.minute >= 30)

    for symbol in ativos:
        try:
            df_d = baixar_dados(symbol, '1d', '60d')
            if df_d is None or len(df_d) < 2:
                continue

            # Máxima do dia ANTERIOR
            df_d_past = df_d[df_d.index.date < hoje]
            if df_d_past.empty:
                continue
            max_anterior = float(df_d_past.iloc[-1]['High'])
            fechamento_anterior = float(df_d_past.iloc[-1]['Close'])

            # RSI Diário para avaliar risco de gap down ou sobrecompra
            df_d['RSI'] = ta.rsi(df_d['Close'], length=14)
            rsi_diario = float(df_d['RSI'].iloc[-1]) if not pd.isna(df_d['RSI'].iloc[-1]) else 50.0

            df_30 = baixar_dados(symbol, '30m', '15d')
            if df_30 is None or len(df_30) < 20:
                continue

            df_30_hoje = df_30[df_30.index.date == hoje]
            if df_30_hoje.empty:
                continue

            last_30 = df_30.iloc[-1]
            close = float(last_30['Close'])

            df_30['EMA9'] = ta.ema(df_30['Close'], length=9)
            df_30['EMA20'] = ta.ema(df_30['Close'], length=20)
            ema9 = float(df_30['EMA9'].iloc[-1])
            ema20 = float(df_30['EMA20'].iloc[-1])

            # VWAP do dia
            df_30_hoje = df_30[df_30.index.date == hoje].copy()
            df_30_hoje['Typical'] = (df_30_hoje['High'] + df_30_hoje['Low'] + df_30_hoje['Close']) / 3
            df_30_hoje['Vol_x_TP'] = df_30_hoje['Typical'] * df_30_hoje['Volume']
            vol_total = df_30_hoje['Volume'].sum()
            vwap = df_30_hoje['Vol_x_TP'].sum() / vol_total if vol_total > 0 else close

            # Volume ratio (RVOL) do 30m
            vol_media = df_30['Volume'].rolling(20).mean()
            vol_med_val = float(vol_media.iloc[-1]) if float(vol_media.iloc[-1]) > 0 else 1.0
            vol_last = float(last_30['Volume'])
            rvol = vol_last / vol_med_val

            # Setup evaluation
            dist_vwap = abs(close - vwap) / close
            dist_ema9 = abs(close - ema9) / close
            dist_ema20 = abs(close - ema20) / close

            # 0.5% threshold for pullback
            is_pullback = (dist_vwap <= 0.005) or (dist_ema9 <= 0.005) or (dist_ema20 <= 0.005)
            is_rompimento_1h = False # Precisaria ler o 1h, ou usar o 30m como proxy de fluxo contínuo
            is_rompimento = close > max_anterior and rvol > 1.0

            setup = "Nenhum"
            status = "⏳ Aguardando"

            risco_venda = rsi_diario > 70
            alerta_rsi = " | ⚠️ RSI no Diário sobrecomprado" if risco_venda else ""

            if is_rompimento:
                setup = "🚀 Rompimento Máx. Ant."
                status = f"✅ Entrada{alerta_rsi}"
            elif is_pullback and close >= vwap and rvol > 1.0: # Pullback conditions + Volume
                setup = "🧲 Pullback (VWAP/EMA)"
                status = f"✅ Entrada{alerta_rsi}"
            elif close > max_anterior:
                setup = "🚀 Rompimento"
                status = "⚠️ Sem Volume no Rompimento"
            elif is_pullback and close >= vwap:
                setup = "🧲 Pullback na Média"
                status = "👀 Monitorar Volume"
            elif dist_vwap <= 0.01 or dist_ema9 <= 0.01:
                setup = "Próximo à Média"
                status = "👀 Monitorar"

            if is_late and "✅ Entrada" not in status:
                status = "🗑️ Descartado (>14h30 - s/ confluência clara)"

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preço': round(close, 2),
                'Máx Ant.': round(max_anterior, 2),
                'VWAP': round(vwap, 2),
                'EMA 9 (30m)': round(ema9, 2),
                'EMA 20 (30m)': round(ema20, 2),
                'RVOL 30m': round(rvol, 2),
                'RSI 1d': round(rsi_diario, 1),
                'Setup': setup,
                'Status': status
            })
        except Exception:
            continue

    return pd.DataFrame(resultados)