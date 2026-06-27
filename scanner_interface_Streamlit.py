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

            df1h = baixar_dados(symbol, '1h', '15d')
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

            df15 = baixar_dados(symbol, '15m', '3d')
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

            df_h = baixar_dados(symbol, '1h', '60d')
            h_score, h_info, h_adx, h_rsi, h_vol_ratio, _ = analisar_timeframe_swing(df_h, "1H") if len(df_h) > 180 else (0, "", 0, 0, 0, 0)

            df_30 = baixar_dados(symbol, '30m', '15d')
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

            df_h = baixar_dados(symbol, '1h', '60d')
            h_score, h_info, h_adx, h_rsi, h_vol_ratio, _ = analisar_timeframe_swing(df_h, "1H") if len(df_h) > 180 else (0, "", 0, 0, 0, 0)

            df_30 = baixar_dados(symbol, '30m', '15d')
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

            df_1h = baixar_dados(symbol, '1h', '60d')
            res_h = analisar_tf(df_1h, "1H") if len(df_1h) >= 50 else None
            h1_score, h1_tend, h1_rsi, h1_adx, h1_macd, _, _, _ = res_h if res_h else (0, "NEUTRA", 0, 0, 0, 0, 0, 0)

            df_30m = baixar_dados(symbol, '30m', '15d')
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

# ===================== INTERFACE STREAMLIT =====================
aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs([
    "Scalping",
    "Scalping Rapido",
    "Swing Hibrido",
    "Swing RR",
    "Swing Pro",
    "Swing Expandido"
])

# --- ABA 1: Scalping ---
with aba1:
    st.subheader("Scanner Scalping (5m + 15m + 1H)")
    st.caption("Filtros: Volume alto + Acima VWAP + Tendencia 1H + RR claro")
    col_sel1, col_btn1 = st.columns([3, 1])
    with col_sel1:
        lista_scalping = st.radio("Lista de ativos:", ["Todos (Blue + Mid/Small)", "Blue Chips"], horizontal=True, key="sel_scalping")
    ativos_scalping = ATIVOS_BLUE_CHIPS if lista_scalping == "Blue Chips" else ATIVOS_COMPLETO

    if st.button("Rodar Scanner Scalping", type="primary", key="btn_scalping"):
        with st.spinner("Analisando mercado..."):
            df = scanner_scalping_melhorado(ativos_scalping)
            if not df.empty:
                df = df.sort_values('Score', ascending=False)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.success(f"Encontradas **{len(df)}** oportunidades de scalping!")
            else:
                st.warning("Nenhuma oportunidade forte no momento.")

# --- ABA 2: Scalping Rapido ---
with aba2:
    st.subheader("Scanner Scalping Rapido (5m + 15m + 1m)")
    st.caption("Filtros reforçados: Volume alto + Acima VWAP + Tendencia 15m + Timing 1m")
    col_sel2, col_btn2 = st.columns([3, 1])
    with col_sel2:
        lista_scalping_r = st.radio("Lista de ativos:", ["Todos (Blue + Mid/Small)", "Blue Chips"], horizontal=True, key="sel_scalping_r")
    ativos_scalping_r = ATIVOS_BLUE_CHIPS if lista_scalping_r == "Blue Chips" else ATIVOS_COMPLETO

    if st.button("Rodar Scanner Scalping Rapido", type="primary", key="btn_scalping_r"):
        with st.spinner("Analisando mercado..."):
            df = scanner_scalping_rapido(ativos_scalping_r)
            if not df.empty:
                df = df.sort_values('Score', ascending=False)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.success(f"Encontradas **{len(df)}** oportunidades de scalping rapido!")
            else:
                st.warning("Nenhuma oportunidade forte no momento.")

# --- ABA 3: Swing Hibrido ---
with aba3:
    st.subheader("Scanner Swing Hibrido (Daily + 1H + 30M)")
    st.caption("Filtros reforçados: Daily forte + Liquidez + Alinhamento multi-TF")
    col_sel3, col_btn3 = st.columns([3, 1])
    with col_sel3:
        lista_swing_h = st.radio("Lista de ativos:", ["Todos (Blue + Mid/Small)", "Blue Chips"], horizontal=True, key="sel_swing_h")
    ativos_swing_h = ATIVOS_BLUE_CHIPS if lista_swing_h == "Blue Chips" else ATIVOS_COMPLETO

    if st.button("Rodar Scanner Swing Hibrido", type="primary", key="btn_swing_h"):
        with st.spinner("Analisando mercado..."):
            df = scanner_swing_hibrido(ativos_swing_h)
            if not df.empty:
                df = df.sort_values('Score Total', ascending=False)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.success(f"Encontradas **{len(df)}** oportunidades de swing trade!")
            else:
                st.warning("Nenhum ativo atendeu aos criterios rigorosos no momento.")

# --- ABA 4: Swing RR ---
with aba4:
    st.subheader("Scanner Swing Trade + Risk/Reward (Daily + 1H + 30M + Alvos)")
    st.caption("Filtros reforçados + Suporte/Resistencia + Stop + Alvos 1:2 e 1:3")
    col_sel4, col_btn4 = st.columns([3, 1])
    with col_sel4:
        lista_swing_rr = st.radio("Lista de ativos:", ["Todos (Blue + Mid/Small)", "Blue Chips"], horizontal=True, key="sel_swing_rr")
    ativos_swing_rr = ATIVOS_BLUE_CHIPS if lista_swing_rr == "Blue Chips" else ATIVOS_COMPLETO

    if st.button("Rodar Scanner Swing RR", type="primary", key="btn_swing_rr"):
        with st.spinner("Analisando mercado..."):
            df = scanner_swing_rr(ativos_swing_rr)
            if not df.empty:
                df = df.sort_values('Score Total', ascending=False)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.success(f"Encontradas **{len(df)}** oportunidades com alvos de RR!")
            else:
                st.warning("Nenhum ativo atendeu aos criterios rigorosos no momento.")

# --- ABA 5: Swing Pro ---
with aba5:
    st.subheader("Scanner Swing Trade Profissional (Daily + 1H + 30M)")
    st.caption("Filtros: Vol >1.5x | Acima EMA20/50 | ADX>20 | RSI 45-75 | Alinhamento 1H+30M")
    col_sel5, col_btn5 = st.columns([3, 1])
    with col_sel5:
        lista_swing_pro = st.radio("Lista de ativos:", ["Todos (Blue + Mid/Small)", "Blue Chips"], horizontal=True, key="sel_swing_pro")
    ativos_swing_pro = ATIVOS_BLUE_CHIPS if lista_swing_pro == "Blue Chips" else ATIVOS_COMPLETO

    if st.button("Rodar Scanner Swing Pro", type="primary", key="btn_swing_pro"):
        with st.spinner("Analisando mercado..."):
            df = scanner_swing_profissional(ativos_swing_pro)
            if not df.empty:
                df = df.sort_values('Score Total', ascending=False)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.success(f"Encontradas **{len(df)}** oportunidades de swing profissional!")
            else:
                st.warning("Nenhum ativo atendeu todos os criterios no momento.")

# --- ABA 6: Swing Expandido ---
with aba6:
    st.subheader("Scanner Swing Expandido (Mid + Small Caps)")
    st.caption("Lista atualizada 2026 | Criterios rigorosos + Confluencia 1h/30m")

    if st.button("Rodar Scanner Swing Expandido", type="primary", key="btn_swing_exp"):
        with st.spinner("Analisando mercado..."):
            df = scanner_swing_expandido(ATIVOS_COMPLETO)
            if not df.empty:
                df = df.sort_values('Score Diario', ascending=False)
                st.dataframe(df, use_container_width=True, hide_index=True)
                bons = df[df['Confluencia Geral'].isin(['Boa', 'Excelente'])]
                if len(bons) > 0:
                    st.success(f"Encontradas **{len(df)}** oportunidades. **{len(bons)}** com confluencia Boa/Excelente.")
                else:
                    st.info(f"Encontradas **{len(df)}** oportunidades, mas nenhuma com confluencia Boa/Excelente.")
            else:
                st.warning("Nenhum ativo atendeu todos os criterios hoje. Mercado ainda em consolidacao.")

# --- RODAPE ---
st.markdown("---")
st.caption(f"Desenvolvido para o mercado brasileiro | Dados via Yahoo Finance | Ultima atualizacao: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
