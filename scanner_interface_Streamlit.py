# -*- coding: utf-8 -*-
"""
SCANNER CONSOLIDADO - INTERFACE STREAMLIT
Mercado Brasileiro - Scalping & Swing Trade
Todos os modos do scanner_consolidado.py disponíveis via Streamlit.
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Scanner Acoes BR", layout="wide", page_icon="📈")
st.title("SCANNER CONSOLIDADO DE ACOES - BRASIL")
st.markdown("**Scalping + Swing Trade** | Dados em tempo real via yfinance")

# ===================== LISTA DE ATIVOS =====================
ATIVOS_BLUE_CHIPS = [
    'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'PRIO3.SA', 'BBAS3.SA',
    'B3SA3.SA', 'BBDC4.SA', 'BPAC11.SA', 'NVDC34.SA', 'TSLA34.SA',
    'AAPL34.SA', 'AMZO34.SA', 'GOGL34.SA', 'MSFT34.SA', 'MELI34.SA',
    'ROXO34.SA', 'IVVB11.SA', 'NASD11.SA', 'GOLD11.SA', 'BOVA11.SA'
]

ATIVOS_MID_SMALL_CAPS = [
    'RENT3.SA', 'LREN3.SA', 'MGLU3.SA', 'HAPV3.SA', 'EQTL3.SA',
    'SBSP3.SA', 'TOTS3.SA', 'RAIL3.SA', 'CSNA3.SA', 'GGBR4.SA',
    'USIM5.SA', 'ALPA4.SA', 'TTEN3.SA', 'POMO4.SA', 'PLPL3.SA',
    'VULC3.SA', 'IRBR3.SA', 'EVEN3.SA', 'DIRR3.SA', 'CURY3.SA',
    'BMOB3.SA', 'ALUP11.SA', 'BRBI11.SA', 'TAEE11.SA', 'BRSR6.SA',
    'LEVE3.SA', 'RANI3.SA', 'SEQL3.SA', 'TUPY3.SA', 'CVCB3.SA',
    'GMAT3.SA', 'GRND3.SA', 'POMO3.SA', 'CEAB3.SA', 'VIVA3.SA',
    'PGMN3.SA', 'SMFT3.SA'
]

ATIVOS_COMPLETO = ATIVOS_BLUE_CHIPS + ATIVOS_MID_SMALL_CAPS

# ===================== FUNCOES UTILITARIAS =====================
@st.cache_data(ttl=300)
def baixar_dados(symbol, interval, period):
    try:
        df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(1, axis=1)
        return df
    except:
        return pd.DataFrame()

def safe_float(x, default=0.0):
    try:
        if pd.isna(x) or x is None:
            return default
        return float(x)
    except:
        return default

# ===================== SCANNER SCALPING (5m + 15m + 1H) =====================
def scanner_scalping_melhorado(ativos):
    resultados = []
    progress = st.progress(0, text="Analisando ativos...")
    total = len(ativos)

    for i, symbol in enumerate(ativos):
        progress.progress(i / total, text=f"Analisando {symbol.replace('.SA', '')}...")
        try:
            df5 = baixar_dados(symbol, '5m', '5d')
            if len(df5) < 200:
                continue

            last5 = df5.iloc[-1]
            prev5 = df5.iloc[-2]
            preco = safe_float(last5['Close'])

            df5['EMA8'] = ta.ema(df5['Close'], length=8)
            df5['EMA21'] = ta.ema(df5['Close'], length=21)
            df5['RSI'] = ta.rsi(df5['Close'], length=14)
            df5['ATR'] = ta.atr(df5['High'], df5['Low'], df5['Close'], length=14)
            df5['VWAP'] = ta.vwap(df5['High'], df5['Low'], df5['Close'], df5['Volume'])
            macd5 = ta.macd(df5['Close'])
            adx5 = ta.adx(df5['High'], df5['Low'], df5['Close'], length=14)

            vol20 = df5['Volume'].rolling(20).mean()
            vol_ratio = safe_float(last5['Volume']) / safe_float(vol20.iloc[-1])
            atr_val = safe_float(df5['ATR'].iloc[-1])
            rsi = safe_float(df5['RSI'].iloc[-1])
            macd_val = safe_float(macd5['MACD_12_26_9'].iloc[-1])
            adx_val = safe_float(adx5['ADX_14'].iloc[-1])
            vwap_val = safe_float(df5['VWAP'].iloc[-1])

            df15 = baixar_dados(symbol, '15m', '5d')
            score_15 = 0
            if len(df15) > 120:
                df15['EMA8'] = ta.ema(df15['Close'], length=8)
                df15['VWAP'] = ta.vwap(df15['High'], df15['Low'], df15['Close'], df15['Volume'])
                if preco > safe_float(df15['EMA8'].iloc[-1]): score_15 += 25
                if preco > safe_float(df15['VWAP'].iloc[-1]): score_15 += 20

            df1h = baixar_dados(symbol, '1h', '75d')
            tendencia_1h = "NEUTRA"
            if len(df1h) > 80:
                df1h['EMA20'] = ta.ema(df1h['Close'], length=20)
                if preco > safe_float(df1h['EMA20'].iloc[-1]):
                    tendencia_1h = "ALTA"
                else:
                    tendencia_1h = "BAIXA"

            if vol_ratio < 2.5: continue
            if safe_float(vol20.iloc[-1]) < 450_000: continue
            if preco <= safe_float(df5['EMA8'].iloc[-1]): continue
            if preco < vwap_val: continue
            if adx_val < 28: continue
            if rsi > 76 or rsi < 45: continue
            if tendencia_1h == "BAIXA": continue

            score = 0
            if preco > safe_float(df5['EMA8'].iloc[-1]): score += 30
            if macd_val > 0: score += 20
            if vol_ratio > 4.0: score += 25
            if adx_val > 35: score += 15
            if 55 < rsi < 72: score += 15
            if atr_val / preco < 0.018: score += 10
            score += score_15

            var_atual = ((preco / safe_float(prev5['Close'])) - 1) * 100
            suporte = safe_float(df5['Low'].rolling(30).min().iloc[-1])
            resistencia = safe_float(df5['High'].rolling(30).max().iloc[-1])
            stop_loss = preco - (atr_val * 1.6)
            risco = preco - stop_loss
            alvo1 = preco + (risco * 1.5)
            alvo2 = preco + (risco * 2.5)
            distancia_stop = ((preco - stop_loss) / preco) * 100

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preco': preco,
                'Var 5m': var_atual,
                'Score': score,
                'Vol Ratio': vol_ratio,
                'ADX': adx_val,
                'RSI': rsi,
                'Tend 1H': tendencia_1h,
                'Suporte': suporte,
                'Resistencia': resistencia,
                'Stop Loss': stop_loss,
                'Dist Stop %': distancia_stop,
                'Alvo 1:1.5': alvo1,
                'Alvo 1:2.5': alvo2,
                'Avaliacao': 'EXCELENTE SCALP' if score >= 95 else 'Boa Entrada' if score >= 80 else 'Monitorar'
            })
        except:
            continue

    progress.progress(1.0, text="Concluido!")
    return pd.DataFrame(resultados)

# ===================== SCANNER SCALPING RAPIDO (5m + 15m + 1m) =====================
def scanner_scalping_rapido(ativos):
    resultados = []
    progress = st.progress(0, text="Analisando ativos...")
    total = len(ativos)

    for i, symbol in enumerate(ativos):
        progress.progress(i / total, text=f"Analisando {symbol.replace('.SA', '')}...")
        try:
            df5 = baixar_dados(symbol, '5m', '5d')
            if len(df5) < 200:
                continue

            last5 = df5.iloc[-1]
            prev5 = df5.iloc[-2]
            preco = safe_float(last5['Close'])

            df5['EMA8'] = ta.ema(df5['Close'], length=8)
            df5['EMA21'] = ta.ema(df5['Close'], length=21)
            df5['RSI'] = ta.rsi(df5['Close'], length=14)
            df5['ATR'] = ta.atr(df5['High'], df5['Low'], df5['Close'], length=14)
            df5['VWAP'] = ta.vwap(df5['High'], df5['Low'], df5['Close'], df5['Volume'])
            macd5 = ta.macd(df5['Close'])
            adx5 = ta.adx(df5['High'], df5['Low'], df5['Close'], length=14)

            vol20 = df5['Volume'].rolling(20).mean()
            vol_ratio = safe_float(last5['Volume']) / safe_float(vol20.iloc[-1])
            vol_medio = safe_float(vol20.iloc[-1])
            atr_val = safe_float(df5['ATR'].iloc[-1])
            rsi = safe_float(df5['RSI'].iloc[-1])
            macd_val = safe_float(macd5['MACD_12_26_9'].iloc[-1])
            adx_val = safe_float(adx5['ADX_14'].iloc[-1])
            vwap_val = safe_float(df5['VWAP'].iloc[-1])

            df15 = baixar_dados(symbol, '15m', '5d')
            tendencia_15 = "NEUTRA"
            score_15 = 0
            if len(df15) > 100:
                df15['EMA8'] = ta.ema(df15['Close'], length=8)
                df15['VWAP'] = ta.vwap(df15['High'], df15['Low'], df15['Close'], df15['Volume'])
                if preco > safe_float(df15['EMA8'].iloc[-1]):
                    tendencia_15 = "ALTA"
                    score_15 += 25
                if preco > safe_float(df15['VWAP'].iloc[-1]):
                    score_15 += 20

            df1 = baixar_dados(symbol, '1m', '1d')
            score_1m = 0
            if len(df1) > 150:
                df1['EMA8'] = ta.ema(df1['Close'], length=8)
                if preco > safe_float(df1['EMA8'].iloc[-1]): score_1m += 30

            if vol_ratio < 2.5: continue
            if vol_medio < 420_000: continue
            if preco <= safe_float(df5['EMA8'].iloc[-1]): continue
            if preco < vwap_val: continue
            if adx_val < 28: continue
            if rsi > 76 or rsi < 45: continue

            score = 0
            if preco > safe_float(df5['EMA8'].iloc[-1]): score += 30
            if macd_val > 0: score += 20
            if vol_ratio > 4.0: score += 25
            if adx_val > 34: score += 15
            if 54 < rsi < 72: score += 15
            if atr_val / preco < 0.018: score += 10
            score += score_15 + (score_1m * 0.8)

            var_atual = ((preco / safe_float(prev5['Close'])) - 1) * 100
            suporte = safe_float(df5['Low'].rolling(40).min().iloc[-1])
            resistencia = safe_float(df5['High'].rolling(40).max().iloc[-1])
            stop_loss = preco - (atr_val * 1.55)
            risco = preco - stop_loss
            alvo1 = preco + (risco * 1.5)
            alvo2 = preco + (risco * 2.5)
            distancia_stop = ((preco - stop_loss) / preco) * 100

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preco': preco,
                'Var 5m': var_atual,
                'Score': score,
                'Vol Ratio': vol_ratio,
                'ADX': adx_val,
                'RSI': rsi,
                'Tend 15m': tendencia_15,
                'Timing 1m': 'Forte' if score_1m >= 25 else 'Fraco',
                'Suporte': suporte,
                'Resistencia': resistencia,
                'Stop Loss': stop_loss,
                'Dist Stop %': distancia_stop,
                'Alvo 1:1.5': alvo1,
                'Alvo 1:2.5': alvo2,
                'Avaliacao': 'EXCELENTE SCALP' if score >= 95 else 'Boa Entrada' if score >= 80 else 'Monitorar'
            })
        except:
            continue

    progress.progress(1.0, text="Concluido!")
    return pd.DataFrame(resultados)

# ===================== ANALISAR TIMEFRAME SWING =====================
def analisar_timeframe_swing(df, tf_name="Daily", incluir_atr=False):
    if len(df) < 100:
        return 0, "", 0, 0, 0, 0

    last = df.iloc[-1]
    preco = safe_float(last['Close'])

    df['EMA9'] = ta.ema(df['Close'], length=9)
    df['EMA20'] = ta.ema(df['Close'], length=20)
    df['EMA50'] = ta.ema(df['Close'], length=50)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

    macd = ta.macd(df['Close'])
    adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)

    vol20 = df['Volume'].rolling(20).mean()
    vol_ratio = safe_float(last['Volume']) / safe_float(vol20.iloc[-1])

    rsi = safe_float(df['RSI'].iloc[-1])
    adx_val = safe_float(adx['ADX_14'].iloc[-1])
    macd_val = safe_float(macd['MACD_12_26_9'].iloc[-1])
    atr_val = safe_float(df['ATR'].iloc[-1]) if incluir_atr else 0

    score = 0
    if preco > safe_float(df['EMA9'].iloc[-1]): score += 25
    if preco > safe_float(df['EMA20'].iloc[-1]): score += 25
    if macd_val > 0: score += 15
    if adx_val > 25: score += 20
    if 48 < rsi < 74: score += 15

    tendencia = "ALTA" if preco > safe_float(df['EMA20'].iloc[-1]) else "BAIXA"
    info = f"{tf_name} {tendencia} | ADX {adx_val:.1f} | RSI {rsi:.1f} | Score {score}"

    return score, info, adx_val, rsi, vol_ratio, atr_val

# ===================== SCANNER SWING HIBRIDO (Daily + 1H + 30M) =====================
def scanner_swing_hibrido(ativos):
    resultados = []
    progress = st.progress(0, text="Analisando ativos...")
    total = len(ativos)

    for i, symbol in enumerate(ativos):
        progress.progress(i / total, text=f"Analisando {symbol.replace('.SA', '')}...")
        try:
            df_d = baixar_dados(symbol, '1d', '1y')
            if len(df_d) < 150:
                continue

            daily_score, daily_info, daily_adx, daily_rsi, daily_vol_ratio, _ = analisar_timeframe_swing(df_d, "Daily")
            last_d = df_d.iloc[-1]
            preco = safe_float(last_d['Close'])

            if daily_vol_ratio < 1.7: continue
            if safe_float(last_d['Volume'].rolling(20).mean().iloc[-1]) < 8_000_000: continue
            if daily_adx < 22: continue
            if not (47 < daily_rsi < 73): continue
            if preco <= safe_float(df_d['EMA50'].iloc[-1]): continue

            df_h = baixar_dados(symbol, '1h', '75d')
            h_score, h_info, h_adx, h_rsi, h_vol_ratio, _ = analisar_timeframe_swing(df_h, "1H") if len(df_h) > 180 else (0, "", 0, 0, 0, 0)

            df_30 = baixar_dados(symbol, '30m', '45d')
            score_30 = 0
            if len(df_30) > 200:
                df_30['EMA9'] = ta.ema(df_30['Close'], length=9)
                df_30['RSI'] = ta.rsi(df_30['Close'], length=14)
                if preco > safe_float(df_30['EMA9'].iloc[-1]): score_30 += 25
                if safe_float(df_30['RSI'].iloc[-1]) > 52: score_30 += 20

            score_total = (daily_score * 1.6) + h_score + score_30
            alinhamento = "FORTE" if (daily_adx > 25 and h_adx > 23) else "Parcial"

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preco': preco,
                'Score Total': round(score_total),
                'Alinhamento': alinhamento,
                'Daily Score': daily_score,
                'Daily Tend': daily_info,
                '1H Score': h_score,
                '1H Info': h_info,
                '30M Score': score_30,
                'Vol 1H': h_vol_ratio,
                'Vol Daily': daily_vol_ratio,
                'Avaliacao': 'EXCELENTE' if score_total >= 200 else 'Boa' if score_total >= 160 else 'Monitorar'
            })
        except:
            continue

    progress.progress(1.0, text="Concluido!")
    return pd.DataFrame(resultados)

# ===================== SCANNER SWING RR (Daily + 1H + 30M + Alvos) =====================
def scanner_swing_rr(ativos):
    resultados = []
    progress = st.progress(0, text="Analisando ativos...")
    total = len(ativos)

    for i, symbol in enumerate(ativos):
        progress.progress(i / total, text=f"Analisando {symbol.replace('.SA', '')}...")
        try:
            df_d = baixar_dados(symbol, '1d', '1y')
            if len(df_d) < 150: continue

            daily_score, daily_info, daily_adx, daily_rsi, daily_vol_ratio, daily_atr = analisar_timeframe_swing(df_d, "Daily", incluir_atr=True)
            last_d = df_d.iloc[-1]
            preco = safe_float(last_d['Close'])

            if daily_vol_ratio < 1.7: continue
            if safe_float(last_d['Volume'].rolling(20).mean().iloc[-1]) < 8_000_000: continue
            if daily_adx < 22: continue
            if not (47 < daily_rsi < 73): continue
            if preco <= safe_float(df_d['EMA50'].iloc[-1]): continue

            df_h = baixar_dados(symbol, '1h', '75d')
            h_score, h_info, h_adx, h_rsi, h_vol_ratio, _ = analisar_timeframe_swing(df_h, "1H") if len(df_h) > 180 else (0, "", 0, 0, 0, 0)

            df_30 = baixar_dados(symbol, '30m', '45d')
            score_30 = 0
            if len(df_30) > 200:
                df_30['EMA9'] = ta.ema(df_30['Close'], length=9)
                df_30['RSI'] = ta.rsi(df_30['Close'], length=14)
                if preco > safe_float(df_30['EMA9'].iloc[-1]): score_30 += 25
                if safe_float(df_30['RSI'].iloc[-1]) > 52: score_30 += 20

            suporte = safe_float(df_d['Low'].rolling(20).min().iloc[-1])
            resistencia = safe_float(df_d['High'].rolling(20).max().iloc[-1])
            stop_atr = preco - (daily_atr * 1.8)
            risco = preco - stop_atr
            alvo2 = preco + (risco * 2)
            alvo3 = preco + (risco * 3)
            distancia_stop = ((preco - stop_atr) / preco) * 100

            score_total = (daily_score * 1.6) + h_score + score_30
            alinhamento = "FORTE" if (daily_adx > 25 and h_adx > 23) else "Parcial"

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preco': preco,
                'Score Total': round(score_total),
                'Alinhamento': alinhamento,
                'Suporte': suporte,
                'Resistencia': resistencia,
                'Stop Sugerido': stop_atr,
                'Dist Stop %': distancia_stop,
                'Alvo 1:2': alvo2,
                'Alvo 1:3': alvo3,
                'Daily Info': daily_info,
                '1H Info': h_info,
                '30M Score': score_30,
                'Vol 1H': h_vol_ratio,
                'Vol Daily': daily_vol_ratio,
                'Avaliacao': 'EXCELENTE' if score_total >= 200 else 'Boa' if score_total >= 160 else 'Monitorar'
            })
        except:
            continue

    progress.progress(1.0, text="Concluido!")
    return pd.DataFrame(resultados)

# ===================== SCANNER SWING PROFISSIONAL (Daily + 1H + 30M) =====================
def scanner_swing_profissional(ativos):
    resultados = []
    progress = st.progress(0, text="Analisando ativos...")
    total = len(ativos)

    def analisar_tf(df, tf_name):
        if len(df) < 50:
            return None
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

        vol20 = df['Volume'].rolling(20).mean()
        vol_ratio = safe_float(last['Volume']) / safe_float(vol20.iloc[-1])

        rsi = safe_float(df['RSI'].iloc[-1])
        adx_val = safe_float(adx['ADX_14'].iloc[-1])
        macd_val = safe_float(macd['MACD_12_26_9'].iloc[-1])

        score_tf = 0
        if preco > safe_float(df['EMA9'].iloc[-1]): score_tf += 25
        if preco > safe_float(df['EMA20'].iloc[-1]): score_tf += 20
        if macd_val > 0: score_tf += 20
        if adx_val > 25: score_tf += 15
        if 52 < rsi < 73: score_tf += 20

        tendencia = "ALTA" if preco > safe_float(df['EMA20'].iloc[-1]) else "BAIXA"
        var = ((preco / safe_float(prev['Close'])) - 1) * 100

        return score_tf, tendencia, rsi, adx_val, macd_val, vol_ratio, var, safe_float(df['ATR'].iloc[-1])

    for i, symbol in enumerate(ativos):
        progress.progress(i / total, text=f"Analisando {symbol.replace('.SA', '')}...")
        try:
            df_daily = baixar_dados(symbol, '1d', '1y')
            if len(df_daily) < 120:
                continue

            res_d = analisar_tf(df_daily, "Daily")
            if not res_d:
                continue
            daily_score, daily_tend, daily_rsi, daily_adx, daily_macd, vol_ratio_d, var_d, atr_d = res_d

            if vol_ratio_d < 1.5: continue
            if safe_float(df_daily.iloc[-1]['Close']) <= safe_float(df_daily['EMA20'].iloc[-1]): continue
            if safe_float(df_daily.iloc[-1]['Close']) <= safe_float(df_daily['EMA50'].iloc[-1]): continue
            if daily_adx < 20: continue
            if not (45 < daily_rsi < 75): continue

            preco = safe_float(df_daily.iloc[-1]['Close'])

            df_1h = baixar_dados(symbol, '1h', '75d')
            res_h = analisar_tf(df_1h, "1H") if len(df_1h) >= 50 else None
            h1_score, h1_tend, h1_rsi, h1_adx, h1_macd, _, _, _ = res_h if res_h else (0, "NEUTRA", 0, 0, 0, 0, 0, 0)

            df_30m = baixar_dados(symbol, '30m', '45d')
            res_30 = analisar_tf(df_30m, "30M") if len(df_30m) >= 50 else None
            m30_score, m30_tend, m30_rsi, m30_adx, m30_macd, _, _, _ = res_30 if res_30 else (0, "NEUTRA", 0, 0, 0, 0, 0, 0)

            score_total = daily_score + h1_score + m30_score
            alinhamento = "FORTE" if h1_tend == m30_tend == daily_tend else "PARCIAL"

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preco': preco,
                'Score Total': score_total,
                'Alinhamento': alinhamento,
                'Daily Score': daily_score,
                'Daily Tend': daily_tend,
                'Daily RSI': daily_rsi,
                'Daily ADX': daily_adx,
                '1H Score': h1_score,
                '1H Tend': h1_tend,
                '1H RSI': h1_rsi,
                '30M Score': m30_score,
                '30M Tend': m30_tend,
                'Vol Daily': vol_ratio_d,
                'Avaliacao': 'EXCELENTE' if score_total >= 240 else 'Boa' if score_total >= 180 else 'Monitorar'
            })
        except:
            continue

    progress.progress(1.0, text="Concluido!")
    return pd.DataFrame(resultados)

# ===================== SCANNER SWING EXPANDIDO (Mid + Small Caps) =====================
def scanner_swing_expandido(ativos):
    resultados = []
    progress = st.progress(0, text="Analisando ativos...")
    total = len(ativos)

    for i, symbol in enumerate(ativos):
        progress.progress(i / total, text=f"Analisando {symbol.replace('.SA', '')}...")
        try:
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
            macd_val = safe_float(macd['MACD_12_26_9'].iloc[-1])
            adx_val = safe_float(adx['ADX_14'].iloc[-1])

            df['Vol20'] = df['Volume'].rolling(20).mean()
            vol_ratio = safe_float(last['Volume']) / safe_float(df['Vol20'].iloc[-1])
            vol_medio = safe_float(df['Vol20'].iloc[-1])
            rsi = safe_float(df['RSI'].iloc[-1])
            atr_dia = safe_float(df['ATR'].iloc[-1])

            if vol_ratio < 1.5: continue
            if vol_medio < 2_500_000: continue
            if preco <= safe_float(df['EMA20'].iloc[-1]): continue
            if preco <= safe_float(df['EMA50'].iloc[-1]): continue
            if adx_val < 20: continue
            if rsi > 75 or rsi < 45: continue

            score = 0
            if preco > safe_float(df['EMA9'].iloc[-1]): score += 20
            if macd_val > 0: score += 20
            if vol_ratio > 2.5: score += 20
            if adx_val > 25: score += 15
            if 55 < rsi < 72: score += 15
            if atr_dia / preco < 0.045: score += 10

            var_dia = ((preco / safe_float(prev['Close'])) - 1) * 100

            confluencia_1h = "Fraca"
            tendencia_1h = "Sem dados"
            rsi_1h = macd_1h = adx_1h = atr_1h = 0.0
            acima_ema_1h = False

            try:
                df_1h = baixar_dados(symbol, '1h', '75d')
                if len(df_1h) >= 80:
                    df_1h['EMA20'] = ta.ema(df_1h['Close'], length=20)
                    df_1h['EMA50'] = ta.ema(df_1h['Close'], length=50)
                    df_1h['RSI'] = ta.rsi(df_1h['Close'], length=14)
                    macd_1h_df = ta.macd(df_1h['Close'])
                    adx_1h_df = ta.adx(df_1h['High'], df_1h['Low'], df_1h['Close'], length=14)
                    atr_1h = safe_float(ta.atr(df_1h['High'], df_1h['Low'], df_1h['Close'], length=14).iloc[-1])

                    last_1h = df_1h.iloc[-1]
                    close_1h = safe_float(last_1h['Close'])
                    ema20_1h = safe_float(df_1h['EMA20'].iloc[-1])
                    ema50_1h = safe_float(df_1h['EMA50'].iloc[-1])
                    acima_ema_1h = close_1h > ema20_1h and close_1h > ema50_1h
                    rsi_1h = safe_float(df_1h['RSI'].iloc[-1])
                    macd_1h = safe_float(macd_1h_df['MACD_12_26_9'].iloc[-1])
                    adx_1h = safe_float(adx_1h_df['ADX_14'].iloc[-1])

                    if acima_ema_1h and adx_1h > 20 and 50 < rsi_1h < 75 and macd_1h > 0:
                        confluencia_1h = "Boa"
                        tendencia_1h = "Alta forte"
                    elif acima_ema_1h:
                        confluencia_1h = "Parcial"
                        tendencia_1h = "Alta moderada"
                    else:
                        tendencia_1h = "Consolidacao / Baixa"
            except:
                pass

            confluencia_30m = "Fraca"
            tendencia_30m = "Sem dados"
            rsi_30m = macd_30m = adx_30m = atr_30m = 0.0
            acima_ema_30m = False

            try:
                df_30m = baixar_dados(symbol, '30m', '45d')
                if len(df_30m) >= 150:
                    df_30m['EMA20'] = ta.ema(df_30m['Close'], length=20)
                    df_30m['EMA50'] = ta.ema(df_30m['Close'], length=50)
                    df_30m['RSI'] = ta.rsi(df_30m['Close'], length=14)
                    macd_30m_df = ta.macd(df_30m['Close'])
                    adx_30m_df = ta.adx(df_30m['High'], df_30m['Low'], df_30m['Close'], length=14)
                    atr_30m = safe_float(ta.atr(df_30m['High'], df_30m['Low'], df_30m['Close'], length=14).iloc[-1])

                    last_30m = df_30m.iloc[-1]
                    close_30m = safe_float(last_30m['Close'])
                    ema20_30m = safe_float(df_30m['EMA20'].iloc[-1])
                    ema50_30m = safe_float(df_30m['EMA50'].iloc[-1])
                    acima_ema_30m = close_30m > ema20_30m and close_30m > ema50_30m
                    rsi_30m = safe_float(df_30m['RSI'].iloc[-1])
                    macd_30m = safe_float(macd_30m_df['MACD_12_26_9'].iloc[-1])
                    adx_30m = safe_float(adx_30m_df['ADX_14'].iloc[-1])

                    if acima_ema_30m and adx_30m > 20 and 50 < rsi_30m < 75 and macd_30m > 0:
                        confluencia_30m = "Boa"
                        tendencia_30m = "Alta forte"
                    elif acima_ema_30m:
                        confluencia_30m = "Parcial"
                        tendencia_30m = "Alta moderada"
                    else:
                        tendencia_30m = "Consolidacao / Baixa"
            except:
                pass

            if confluencia_1h == "Boa" and confluencia_30m == "Boa":
                confluencia_geral = "Excelente"
            elif confluencia_1h == "Boa" or confluencia_30m == "Boa":
                confluencia_geral = "Boa"
            elif confluencia_1h == "Parcial" and confluencia_30m == "Parcial":
                confluencia_geral = "Parcial"
            else:
                confluencia_geral = "Fraca"

            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preco': preco,
                'Score Diario': score,
                'Var %': var_dia,
                'Vol Ratio': vol_ratio,
                'Vol Medio (M)': vol_medio / 1_000_000,
                'ADX': adx_val,
                'RSI': rsi,
                'ATR Diario': atr_dia,
                'Tend 1H': tendencia_1h,
                'Confluencia 1H': confluencia_1h,
                'Acima EMA 1H': acima_ema_1h,
                'RSI 1H': rsi_1h,
                'ADX 1H': adx_1h,
                'Tend 30M': tendencia_30m,
                'Confluencia 30M': confluencia_30m,
                'Acima EMA 30M': acima_ema_30m,
                'RSI 30M': rsi_30m,
                'ADX 30M': adx_30m,
                'Confluencia Geral': confluencia_geral,
            })
        except:
            continue

    progress.progress(1.0, text="Concluido!")
    return pd.DataFrame(resultados)

# ===================== HELPER: COPY TO CLIPBOARD =====================
def formatar_dataframe_para_texto(df):
    """Converte DataFrame em texto linear (uma linha por ativo, chave: valor)."""
    if df is None or df.empty:
        return "Não há setups de compra válidos no momento."

    cols = df.columns.tolist()
    linhas = []
    for _, row in df.iterrows():
        pares = []
        for col in cols:
            val = row[col]
            if pd.isna(val):
                val_str = "N/A"
            elif isinstance(val, float):
                val_str = f"{val:.2f}"
            else:
                val_str = str(val)
            pares.append(f"{col}: {val_str}")
        linhas.append(" | ".join(pares))

    return "\n".join(linhas)

def mostrar_resultado(df, label="resultado"):
    """Exibe o dataframe normal, mas copia com prompt de trader."""
    if df is None or df.empty:
        st.warning("Nenhum resultado encontrado.")
        return

    # Exibir dataframe normalmente
    st.dataframe(df, width='stretch', hide_index=True)

    # Prompt do trader (incluído apenas no clipboard)
    prompt_trader = """### Você é um trader profissional de Intraday e Swing curto prazo no mercado brasileiro.

**Regras de Análise (obedeça rigorosamente):**
- Timeframe principal: 1 hora
- Timeframe auxiliar: 30 minutos
- Estilo: Intraday ou Swing de 1 a 3 dias (posso carregar overnight)
- Risco máximo por trade: 1% do capital
- Risk:Reward mínimo obrigatório: **1:2**
- **Só liste setups de COMPRA válidos** (nada de venda ou short)
- Só recomende entrada se Score ≥ 65 e haja boa confluência entre 1h e 30m

**Responda EXATAMENTE neste formato:**

### ANÁLISE FINAL

**Setups de Compra Válidos (em ordem de prioridade):**

**XXXX** → **Score: XX/100**
**Entrada Sugerida:** R$ XXXX
**Stop Loss:** R$ XXXX (-X.X%)
**Target 1:** R$ XXXX (+X.X% | R:R 1:2)
**Target 2:** R$ XXXX (+X.X% | R:R 1:3)
**Confluência 1h + 30m:**
**Forças principais:**
**Fraquezas / Riscos:**
**Estratégia sugerida:**

**Setups para Monitorar (sem confluência suficiente):**
XXXX → Motivo breve

**Resumo Geral:**
**Viés do mercado hoje:**
**Nível de risco do dia (Baixo / Médio / Alto):**
**Melhor horário para entrada:**

Seja objetivo, direto e conservador. Se não houver setups bons, diga claramente "Não há setups de compra válidos no momento."

---

**Dados do Scanner (cole aqui todo o output do scanner):**

"""

    # Converter DataFrame para formato textual linear
    dados_textuais = formatar_dataframe_para_texto(df)

    # Combinar prompt + dados
    texto_completo = prompt_trader + dados_textuais

    # Escapar para HTML seguro (textarea) - só precisa escapar &, <, > e a sequência </textarea>
    html_safe = texto_completo.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # ID único por botão
    import hashlib
    uid = "t" + hashlib.md5((label + str(id(df))).encode()).hexdigest()[:8]

    copy_html = f"""
    <style>
        #copybtn{uid} {{
            background: linear-gradient(135deg, #065f46, #10b981);
            color: white; border: none; border-radius: 8px;
            padding: 10px 20px; font-size: 15px; cursor: pointer;
            font-family: sans-serif; font-weight: bold;
            transition: all 0.2s ease;
        }}
        #copybtn{uid}:hover {{
            background: linear-gradient(135deg, #10b981, #059669);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(16,185,129,0.4);
        }}
    </style>
    <textarea id="src{uid}" style="position:absolute;left:-9999px;top:0;width:1px;height:1px">{html_safe}</textarea>
    <button id="copybtn{uid}">📋 Copiar Análise Completa</button>
    <script>
        const btn{uid} = document.getElementById('copybtn{uid}');
        btn{uid}.addEventListener('click', function() {{
            const ta = document.getElementById('src{uid}');
            ta.style.position = 'static';
            ta.style.left = '0';
            ta.style.width = '100%';
            ta.style.height = '200px';
            ta.select();
            ta.setSelectionRange(0, 99999);
            let ok = false;
            try {{ ok = document.execCommand('copy'); }} catch(e) {{ ok = false; }}
            if (ok) {{
                btn{uid}.innerText = '✅ Copiado!';
                btn{uid}.style.background = 'linear-gradient(135deg, #064e3b, #059669)';
                ta.style.position = 'absolute';
                ta.style.left = '-9999px';
                ta.style.width = '1px';
                ta.style.height = '1px';
                setTimeout(() => {{
                    btn{uid}.innerText = '📋 Copiar Análise Completa';
                    btn{uid}.style.background = 'linear-gradient(135deg, #065f46, #10b981)';
                }}, 2500);
            }} else {{
                btn{uid}.innerText = 'Selecione e use Ctrl+C';
                btn{uid}.style.background = '#dc2626';
                ta.focus();
            }}
        }});
    </script>
    """
    st.iframe(copy_html, height=55)


# ===================== INTERFACE STREAMLIT =====================

# Inicialização do Session State para guardar os resultados dos scanners
scanners_keys = ['df_sc', 'df_sr', 'df_sh', 'df_rr', 'df_pro', 'df_exp']
for key in scanners_keys:
    if key not in st.session_state:
        st.session_state[key] = None

st.markdown("---")
st.subheader("⚙️ Painel de Controle Global")

col_radio, col_btn = st.columns([3, 1])
with col_radio:
    lista_global = st.radio(
        "Lista de ativos para todos os scanners:",
        ["Todos (Blue + Mid/Small)", "Blue Chips"],
        horizontal=True,
        key="sel_global"
    )

# Limpar session state se a seleção da lista global de ativos mudar
if 'lista_anterior' not in st.session_state:
    st.session_state.lista_anterior = lista_global

if st.session_state.lista_anterior != lista_global:
    for key in scanners_keys:
        st.session_state[key] = None
    st.session_state.lista_anterior = lista_global

with col_btn:
    rodar_todos = st.button("🚀 Rodar Todos os Scanners", type="primary", key="btn_rodar_todos", width='stretch')

ativos_global = ATIVOS_BLUE_CHIPS if lista_global == "Blue Chips" else ATIVOS_COMPLETO

st.markdown("---")

# ---- SCANNER 1: Scalping ----
with st.expander("📊 Scanner Scalping (5m + 15m + 1H)", expanded=True):
    st.caption("Filtros: Volume alto + Acima VWAP + Tendencia 1H + RR claro")
    btn_sc = st.button("▶ Rodar Scalping", key="btn_scalping")
    if rodar_todos or btn_sc:
        with st.spinner("Analisando Scalping..."):
            df_sc = scanner_scalping_melhorado(ativos_global)
            if not df_sc.empty:
                st.session_state.df_sc = df_sc.sort_values('Score', ascending=False)
            else:
                st.session_state.df_sc = pd.DataFrame()
                
    if st.session_state.df_sc is not None:
        if not st.session_state.df_sc.empty:
            mostrar_resultado(st.session_state.df_sc, label="scalping")
            st.success(f"Encontradas **{len(st.session_state.df_sc)}** oportunidades de scalping!")
        else:
            st.warning("Nenhuma oportunidade forte no momento.")

# ---- SCANNER 2: Scalping Rapido ----
with st.expander("⚡ Scanner Scalping Rapido (5m + 15m + 1m)", expanded=True):
    st.caption("Filtros reforçados: Volume alto + Acima VWAP + Tendencia 15m + Timing 1m")
    btn_sr = st.button("▶ Rodar Scalping Rapido", key="btn_scalping_r")
    if rodar_todos or btn_sr:
        with st.spinner("Analisando Scalping Rapido..."):
            df_sr = scanner_scalping_rapido(ativos_global)
            if not df_sr.empty:
                st.session_state.df_sr = df_sr.sort_values('Score', ascending=False)
            else:
                st.session_state.df_sr = pd.DataFrame()
                
    if st.session_state.df_sr is not None:
        if not st.session_state.df_sr.empty:
            mostrar_resultado(st.session_state.df_sr, label="scalping_rapido")
            st.success(f"Encontradas **{len(st.session_state.df_sr)}** oportunidades de scalping rapido!")
        else:
            st.warning("Nenhuma oportunidade forte no momento.")

# ---- SCANNER 3: Swing Hibrido ----
with st.expander("🔀 Scanner Swing Hibrido (Daily + 1H + 30M)", expanded=True):
    st.caption("Filtros reforçados: Daily forte + Liquidez + Alinhamento multi-TF")
    btn_sh = st.button("▶ Rodar Swing Hibrido", key="btn_swing_h")
    if rodar_todos or btn_sh:
        with st.spinner("Analisando Swing Hibrido..."):
            df_sh = scanner_swing_hibrido(ativos_global)
            if not df_sh.empty:
                st.session_state.df_sh = df_sh.sort_values('Score Total', ascending=False)
            else:
                st.session_state.df_sh = pd.DataFrame()
                
    if st.session_state.df_sh is not None:
        if not st.session_state.df_sh.empty:
            mostrar_resultado(st.session_state.df_sh, label="swing_hibrido")
            st.success(f"Encontradas **{len(st.session_state.df_sh)}** oportunidades de swing trade!")
        else:
            st.warning("Nenhum ativo atendeu aos criterios rigorosos no momento.")

# ---- SCANNER 4: Swing RR ----
with st.expander("🎯 Scanner Swing Trade + Risk/Reward (Daily + 1H + 30M + Alvos)", expanded=True):
    st.caption("Filtros reforçados + Suporte/Resistencia + Stop + Alvos 1:2 e 1:3")
    btn_rr = st.button("▶ Rodar Swing RR", key="btn_swing_rr")
    if rodar_todos or btn_rr:
        with st.spinner("Analisando Swing RR..."):
            df_rr = scanner_swing_rr(ativos_global)
            if not df_rr.empty:
                st.session_state.df_rr = df_rr.sort_values('Score Total', ascending=False)
            else:
                st.session_state.df_rr = pd.DataFrame()
                
    if st.session_state.df_rr is not None:
        if not st.session_state.df_rr.empty:
            mostrar_resultado(st.session_state.df_rr, label="swing_rr")
            st.success(f"Encontradas **{len(st.session_state.df_rr)}** oportunidades com alvos de RR!")
        else:
            st.warning("Nenhum ativo atendeu aos criterios rigorosos no momento.")

# ---- SCANNER 5: Swing Pro ----
with st.expander("🏆 Scanner Swing Trade Profissional (Daily + 1H + 30M)", expanded=True):
    st.caption("Filtros: Vol >1.5x | Acima EMA20/50 | ADX>20 | RSI 45-75 | Alinhamento 1H+30M")
    btn_pro = st.button("▶ Rodar Swing Pro", key="btn_swing_pro")
    if rodar_todos or btn_pro:
        with st.spinner("Analisando Swing Pro..."):
            df_pro = scanner_swing_profissional(ativos_global)
            if not df_pro.empty:
                st.session_state.df_pro = df_pro.sort_values('Score Total', ascending=False)
            else:
                st.session_state.df_pro = pd.DataFrame()
                
    if st.session_state.df_pro is not None:
        if not st.session_state.df_pro.empty:
            mostrar_resultado(st.session_state.df_pro, label="swing_pro")
            st.success(f"Encontradas **{len(st.session_state.df_pro)}** oportunidades de swing profissional!")
        else:
            st.warning("Nenhum ativo atendeu todos os criterios no momento.")

# ---- SCANNER 6: Swing Expandido ----
with st.expander("🌐 Scanner Swing Expandido (Blue + Mid/Small Caps)", expanded=True):
    st.caption("Lista atualizada 2026 | Criterios rigorosos + Confluencia 1h/30m")
    btn_exp = st.button("▶ Rodar Swing Expandido", key="btn_swing_exp")
    if rodar_todos or btn_exp:
        with st.spinner("Analisando Swing Expandido..."):
            df_exp = scanner_swing_expandido(ativos_global)
            if not df_exp.empty:
                st.session_state.df_exp = df_exp.sort_values('Score Diario', ascending=False)
            else:
                st.session_state.df_exp = pd.DataFrame()
                
    if st.session_state.df_exp is not None:
        if not st.session_state.df_exp.empty:
            mostrar_resultado(st.session_state.df_exp, label="swing_expandido")
            bons = st.session_state.df_exp[st.session_state.df_exp['Confluencia Geral'].isin(['Boa', 'Excelente'])]
            if len(bons) > 0:
                st.success(f"Encontradas **{len(st.session_state.df_exp)}** oportunidades. **{len(bons)}** com confluencia Boa/Excelente.")
            else:
                st.info(f"Encontradas **{len(st.session_state.df_exp)}** oportunidades, mas nenhuma com confluencia Boa/Excelente.")
        else:
            st.warning("Nenhum ativo atendeu todos os criterios hoje. Mercado ainda em consolidacao.")

# --- RODAPE ---
st.markdown("---")
st.caption(f"Desenvolvido para o mercado brasileiro | Dados via Yahoo Finance | Ultima atualizacao: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
