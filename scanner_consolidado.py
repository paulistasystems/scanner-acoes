# -*- coding: utf-8 -*-
"""
SCANNER CONSOLIDADO DE AÇÕES - MERCADO BRASILEIRO
==================================================
Consolida todos os scanners de scalping e swing trade em um único script.

Modos disponíveis:
    - scalping      : Scanner de scalping (5m + 15m + 1H)
    - scalping_fast : Scanner de scalping rápido (5m + 15m + 1m)
    - swing         : Scanner de swing trade (Daily + 1H + 30M)
    - swing_rr      : Scanner de swing com RR (Daily + 1H + 30M + alvos)
    - swing_pro     : Scanner de swing profissional (Daily + 1H + 30M)
    - swing_exp     : Scanner de swing expandido (Mid + Small caps)
    - todos         : Executa todos os scanners (sequencial)

Uso: python scanner_consolidado.py [modo]
Exemplo: python scanner_consolidado.py scalping
"""

import sys
import subprocess
from datetime import datetime
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# Instalação automática de dependências
try:
    import pandas_ta
except ImportError:
    print("Instalando pandas_ta...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas_ta", "-q"])
    import pandas_ta

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


# ===================== FUNÇÕES UTILITÁRIAS =====================
def safe_float(x, default=0.0):
    """Converte valor para float com tratamento de erros."""
    try:
        if pd.isna(x) or x is None:
            return default
        return float(x)
    except:
        return default


def baixar_dados(symbol, interval, period):
    """Baixa dados do yfinance com tratamento de MultiIndex."""
    try:
        df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(1, axis=1)
        return df
    except:
        return pd.DataFrame()


# ===================== SCANNERS DE SCALPING =====================
def scanner_scalping_melhorado(ativos=ATIVOS_COMPLETO):
    """
    Scanner de Scalping Melhorado (5m + 15m + 1H)
    Filtros: Volume alto + Acima VWAP + Tendência 1H + RR claro
    """
    print(f"{'='*130}")
    print(f"🔄 SCANNER SCALPING PROFISSIONAL (5m + 15m + 1H) - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("Filtros: Volume explosivo + Acima VWAP + Tendência 1H + RR claro")
    print(f"{'='*130}\n")

    def gerar_analise_scalping(symbol):
        try:
            # ==================== 5 MINUTOS (Principal) ====================
            df5 = baixar_dados(symbol, '5m', '5d')
            if len(df5) < 200:
                return None, 0

            last5 = df5.iloc[-1]
            prev5 = df5.iloc[-2]
            preco = safe_float(last5['Close'])

            # Indicadores 5m
            df5['EMA8']   = ta.ema(df5['Close'], length=8)
            df5['EMA21']  = ta.ema(df5['Close'], length=21)
            df5['RSI']    = ta.rsi(df5['Close'], length=14)
            df5['ATR']    = ta.atr(df5['High'], df5['Low'], df5['Close'], length=14)
            df5['VWAP']   = ta.vwap(df5['High'], df5['Low'], df5['Close'], df5['Volume'])

            macd5 = ta.macd(df5['Close'])
            adx5 = ta.adx(df5['High'], df5['Low'], df5['Close'], length=14)

            vol20 = df5['Volume'].rolling(20).mean()
            vol_ratio = safe_float(last5['Volume']) / safe_float(vol20.iloc[-1])
            atr_val = safe_float(df5['ATR'].iloc[-1])
            rsi = safe_float(df5['RSI'].iloc[-1])
            macd_val = safe_float(macd5['MACD_12_26_9'].iloc[-1])
            adx_val = safe_float(adx5['ADX_14'].iloc[-1])
            vwap_val = safe_float(df5['VWAP'].iloc[-1])

            # ==================== 15 MINUTOS (Confirmação) ====================
            df15 = baixar_dados(symbol, '15m', '5d')
            score_15 = 0
            if len(df15) > 120:
                df15['EMA8'] = ta.ema(df15['Close'], length=8)
                df15['VWAP'] = ta.vwap(df15['High'], df15['Low'], df15['Close'], df15['Volume'])
                if preco > safe_float(df15['EMA8'].iloc[-1]): score_15 += 25
                if preco > safe_float(df15['VWAP'].iloc[-1]): score_15 += 20

            # ==================== 1H (Tendência Maior - Filtro Leve) ====================
            df1h = baixar_dados(symbol, '1h', '15d')
            tendencia_1h = "NEUTRA"
            if len(df1h) > 80:
                df1h['EMA20'] = ta.ema(df1h['Close'], length=20)
                if preco > safe_float(df1h['EMA20'].iloc[-1]):
                    tendencia_1h = "✅ ALTA"
                else:
                    tendencia_1h = "❌ BAIXA"

            # ==================== FILTROS RIGOROSOS ====================
            if vol_ratio < 2.5: return None, 0
            if safe_float(vol20.iloc[-1]) < 450_000: return None, 0
            if preco <= safe_float(df5['EMA8'].iloc[-1]): return None, 0
            if preco < vwap_val: return None, 0
            if adx_val < 28: return None, 0
            if rsi > 76 or rsi < 45: return None, 0
            if tendencia_1h == "❌ BAIXA": return None, 0

            # ==================== SCORE FINAL ====================
            score = 0
            if preco > safe_float(df5['EMA8'].iloc[-1]): score += 30
            if macd_val > 0: score += 20
            if vol_ratio > 4.0: score += 25
            if adx_val > 35: score += 15
            if 55 < rsi < 72: score += 15
            if atr_val / preco < 0.018: score += 10
            score += score_15

            var_atual = ((preco / safe_float(prev5['Close'])) - 1) * 100

            # ==================== SUPORTE / RESISTÊNCIA / STOP / ALVOS ====================
            suporte = safe_float(df5['Low'].rolling(30).min().iloc[-1])
            resistencia = safe_float(df5['High'].rolling(30).max().iloc[-1])

            stop_loss = preco - (atr_val * 1.6)
            risco = preco - stop_loss
            alvo1 = preco + (risco * 1.5)
            alvo2 = preco + (risco * 2.5)

            distancia_stop = ((preco - stop_loss) / preco) * 100

            texto = f"""
**🚀 {symbol.replace('.SA', '')}**   **Score: {score}/115**   {tendencia_1h}

**Preço:** R$ {preco:.2f}   |   Var 5m: {var_atual:+.2f}%

**5 Minutos (Principal):**
• Volume: {vol_ratio:.2f}x | ADX: {adx_val:.1f} | RSI: {rsi:.1f}
• VWAP: R$ {vwap_val:.2f} → Acima ✅
• Acima EMA8: ✅

**15 Minutos:** {'✅ Forte' if score_15 >= 35 else '⚠️ Moderada'}

**📍 Operação Sugerida:**
• Suporte: R$ {suporte:.2f}
• Resistência: R$ {resistencia:.2f}
• Stop Loss: R$ {stop_loss:.2f}  (-{distancia_stop:.2f}%)
• Alvo 1:1.5 → R$ {alvo1:.2f}
• Alvo 1:2.5 → R$ {alvo2:.2f}

**Resumo:** {'🔥 EXCELENTE SCALP' if score >= 95 else '✅ Boa Entrada' if score >= 80 else '📍 Monitorar'}
"""
            return texto, score
        except Exception as e:
            return None, 0

    resultados = []
    for symbol in ativos:
        res, score = gerar_analise_scalping(symbol)
        if res:
            resultados.append((score, res, symbol))

    resultados.sort(reverse=True)

    for score, texto, _ in resultados:
        print("=" * 125)
        print(texto)
        print("=" * 125)

    print(f"\n✅ Total de oportunidades de Scalping encontradas: {len(resultados)}")
    return len(resultados)


def scanner_scalping_rapido(ativos=ATIVOS_COMPLETO):
    """
    Scanner de Scalping Rápido (5m + 15m + 1m)
    Filtros reforçados: Volume alto + Acima VWAP + Tendência 15m + RR claro
    """
    print(f"{'='*130}")
    print(f"🔄 SCANNER SCALPING PROFISSIONAL (5m + 15m + 1m) - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("Filtros reforçados: Volume alto + Acima VWAP + Tendência 15m + RR claro")
    print(f"{'='*130}\n")

    def gerar_analise_scalping(symbol):
        try:
            # ==================== 5 MINUTOS (Principal) ====================
            df5 = baixar_dados(symbol, '5m', '5d')
            if len(df5) < 200:
                return None, 0

            last5 = df5.iloc[-1]
            prev5 = df5.iloc[-2]
            preco = safe_float(last5['Close'])

            # Indicadores 5m
            df5['EMA8']   = ta.ema(df5['Close'], length=8)
            df5['EMA21']  = ta.ema(df5['Close'], length=21)
            df5['RSI']    = ta.rsi(df5['Close'], length=14)
            df5['ATR']    = ta.atr(df5['High'], df5['Low'], df5['Close'], length=14)
            df5['VWAP']   = ta.vwap(df5['High'], df5['Low'], df5['Close'], df5['Volume'])

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

            # ==================== 15 MINUTOS (Tendência) ====================
            df15 = baixar_dados(symbol, '15m', '3d')
            tendencia_15 = "NEUTRA"
            score_15 = 0
            if len(df15) > 100:
                df15['EMA8'] = ta.ema(df15['Close'], length=8)
                df15['VWAP'] = ta.vwap(df15['High'], df15['Low'], df15['Close'], df15['Volume'])
                if preco > safe_float(df15['EMA8'].iloc[-1]):
                    tendencia_15 = "✅ ALTA"
                    score_15 += 25
                if preco > safe_float(df15['VWAP'].iloc[-1]):
                    score_15 += 20

            # ==================== 1 MINUTO (Timing) ====================
            df1 = baixar_dados(symbol, '1m', '1d')
            score_1m = 0
            if len(df1) > 150:
                df1['EMA8'] = ta.ema(df1['Close'], length=8)
                if preco > safe_float(df1['EMA8'].iloc[-1]): score_1m += 30

            # ==================== FILTROS RIGOROSOS ====================
            if vol_ratio < 2.5: return None, 0
            if vol_medio < 420_000: return None, 0
            if preco <= safe_float(df5['EMA8'].iloc[-1]): return None, 0
            if preco < vwap_val: return None, 0
            if adx_val < 28: return None, 0
            if rsi > 76 or rsi < 45: return None, 0

            # ==================== SCORE FINAL ====================
            score = 0
            if preco > safe_float(df5['EMA8'].iloc[-1]): score += 30
            if macd_val > 0: score += 20
            if vol_ratio > 4.0: score += 25
            if adx_val > 34: score += 15
            if 54 < rsi < 72: score += 15
            if atr_val / preco < 0.018: score += 10
            score += score_15 + (score_1m * 0.8)

            var_atual = ((preco / safe_float(prev5['Close'])) - 1) * 100

            # ==================== SUPORTE / RESISTÊNCIA / STOP / ALVOS ====================
            suporte = safe_float(df5['Low'].rolling(40).min().iloc[-1])
            resistencia = safe_float(df5['High'].rolling(40).max().iloc[-1])

            stop_loss = preco - (atr_val * 1.55)
            risco = preco - stop_loss
            alvo1 = preco + (risco * 1.5)
            alvo2 = preco + (risco * 2.5)

            distancia_stop = ((preco - stop_loss) / preco) * 100

            texto = f"""
**🚀 {symbol.replace('.SA', '')}**   **Score: {score:.0f}/120**   {tendencia_15}

**Preço:** R$ {preco:.2f}   |   Var 5m: {var_atual:+.2f}%

**5 Minutos (Principal):**
• Volume: {vol_ratio:.2f}x | ADX: {adx_val:.1f} | RSI: {rsi:.1f}
• VWAP: R$ {vwap_val:.2f} → Acima ✅
• Acima EMA8: ✅

**15m Tendência:** {tendencia_15}
**1 Minuto Timing:** {'✅ Forte' if score_1m >= 25 else '⚠️'}

**📍 Operação Sugerida:**
• Suporte: R$ {suporte:.2f}
• Resistência: R$ {resistencia:.2f}
• Stop Loss: R$ {stop_loss:.2f}  (-{distancia_stop:.2f}%)
• Alvo 1:1.5 → R$ {alvo1:.2f}
• Alvo 1:2.5 → R$ {alvo2:.2f}

**Resumo:** {'🔥 EXCELENTE SCALP' if score >= 95 else '✅ Boa Entrada' if score >= 80 else '📍 Monitorar'}
"""
            return texto, score
        except Exception as e:
            return None, 0

    resultados = []
    for symbol in ativos:
        res, score = gerar_analise_scalping(symbol)
        if res:
            resultados.append((score, res, symbol))

    resultados.sort(reverse=True)

    for score, texto, _ in resultados:
        print("=" * 130)
        print(texto)
        print("=" * 130)

    print(f"\n✅ Total de oportunidades de Scalping encontradas: {len(resultados)}")
    return len(resultados)


# ===================== SCANNERS DE SWING TRADE =====================
def analisar_timeframe_swing(df, tf_name="Daily", incluir_atr=False):
    """Análise comum para swing trade em um timeframe."""
    if len(df) < 100:
        return 0, "", 0, 0, 0, 0

    last = df.iloc[-1]
    prev = df.iloc[-2]
    preco = safe_float(last['Close'])

    df['EMA9']  = ta.ema(df['Close'], length=9)
    df['EMA20'] = ta.ema(df['Close'], length=20)
    df['EMA50'] = ta.ema(df['Close'], length=50)
    df['RSI']   = ta.rsi(df['Close'], length=14)
    df['ATR']   = ta.atr(df['High'], df5['Low'], df5['Close'], length=14)

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

    tendencia = "✅ ALTA" if preco > safe_float(df['EMA20'].iloc[-1]) else "❌ BAIXA"

    info = f"**{tf_name}** {tendencia} | ADX {adx_val:.1f} | RSI {rsi:.1f} | Score {score}"

    return score, info, adx_val, rsi, vol_ratio, atr_val


def scanner_swing_hibrido(ativos=ATIVOS_BLUE_CHIPS):
    """
    Scanner Swing Trade Híbrido (Daily + 1H + 30M)
    Filtros reforçados: Daily forte + Liquidez + Alinhamento multi-TF
    """
    print(f"{'='*110}")
    print(f"🔄 SCANNER SWING TRADE HÍBRIDO (Daily + 1H + 30M) - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("Filtros reforçados: Daily forte + Liquidez + Alinhamento multi-TF")
    print(f"{'='*110}\n")

    def gerar_analise_swing(symbol):
        try:
            # ==================== DAILY (Tendência Base) ====================
            df_d = baixar_dados(symbol, '1d', '1y')
            if len(df_d) < 150:
                return None, 0

            daily_score, daily_info, daily_adx, daily_rsi, daily_vol_ratio, _ = analisar_timeframe_swing(df_d, "📅 Daily")

            last_d = df_d.iloc[-1]
            preco = safe_float(last_d['Close'])

            # Filtros fortes no Daily
            if daily_vol_ratio < 1.7: return None, 0
            if safe_float(last_d['Volume'].rolling(20).mean().iloc[-1]) < 8_000_000: return None, 0
            if daily_adx < 22: return None, 0
            if not (47 < daily_rsi < 73): return None, 0
            if preco <= safe_float(df_d['EMA50'].iloc[-1]): return None, 0

            # ==================== 1H (Setup Principal) ====================
            df_h = baixar_dados(symbol, '1h', '60d')
            h_score, h_info, h_adx, h_rsi, h_vol_ratio, _ = analisar_timeframe_swing(df_h, "🕐 1H") if len(df_h) > 180 else (0, "", 0, 0, 0, 0)

            # ==================== 30M (Timing) ====================
            df_30 = baixar_dados(symbol, '30m', '15d')
            score_30 = 0
            if len(df_30) > 200:
                df_30['EMA9'] = ta.ema(df_30['Close'], length=9)
                df_30['RSI'] = ta.rsi(df_30['Close'], length=14)
                if preco > safe_float(df_30['EMA9'].iloc[-1]): score_30 += 25
                if safe_float(df_30['RSI'].iloc[-1]) > 52: score_30 += 20

            # ==================== SCORE FINAL PONDERADO ====================
            score_total = (daily_score * 1.6) + h_score + score_30

            alinhamento = "✅ FORTE" if (daily_adx > 25 and h_adx > 23) else "⚠️ Parcial"

            texto = f"""
**🚀 {symbol.replace('.SA', '')}**   **Score Total: {score_total:.0f}/280**   {alinhamento}

**Preço Atual:** R$ {preco:.2f}

{daily_info}
{h_info}
**30M Timing:** {'✅ Alinhado' if score_30 >= 35 else '⚠️ Monitorar'}

**Volume:** {h_vol_ratio:.2f}x (1h) | {daily_vol_ratio:.2f}x (Daily)
**Resumo:** {'🔥 EXCELENTE' if score_total >= 200 else '✅ Boa' if score_total >= 160 else '📍 Monitorar'}
"""
            return texto, score_total
        except Exception as e:
            return None, 0

    resultados = []
    for symbol in ativos:
        res, score = gerar_analise_swing(symbol)
        if res:
            resultados.append((score, res, symbol))

    resultados.sort(reverse=True)

    for score, texto, _ in resultados:
        print("=" * 110)
        print(texto)
        print("=" * 110)

    if len(resultados) == 0:
        print("Nenhum ativo atendeu os critérios rigorosos no momento.")
    else:
        print(f"\n✅ Total de oportunidades encontradas: {len(resultados)}")
    return len(resultados)


def scanner_swing_rr(ativos=ATIVOS_BLUE_CHIPS):
    """
    Scanner Swing Trade Híbrido + Risk/Reward (Daily + 1H + 30M + Alvos)
    Filtros reforçados + Suporte/Resistência + Stop + Alvos 1:2 e 1:3
    """
    print(f"{'='*120}")
    print(f"🔄 SCANNER SWING TRADE HÍBRIDO + RR - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("Filtros reforçados + Suporte/Resistência + Stop + Alvos 1:2 e 1:3")
    print(f"{'='*120}\n")

    def gerar_analise_swing(symbol):
        try:
            # ==================== DAILY ====================
            df_d = baixar_dados(symbol, '1d', '1y')
            if len(df_d) < 150: return None, 0

            daily_score, daily_info, daily_adx, daily_rsi, daily_vol_ratio, daily_atr = analisar_timeframe_swing(df_d, "📅 Daily", incluir_atr=True)

            last_d = df_d.iloc[-1]
            preco = safe_float(last_d['Close'])

            # Filtros Daily
            vol_medio_diario = safe_float(last_d['Volume'].rolling(20).mean().iloc[-1])
            if daily_vol_ratio < 1.7: return None, 0
            if vol_medio_diario < 8_000_000: return None, 0
            if daily_adx < 22: return None, 0
            if not (47 < daily_rsi < 73): return None, 0
            if preco <= safe_float(df_d['EMA50'].iloc[-1]): return None, 0

            # ==================== 1H ====================
            df_h = baixar_dados(symbol, '1h', '60d')
            h_score, h_info, h_adx, h_rsi, h_vol_ratio, _ = analisar_timeframe_swing(df_h, "🕐 1H") if len(df_h) > 180 else (0, "", 0, 0, 0, 0)

            # ==================== 30M ====================
            df_30 = baixar_dados(symbol, '30m', '15d')
            score_30 = 0
            if len(df_30) > 200:
                df_30['EMA9'] = ta.ema(df_30['Close'], length=9)
                df_30['RSI'] = ta.rsi(df_30['Close'], length=14)
                if preco > safe_float(df_30['EMA9'].iloc[-1]): score_30 += 25
                if safe_float(df_30['RSI'].iloc[-1]) > 52: score_30 += 20

            # ==================== CÁLCULO DE SUPORTE / RESISTÊNCIA / STOP / ALVOS ====================
            suporte = safe_float(df_d['Low'].rolling(20).min().iloc[-1])
            resistencia = safe_float(df_d['High'].rolling(20).max().iloc[-1])

            stop_atr = preco - (daily_atr * 1.8)
            risco = preco - stop_atr
            alvo2 = preco + (risco * 2)
            alvo3 = preco + (risco * 3)

            distancia_stop = ((preco - stop_atr) / preco) * 100

            # Score Final
            score_total = (daily_score * 1.6) + h_score + score_30

            alinhamento = "✅ FORTE" if (daily_adx > 25 and h_adx > 23) else "⚠️ Parcial"

            texto = f"""
**🚀 {symbol.replace('.SA', '')}**   **Score Total: {score_total:.0f}/280**   {alinhamento}

**Preço Atual:** R$ {preco:.2f}

{daily_info}
{h_info}
**30M Timing:** {'✅ Alinhado' if score_30 >= 35 else '⚠️ Monitorar'}

**Volume:** {h_vol_ratio:.2f}x (1h) | {daily_vol_ratio:.2f}x (Daily)

**📍 Estrutura Técnica:**
- Suporte: R$ {suporte:.2f}
- Resistência: R$ {resistencia:.2f}
- Stop Sugerido: R$ {stop_atr:.2f}  (-{distancia_stop:.2f}%)
- Alvo 1:2 → R$ {alvo2:.2f}
- Alvo 1:3 → R$ {alvo3:.2f}

**Resumo:** {'🔥 EXCELENTE' if score_total >= 200 else '✅ Boa' if score_total >= 160 else '📍 Monitorar'}
"""
            return texto, score_total
        except Exception as e:
            return None, 0

    resultados = []
    for symbol in ativos:
        res, score = gerar_analise_swing(symbol)
        if res:
            resultados.append((score, res, symbol))

    resultados.sort(reverse=True)

    for score, texto, _ in resultados:
        print("=" * 120)
        print(texto)
        print("=" * 120)

    if len(resultados) == 0:
        print("Nenhum ativo atendeu os critérios rigorosos no momento.")
    else:
        print(f"\n✅ Total de oportunidades encontradas: {len(resultados)}")
    return len(resultados)


def scanner_swing_profissional(ativos=ATIVOS_BLUE_CHIPS):
    """
    Scanner Swing Trade Profissional (Daily + 1H + 30M)
    Filtros: Vol >1.5x | Acima EMA20/50 | ADX>20 | RSI 45-75 | Alinhamento 1H+30M
    """
    print(f"{'='*100}")
    print(f"🔄 SCANNER SWING TRADE PROFISSIONAL - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("Filtros: Vol >1.5x | Acima EMA20/50 | ADX>20 | RSI 45-75 | Alinhamento 1H+30M")
    print(f"{'='*100}\n")

    def analisar_timeframe(df, tf_name="Daily"):
        if len(df) < 50:
            return None

        last = df.iloc[-1]
        prev = df.iloc[-2]
        preco = safe_float(last['Close'])

        df['EMA9']  = ta.ema(df['Close'], length=9)
        df['EMA20'] = ta.ema(df['Close'], length=20)
        df['EMA50'] = ta.ema(df['Close'], length=50)
        df['RSI']   = ta.rsi(df['Close'], length=14)
        df['ATR']   = ta.atr(df['High'], df['Low'], df['Close'], length=14)

        macd = ta.macd(df['Close'])
        adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)

        vol20 = df['Volume'].rolling(20).mean()
        vol_ratio = safe_float(last['Volume']) / safe_float(vol20.iloc[-1])

        rsi = safe_float(df['RSI'].iloc[-1])
        adx_val = safe_float(adx['ADX_14'].iloc[-1])
        macd_val = safe_float(macd['MACD_12_26_9'].iloc[-1])

        # Score por timeframe
        score_tf = 0
        if preco > safe_float(df['EMA9'].iloc[-1]): score_tf += 25
        if preco > safe_float(df['EMA20'].iloc[-1]): score_tf += 20
        if macd_val > 0: score_tf += 20
        if adx_val > 25: score_tf += 15
        if 52 < rsi < 73: score_tf += 20

        tendencia = "✅ ALTA" if preco > safe_float(df['EMA20'].iloc[-1]) else "❌ BAIXA"

        texto = f"""
**{tf_name}** {tendencia} (Score: {score_tf}/100)
• Preço: R$ {preco:.2f} | Var: {((preco / safe_float(prev['Close']))-1)*100:+.2f}%
• RSI: {rsi:.1f} | MACD: {macd_val:.4f} | ADX: {adx_val:.1f}
• ATR: R$ {safe_float(df['ATR'].iloc[-1]):.2f} ({(safe_float(df['ATR'].iloc[-1])/preco*100):.2f}%)
• Volume: {vol_ratio:.2f}x média
"""
        return texto, score_tf, tendencia, rsi, adx_val

    def gerar_analise_swing(symbol):
        try:
            # ===================== DAILY =====================
            df_daily = yf.download(symbol, period="1y", interval="1d", progress=False, auto_adjust=True)
            if isinstance(df_daily.columns, pd.MultiIndex):
                df_daily = df_daily.droplevel(1, axis=1)
            if len(df_daily) < 120:
                return None, 0

            daily_texto, daily_score, daily_tend, daily_rsi, daily_adx = analisar_timeframe(df_daily, "Daily")

            # Filtros principais (Daily)
            last_daily = df_daily.iloc[-1]
            vol_ratio_daily = safe_float(last_daily['Volume']) / safe_float(df_daily['Volume'].rolling(20).mean().iloc[-1])

            if vol_ratio_daily < 1.5: return None, 0
            if safe_float(last_daily['Close']) <= safe_float(df_daily['EMA20'].iloc[-1]): return None, 0
            if safe_float(last_daily['Close']) <= safe_float(df_daily['EMA50'].iloc[-1]): return None, 0
            if daily_adx < 20: return None, 0
            if not (45 < daily_rsi < 75): return None, 0

            # ===================== 1H =====================
            df_1h = yf.download(symbol, period="60d", interval="1h", progress=False, auto_adjust=True)
            if isinstance(df_1h.columns, pd.MultiIndex):
                df_1h = df_1h.droplevel(1, axis=1)
            h1_texto, h1_score, h1_tend, h1_rsi, h1_adx = analisar_timeframe(df_1h, "1H")

            # ===================== 30M =====================
            df_30m = yf.download(symbol, period="15d", interval="30m", progress=False, auto_adjust=True)
            if isinstance(df_30m.columns, pd.MultiIndex):
                df_30m = df_30m.droplevel(1, axis=1)
            m30_texto, m30_score, m30_tend, m30_rsi, m30_adx = analisar_timeframe(df_30m, "30M")

            # Score Total
            score_total = daily_score + h1_score + m30_score

            texto_final = f"""
**🚀 {symbol.replace('.SA', '')}**  **(Score Total: {score_total}/300)**

**Preço Atual:** R$ {safe_float(last_daily['Close']):.2f}   |   Vol: {vol_ratio_daily:.2f}x

{daily_texto}
{h1_texto}
{m30_texto}

**Alinhamento Multi-Timeframe:** {'✅ FORTE' if h1_tend == m30_tend == daily_tend else '⚠️ PARCIAL'}
"""
            return texto_final, score_total
        except Exception as e:
            print(f"Erro em {symbol}: {e}")
            return None, 0

    resultados = []
    for symbol in ativos:
        res, score = gerar_analise_swing(symbol)
        if res:
            resultados.append((score, res, symbol))

    resultados.sort(reverse=True)

    for score, texto, _ in resultados:
        print("=" * 100)
        print(texto)
        print("=" * 100)

    if len(resultados) == 0:
        print("Nenhum ativo atendeu todos os critérios no momento.")
    else:
        print(f"\n✅ Total de oportunidades encontradas: {len(resultados)}")
    return len(resultados)


def scanner_swing_expandido(ativos=ATIVOS_COMPLETO):
    """
    Scanner Swing Trade Expandido (Mid + Small Caps)
    Lista atualizada 2026 | Critérios rigorosos mantidos + Confluência 1h/30m
    """
    print(f"{'='*100}")
    print(f"🔄 SCANNER SWING TRADE LIMPO - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("Lista atualizada 2026 | Critérios rigorosos mantidos + Confluência 1h/30m")
    print(f"{'='*100}\n")

    def gerar_analise_swing(symbol):
        try:
            # ==================== DAILY (Swing) ====================
            df = yf.download(symbol, period="1y", interval="1d", progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df = df.droplevel(1, axis=1)
            if len(df) < 120:
                return None, 0

            last = df.iloc[-1]
            prev = df.iloc[-2]
            preco = safe_float(last['Close'])

            df['EMA9']  = ta.ema(df['Close'], length=9)
            df['EMA20'] = ta.ema(df['Close'], length=20)
            df['EMA50'] = ta.ema(df['Close'], length=50)
            df['RSI']   = ta.rsi(df['Close'], length=14)
            df['ATR']   = ta.atr(df['High'], df['Low'], df['Close'], length=14)

            macd = ta.macd(df['Close'])
            macd_val = safe_float(macd['MACD_12_26_9'].iloc[-1])

            adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
            adx_val = safe_float(adx['ADX_14'].iloc[-1])

            df['Vol20'] = df['Volume'].rolling(20).mean()
            vol_ratio = safe_float(last['Volume']) / safe_float(df['Vol20'].iloc[-1])
            vol_medio = safe_float(df['Vol20'].iloc[-1])

            # FILTROS RIGOROSOS (mantidos)
            if vol_ratio < 1.5: return None, 0
            if vol_medio < 2_500_000: return None, 0
            if preco <= safe_float(df['EMA20'].iloc[-1]): return None, 0
            if preco <= safe_float(df['EMA50'].iloc[-1]): return None, 0
            if adx_val < 20: return None, 0

            rsi = safe_float(df['RSI'].iloc[-1])
            if rsi > 75 or rsi < 45: return None, 0

            # Score Diário
            score = 0
            if preco > safe_float(df['EMA9'].iloc[-1]): score += 20
            if macd_val > 0: score += 20
            if vol_ratio > 2.5: score += 20
            if adx_val > 25: score += 15
            if 55 < rsi < 72: score += 15
            if safe_float(df['ATR'].iloc[-1]) / preco < 0.045: score += 10

            var_dia = ((preco / safe_float(prev['Close'])) - 1) * 100
            atr_dia = safe_float(df['ATR'].iloc[-1])

            # ==================== 1H (Principal) ====================
            rsi_1h = macd_1h = adx_1h = atr_1h = 0.0
            acima_ema20_50_1h = False
            tendencia_1h = "Sem dados suficientes"
            confluencia_1h = "Fraca"

            try:
                df_1h = yf.download(symbol, period="75d", interval="1h", progress=False, auto_adjust=True)
                if isinstance(df_1h.columns, pd.MultiIndex):
                    df_1h = df_1h.droplevel(1, axis=1)
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

                    acima_ema20_50_1h = close_1h > ema20_1h and close_1h > ema50_1h
                    rsi_1h = safe_float(df_1h['RSI'].iloc[-1])
                    macd_1h = safe_float(macd_1h_df['MACD_12_26_9'].iloc[-1])
                    adx_1h = safe_float(adx_1h_df['ADX_14'].iloc[-1])

                    if acima_ema20_50_1h and adx_1h > 20 and 50 < rsi_1h < 75 and macd_1h > 0:
                        confluencia_1h = "Boa ✅"
                        tendencia_1h = "Alta forte"
                    elif acima_ema20_50_1h:
                        confluencia_1h = "Parcial"
                        tendencia_1h = "Alta moderada"
                    else:
                        tendencia_1h = "Consolidação / Baixa"
            except:
                pass

            # ==================== 30M (Auxiliar) ====================
            rsi_30m = macd_30m = adx_30m = atr_30m = 0.0
            acima_ema20_50_30m = False
            tendencia_30m = "Sem dados suficientes"
            confluencia_30m = "Fraca"

            try:
                df_30m = yf.download(symbol, period="45d", interval="30m", progress=False, auto_adjust=True)
                if isinstance(df_30m.columns, pd.MultiIndex):
                    df_30m = df_30m.droplevel(1, axis=1)
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

                    acima_ema20_50_30m = close_30m > ema20_30m and close_30m > ema50_30m
                    rsi_30m = safe_float(df_30m['RSI'].iloc[-1])
                    macd_30m = safe_float(macd_30m_df['MACD_12_26_9'].iloc[-1])
                    adx_30m = safe_float(adx_30m_df['ADX_14'].iloc[-1])

                    if acima_ema20_50_30m and adx_30m > 20 and 50 < rsi_30m < 75 and macd_30m > 0:
                        confluencia_30m = "Boa ✅"
                        tendencia_30m = "Alta forte"
                    elif acima_ema20_50_30m:
                        confluencia_30m = "Parcial"
                        tendencia_30m = "Alta moderada"
                    else:
                        tendencia_30m = "Consolidação / Baixa"
            except:
                pass

            # Confluência combinada
            if confluencia_1h == "Boa ✅" and confluencia_30m == "Boa ✅":
                confluencia_geral = "Excelente ✅✅"
            elif confluencia_1h == "Boa ✅" or confluencia_30m == "Boa ✅":
                confluencia_geral = "Boa ✅"
            elif confluencia_1h == "Parcial" and confluencia_30m == "Parcial":
                confluencia_geral = "Parcial"
            else:
                confluencia_geral = "Fraca / Sem confluência"

            # ==================== TEXTO FINAL ====================
            texto = f"""
**Ativo:** {symbol.replace('.SA', '')} **(Score Diário: {score}/100)** 🔥

**Preço:** R$ {preco:.2f}   |   Variação: {var_dia:+.2f}%

**Volume:** {vol_ratio:.2f}x média 20d  |  Média: {vol_medio/1_000_000:.1f}M

**Tendência Diária:** Forte ✅
- Acima EMA9 / EMA20 / EMA50
- ADX {adx_val:.1f} ({'Forte' if adx_val > 25 else 'Moderada'})

**Osciladores Diários:**
- RSI (14): {rsi:.1f}
- MACD: {macd_val:.3f}
- ATR: R$ {atr_dia:.2f} ({(atr_dia/preco*100):.2f}%)

**Confluência 1h (Principal):**
- Tendência: {tendencia_1h}
- Acima EMA20/EMA50: {'Sim ✅' if acima_ema20_50_1h else 'Não ❌'}
- RSI (14): {rsi_1h:.1f}   |   MACD: {macd_1h:.3f}
- ADX: {adx_1h:.1f}   |   ATR: R$ {atr_1h:.2f}
- Status: {confluencia_1h}

**Confluência 30m (Auxiliar):**
- Tendência: {tendencia_30m}
- Acima EMA20/EMA50: {'Sim ✅' if acima_ema20_50_30m else 'Não ❌'}
- RSI (14): {rsi_30m:.1f}   |   MACD: {macd_30m:.3f}
- ADX: {adx_30m:.1f}   |   ATR: R$ {atr_30m:.2f}
- Status: {confluencia_30m}

**Confluência Geral (1h + 30m):** {confluencia_geral}
"""
            return texto, score
        except Exception as e:
            return None, 0

    resultados = []
    for symbol in ativos:
        res, score = gerar_analise_swing(symbol)
        if res:
            resultados.append((score, res, symbol))

    resultados.sort(reverse=True)

    for score, texto, _ in resultados:
        print("=" * 100)
        print(texto)
        print("=" * 100)

    if len(resultados) == 0:
        print("Nenhum ativo atendeu todos os critérios hoje.")
        print("Mercado ainda em consolidação. Continue rodando todo dia após o fechamento.")
    else:
        print(f"\n✅ Total de oportunidades encontradas: {len(resultados)}")
        print("⚠️  Apenas considere entrada se Confluência Geral = Boa ou Excelente + Score Diário ≥ 65")
    return len(resultados)


# ===================== FUNÇÃO PRINCIPAL =====================
def main():
    """Função principal com selector de modo."""
    modos = {
        'scalping': scanner_scalping_melhorado,
        'scalping_fast': scanner_scalping_rapido,
        'swing': scanner_swing_hibrido,
        'swing_rr': scanner_swing_rr,
        'swing_pro': scanner_swing_profissional,
        'swing_exp': scanner_swing_expandido,
        'todos': None  # Caso especial
    }

    if len(sys.argv) < 2:
        print("=" * 60)
        print("SCANNER CONSOLIDADO DE AÇÕES - MERCADO BRASILEIRO")
        print("=" * 60)
        print("\nModos disponíveis:")
        for modo in modos:
            if modo != 'todos':
                print(f"  • {modo:<15} - {modos[modo].__doc__.split('.')[0] if modos[modo].__doc__ else ''}")
        print(f"  • {'todos':<15} - Executa todos os scanners sequencialmente")
        print("\nUso: python scanner_consolidado.py [modo]")
        print("Exemplo: python scanner_consolidado.py scalping")
        print("\nModo padrão: todos (executa todos os scanners)")
        print("=" * 60)
        modo = 'todos'
    else:
        modo = sys.argv[1].lower()

    if modo == 'todos':
        print("\n🔄 EXECUTANDO TODOS OS SCANNERS SEQUENCIALMENTE\n")
        print("=" * 130)
        total_geral = 0
        for m, scanner in modos.items():
            if m != 'todos':
                print(f"\n\n{'#' * 130}")
                print(f"# MODO: {m.upper()}")
                print(f"{'#' * 130}\n")
                resultado = scanner()
                total_geral += resultado if resultado else 0
        print(f"\n{'=' * 130}")
        print(f"✅ TOTAL GERAL DE OPORTUNIDADES EM TODOS OS SCANNERS: {total_geral}")
        print(f"{'=' * 130}")
    elif modo in modos:
        modos[modo]()
    else:
        print(f"❌ Modo '{modo}' não reconhecido.")
        print(f"Modos disponíveis: {', '.join(modos.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
