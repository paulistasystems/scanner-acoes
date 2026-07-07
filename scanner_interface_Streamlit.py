# -*- coding: utf-8 -*-
"""
SCANNER CONSOLIDADO - VERSÃO MELHORADA
- Sliders para Volume, ADX e RSI
- ADX Rising + DI+/DI-
- Avaliação da Tríade (ADX + RSI + Volume)
- 4 scanners diferenciados
- Sinais de saída
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
from datetime import datetime
import data_layer

# Page config
st.set_page_config(page_title="Scanner Ações BR", layout="wide", page_icon="📈")
st.title("📈 SCANNER CONSOLIDADO DE AÇÕES - BRASIL")

# ===================== PERFIS DE ANÁLISE =====================
PROFILES = {
    "🛡️ Conservador": {
        "adx_min": 20,
        "rsi_min": 45,
        "rsi_max": 65,
        "vol_ratio": 1.5,
        "vol_medio_min": 1_000_000,
        "desc": "Menos setups, maior qualidade. Volume forte (1.5x) + liquidez mínima 1M + tendência clara."
    },
    "⚖️ Moderado": {
        "adx_min": 15,
        "rsi_min": 40,
        "rsi_max": 70,
        "vol_ratio": 1.2,
        "vol_medio_min": 500_000,
        "desc": "Equilíbrio entre quantidade e qualidade. Volume moderado (1.2x) + liquidez mínima 500K."
    },
    "🔥 Agressivo": {
        "adx_min": 15,
        "rsi_min": 40,
        "rsi_max": 80,
        "vol_ratio": 0.8,
        "vol_medio_min": 300_000,
        "desc": "Máximo de oportunidades. Volume permissivo (0.8x) + liquidez mínima 300K."
    },
}
DEFAULT_PROFILE = "🛡️ Conservador"
ADX_RISING_PERIODS = 5

# Chaves de cache dos resultados dos scanners em st.session_state.
# Definido no escopo do módulo (e não dentro do corpo do script) para estar
# sempre disponível no callback on_change do radio de perfil, que executa
# ANTES do corpo do script a cada rerun.
#
# Os caches são separados por FAMÍLIA para garantir independência total entre
# os scanners Evolved (dependem do perfil/seletores) e os Legacy (filtros
# hardcoded). Trocar de perfil ou clicar em "Atualizar Scanners" invalida só
# os Evolved; o botão "Atualizar Legacy" invalida só os Legacy. Assim o
# resultado de uma família nunca é perturbado pela outra.
EVOLVED_CACHE_KEYS = ['df_fusion', 'df_hibrido', 'df_rr', 'df_pro', 'df_exp']
LEGACY_CACHE_KEYS = ['df_legacy_prof', 'df_legacy_intra', 'df_legacy_exp']
SCANNER_CACHE_KEYS = EVOLVED_CACHE_KEYS + LEGACY_CACHE_KEYS  # init na carga da página

# ===================== LISTAS POR CATEGORIA (BUSCA UNIVERSAL) =====================

# Ações - Bancos / Financeiras / Seguros
UNIV_BANCOS = [
    'ITUB4.SA', 'BBAS3.SA', 'BBDC4.SA', 'BBDC3.SA', 'SANB11.SA',
    'BPAC11.SA', 'ITSA4.SA', 'BBSE3.SA', 'PSSA3.SA', 'BRSR6.SA',
    'ABCB4.SA', 'BMGB4.SA',
]

# Ações - Energia Elétrica
UNIV_ENERGIA = [
    'EQTL3.SA', 'CMIG4.SA', 'CPFE3.SA',
    'ENGI11.SA', 'CPLE3.SA', 'NEOE3.SA', 'AURE3.SA', 'TAEE11.SA',
    'EGIE3.SA', 'COCE5.SA', 'ENEV3.SA',
    'CSMG3.SA', 'SBSP3.SA', 'SAPR11.SA',
]

# Ações - Petróleo / Gás / Distribuição
UNIV_PETROLEO = [
    'PETR4.SA', 'PETR3.SA', 'PRIO3.SA', 'CSAN3.SA', 'UGPA3.SA',
    'VBBR3.SA', 'RECV3.SA', 'RAIZ4.SA',
]

# Ações - Mineração / Siderurgia / Metalurgia
UNIV_MINERACAO = [
    'VALE3.SA', 'GGBR4.SA', 'GGBR3.SA', 'GOAU4.SA', 'USIM5.SA',
    'CSNA3.SA', 'CMIN3.SA', 'FESA4.SA', 'BRKM5.SA', 'UNIP6.SA',
]

# Ações - Varejo / Consumo
UNIV_VAREJO = [
    'LREN3.SA', 'MGLU3.SA', 'GRND3.SA', 'ALPA4.SA', 'CEAB3.SA',
    'RIAA3.SA', 'LJQQ3.SA', 'BHIA3.SA', 'AMAR3.SA', 'VULC3.SA',
]

# Ações - Saúde / Farmacêutica
UNIV_SAUDE = [
    'HAPV3.SA', 'RDOR3.SA', 'FLRY3.SA', 'HYPE3.SA', 'RADL3.SA',
    'ONCO3.SA', 'BLAU3.SA', 'AALR3.SA',
]

# Ações - Imobiliário / Construção
UNIV_IMOBILIARIO = [
    'MRVE3.SA', 'CYRE3.SA', 'EVEN3.SA', 'EZTC3.SA', 'DIRR3.SA',
    'TEND3.SA', 'LAVV3.SA', 'TRIS3.SA', 'MDNE3.SA', 'CURY3.SA',
    'PLPL3.SA', 'MELK3.SA', 'MTRE3.SA', 'GFSA3.SA',
]

# Ações - Alimentos / Agro / Bebidas
UNIV_ALIMENTOS = [
    'ABEV3.SA', 'JBSS32.SA', 'BRFT11.SA', 'MBRF3.SA', 'BEEF3.SA',
    'MDIA3.SA', 'SMTO3.SA', 'SLCE3.SA', 'AGRO3.SA', 'CAML3.SA',
    'JALL3.SA',
]

# Ações - Transportes / Logística / Aéreas
UNIV_TRANSPORTES = [
    'ECOR3.SA', 'EMBJ3.SA',
    'RAIL3.SA', 'TGMA3.SA', 'HBSA3.SA', 'LOGN3.SA',
]

# Ações - Telecom / Tecnologia
UNIV_TECH = [
    'VIVT3.SA', 'TIMS3.SA', 'TOTS3.SA', 'LWSA3.SA', 'POSI3.SA',
    'INTB3.SA', 'CASH3.SA', 'BMOB3.SA', 'MLAS3.SA',
    'DESK3.SA', 'SEQL3.SA',
]

# Ações - Industrial / Bens de Capital
UNIV_INDUSTRIAL = [
    'WEGE3.SA', 'B3SA3.SA', 'RENT3.SA', 'VAMO3.SA', 'SIMH3.SA',
    'KEPL3.SA', 'TUPY3.SA', 'POMO4.SA', 'RAPT4.SA', 'LEVE3.SA',
    'MILS3.SA', 'WIZC3.SA', 'MULT3.SA', 'IGTI11.SA',
]

# Ações - Papel / Celulose
UNIV_PAPEL = [
    'KLBN11.SA', 'SUZB3.SA', 'DXCO3.SA',
]

# Ações - Educação
UNIV_EDUCACAO = [
    'COGN3.SA', 'YDUQ3.SA', 'ANIM3.SA', 'SEER3.SA',
]

# ===================== BDRs (Brazilian Depositary Receipts) =====================

# BDRs - Tecnologia
BDR_TECH = [
    'AAPL34.SA', 'MSFT34.SA', 'AMZO34.SA', 'GOGL34.SA', 'NVDC34.SA',
    'TSLA34.SA', 'NFLX34.SA', 'ADBE34.SA', 'ORCL34.SA',
    'CSCO34.SA', 'AVGO34.SA', 'QCOM34.SA', 'A1MD34.SA',
    'PYPL34.SA', 'U1BE34.SA', 'S1PO34.SA',
]

# BDRs - Finanças
BDR_FINANCAS = [
    'JPMC34.SA', 'BOAC34.SA', 'GSGI34.SA', 'MSBR34.SA', 'BERK34.SA',
    'VISA34.SA',
]

# BDRs - Consumo / Varejo
BDR_CONSUMO = [
    'COCA34.SA', 'PEPB34.SA', 'MCDC34.SA', 'NIKE34.SA', 'SBUB34.SA',
    'PGCO34.SA', 'WALM34.SA', 'HOME34.SA', 'DISB34.SA',
]

# BDRs - Saúde / Farma
BDR_SAUDE = [
    'JNJB34.SA', 'PFIZ34.SA', 'MRCK34.SA', 'ABBV34.SA', 'LILY34.SA',
]

# BDRs - Industrial / Energia / Outros
BDR_INDUSTRIAL = [
    'CATP34.SA', 'HONB34.SA', 'MMMC34.SA',
    'EXXO34.SA', 'CHVX34.SA', 'DHER34.SA',
]

# ===================== ETFs =====================
ETFS_B3 = [
    # Índices Brasil
    'BOVA11.SA', 'BOVV11.SA', 'SMAL11.SA', 'XBOV11.SA', 'DIVO11.SA',
    'MATB11.SA', 'FIND11.SA', 'GOVE11.SA', 'PIBB11.SA',
    # Índices Internacionais
    'IVVB11.SA', 'SPXI11.SA', 'NASD11.SA',
    # Temáticos / Setoriais
    'HASH11.SA', 'QBTC11.SA', 'ETHE11.SA', 'GOLD11.SA',
    'TECK11.SA', 'JURO11.SA',
    # Renda Fixa
    'IMAB11.SA', 'IRFM11.SA', 'B5P211.SA', 'FIXA11.SA',
]

# ===================== FIIs (Fundos Imobiliários) =====================
FIIS_B3 = [
    # Logístico
    'HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VILG11.SA', 'BRCO11.SA',
    # Shopping / Varejo
    'XPML11.SA', 'VISC11.SA', 'HSML11.SA',
    # Lajes Corporativas
    'KNRI11.SA', 'PVBI11.SA', 'JSRE11.SA', 'BRCR11.SA', 'RCRB11.SA',
    # Papel (CRI / CRA)
    'MXRF11.SA', 'CPTS11.SA', 'IRDM11.SA', 'RBRR11.SA', 'RECR11.SA',
    'VGIP11.SA', 'KNCR11.SA', 'HGCR11.SA',
    # Híbridos / Diversificados
    'HGBS11.SA', 'ALZR11.SA', 'TRXF11.SA', 'TGAR11.SA',
    'RBRF11.SA',
]

# ===================== LISTA MASTER COMBINADA =====================
_ACOES_UNIVERSAL = (
    UNIV_BANCOS + UNIV_ENERGIA + UNIV_PETROLEO + UNIV_MINERACAO +
    UNIV_VAREJO + UNIV_SAUDE + UNIV_IMOBILIARIO + UNIV_ALIMENTOS +
    UNIV_TRANSPORTES + UNIV_TECH + UNIV_INDUSTRIAL + UNIV_PAPEL + UNIV_EDUCACAO
)
_BDRS_UNIVERSAL = BDR_TECH + BDR_FINANCAS + BDR_CONSUMO + BDR_SAUDE + BDR_INDUSTRIAL
_ETFS_UNIVERSAL = ETFS_B3
_FIIS_UNIVERSAL = FIIS_B3

ATIVOS_B3_AMPLIADO = list(set(
    _ACOES_UNIVERSAL + _BDRS_UNIVERSAL + _ETFS_UNIVERSAL + _FIIS_UNIVERSAL
))

# Contadores por categoria (para exibição na interface)
CONTAGEM_CATEGORIAS = {
    'Ações': len(set(_ACOES_UNIVERSAL)),
    'BDRs': len(set(_BDRS_UNIVERSAL)),
    'ETFs': len(set(_ETFS_UNIVERSAL)),
    'FIIs': len(set(_FIIS_UNIVERSAL)),
}


# ===================== FUNÇÕES UTILITÁRIAS =====================
def baixar_dados(symbol, interval, period):
    """Devolve candles OHLCV. Fonte única de verdade: o banco SQLite (data_layer).
    O yfinance só é chamado para preencher dados ausentes — a decisão de buscar é
    "está preenchido?", não "houve falha na tentativa". Assinatura preservada para
    não alterar os ~22 pontos de chamada. Veja data_layer.get_bars."""
    return data_layer.get_bars(symbol, interval, period)


def _prewarm_com_progresso(ativos, intervals, rotulo="Baixando dados"):
    """Aquisição ANTES da análise: baixa todos os dados necessários via
    data_layer.prewarm (retry + log de falhas em fetch_failures), com barra de
    progresso. Retorna a lista de (symbol, interval) que falharam. Assim todo o
    download acontece antes de qualquer análise e os ativos não preenchidos ficam
    registrados (e são pulados naturalmente pelas checagens de comprimento)."""
    total = max(1, len(ativos) * len(intervals))
    barra = st.progress(0.0)
    texto = st.empty()
    texto.text(f"{rotulo} (0/{total})…")
    def _cb(done, tot, symbol, ok):
        barra.progress(done / tot if tot else 1.0)
        texto.text(f"{rotulo}: {done}/{tot} — {symbol} {'✓' if ok else '✗'}")
    try:
        return data_layer.prewarm(ativos, intervals, progress=_cb)
    finally:
        barra.empty()
        texto.empty()


def safe_float(x, default=0.0):
    """Converte valor para float com tratamento de erros."""
    try:
        if pd.isna(x) or x is None:
            return default
        return float(x)
    except Exception:
        return default


# ===================== ANÁLISE COMPLETA =====================
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


# ===================== SCANNERS DIFERENCIADOS =====================

# ===================== LEGACY SCANNERS =====================
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


# ===================== EVOLVED SCANNERS =====================

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


# ===================== INTERFACE =====================
st.markdown("---")
st.subheader("⚙️ Painel de Controle Global")

# Radio fora do form para atualização imediata da legenda.
def _limpar_caches_evolved():
    """Invalida APENAS os caches dos scanners Evolved ao trocar de perfil,
    para que sejam recalculados imediatamente com os novos filtros.
    Os scanners Legacy são intocados: seus filtros são hardcoded e
    independentes dos seletores, portanto não devem mudar ao trocar de perfil."""
    for key in EVOLVED_CACHE_KEYS:
        st.session_state[key] = None


profile_names = list(PROFILES.keys()) + ["🎛️ Personalizado"]
perfil_selecionado = st.radio(
    "🎯 Perfil de Análise",
    profile_names,
    index=profile_names.index(DEFAULT_PROFILE),
    horizontal=True,
    help="Selecione um perfil predefinido ou Personalizado para ajustar manualmente",
    on_change=_limpar_caches_evolved,
)

# Mostrar legenda do perfil selecionado fora do form (atualiza imediatamente)
if perfil_selecionado in PROFILES:
    p = PROFILES[perfil_selecionado]
    st.info(f"**{perfil_selecionado}** — {p['desc']}  \n"
            f"📊 Vol ≥ {p['vol_ratio']}x | 💧 Liquidez ≥ {p['vol_medio_min']/1_000_000:.1f}M | "
            f"📈 ADX ≥ {p['adx_min']} | "
            f"⬇️ RSI ≥ {p['rsi_min']} | ⬆️ RSI ≤ {p['rsi_max']}")
    # Set values for use in form
    min_vol_ratio = p["vol_ratio"]
    vol_medio_min = p["vol_medio_min"]
    adx_min = p["adx_min"]
    rsi_min = p["rsi_min"]
    rsi_max = p["rsi_max"]

# Usar st.form para os sliders e botão de submit
# Só o botão de submit (Atualizar Scanners) dispara o rerun pesado
with st.form("painel_controle"):
    if perfil_selecionado == "🎛️ Personalizado":
        # Personalizado: mostrar sliders
        col_vol, col_liq, col_adx, col_rsi_min, col_rsi_max = st.columns(5)
        with col_vol:
            min_vol_ratio = st.slider(
                "📊 Volume Ratio Mínimo",
                min_value=0.5,
                max_value=3.0,
                value=PROFILES[DEFAULT_PROFILE]["vol_ratio"],
                step=0.1,
                help="Ratio mínimo entre volume atual e média de 20 períodos"
            )
        with col_liq:
            vol_medio_min = st.slider(
                "💧 Liquidez Mínima (M)",
                min_value=0.1,
                max_value=10.0,
                value=PROFILES[DEFAULT_PROFILE]["vol_medio_min"] / 1_000_000,
                step=0.1,
                help="Volume médio diário mínimo (em milhões). Guarda de liquidez."
            ) * 1_000_000
        with col_adx:
            adx_min = st.slider(
                "📈 ADX Mínimo",
                min_value=15,
                max_value=35,
                value=PROFILES[DEFAULT_PROFILE]["adx_min"],
                step=1,
                help="Força mínima da tendência (ADX). Valores > 25 indicam tendência forte"
            )
        with col_rsi_min:
            rsi_min = st.slider(
                "⬇️ RSI Mínimo",
                min_value=40,
                max_value=60,
                value=PROFILES[DEFAULT_PROFILE]["rsi_min"],
                step=1,
                help="RSI mínimo para considerar momentum de alta"
            )
        with col_rsi_max:
            rsi_max = st.slider(
                "⬆️ RSI Máximo",
                min_value=60,
                max_value=80,
                value=PROFILES[DEFAULT_PROFILE]["rsi_max"],
                step=1,
                help="RSI máximo antes de sobrecompra"
            )

    # Botão de submit do form — único gatilho de rerun pesado
    rodar_todos = st.form_submit_button("🔄 Atualizar Scanners", type="primary", width='stretch')

# Usar sempre a lista universal completa
ativos_global = ATIVOS_B3_AMPLIADO
lista_global = "Universal"

# ===================== LEGENDA =====================
with st.expander("📖 Legenda dos Indicadores", expanded=True):
    col_leg1, col_leg2, col_leg3 = st.columns(3)
    with col_leg1:
        st.markdown("""
        **Indicadores Técnicos:**
        - **ADX**: Força da tendência (> 25 = forte)
        - **ADX Rising**: ADX crescendo vs 5 períodos atrás
        - **+DI / -DI**: Direção da tendência (+DI > -DI = alta)
        """)
    with col_leg2:
        st.markdown("""
        **Zonas de RSI:**
        - **< 40**: Sobrevendido
        - **52-70**: Zona ideal de momentum
        - **> 75**: Sobrecomprado
        """)
    with col_leg3:
        st.markdown("""
        **Tríade (ADX + RSI + Volume):**
        - ✅ **Completa**: Todos na zona ideal
        - ⚠️ **Parcial**: Pelo menos um fora

        **Sinais de Saída:**
        - ⚠️ ADX↓: ADX caindo (perda de força)
        - ⚠️ RSI↑: RSI acima do máximo
        - ✅: Sem alertas
        """)

# ===================== ATIVOS EM USO =====================
with st.expander(f"📋 Ativos em uso — {len(ativos_global)} ativos", expanded=True):
    col_u1, col_u2 = st.columns(2)

    with col_u1:
        st.markdown(f"**🔍 Universo completo ({len(ATIVOS_B3_AMPLIADO)} ativos):**")
        for cat, qtd in CONTAGEM_CATEGORIAS.items():
            st.markdown(f"- {cat}: **{qtd}**")

    with col_u2:
        st.warning("⚠️ Analisando **todos** os ativos cadastrados. O scan pode demorar vários minutos.")

    # Lista completa de todos os símbolos divididos por categoria
    with st.expander("📝 Ver todos os símbolos"):
        categorized_symbols = {
            'Ações': sorted(list(set([s.replace('.SA', '') for s in _ACOES_UNIVERSAL]))),
            'BDRs': sorted(list(set([s.replace('.SA', '') for s in _BDRS_UNIVERSAL]))),
            'ETFs': sorted(list(set([s.replace('.SA', '') for s in _ETFS_UNIVERSAL]))),
            'FIIs': sorted(list(set([s.replace('.SA', '') for s in _FIIS_UNIVERSAL]))),
        }
        for cat, symbols in categorized_symbols.items():
            with st.expander(f"📦 {cat} ({len(symbols)})", expanded=False):
                st.markdown(", ".join([f"`{s}`" for s in symbols]))

# ===================== CONTROLE DE ESTADO =====================
for key in SCANNER_CACHE_KEYS:
    if key not in st.session_state:
        st.session_state[key] = None

# Botão "Atualizar Scanners": invalida APENAS os caches Evolved (+ cache de
# dados para forçar snapshot fresco). Os scanners Legacy NÃO são afetados —
# têm seu próprio botão de refresh no painel Legacy.
if rodar_todos:
    for key in EVOLVED_CACHE_KEYS:
        st.session_state[key] = None
    # Limpar cache do yfinance para baixar dados frescos
    data_layer.invalidate()

st.markdown("---")


# ===================== DISPLAY HELPERS =====================
def mostrar_resumo_triade(df_resultado):
    """Mostra resumo da Tríade no topo do scanner."""
    if df_resultado is None or df_resultado.empty:
        return
    if 'Tríade' not in df_resultado.columns:
        return
    total = len(df_resultado)
    completas = len(df_resultado[df_resultado['Tríade'] == '✅ Completa'])
    parciais = total - completas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Ativos", total)
    with col2:
        st.metric("Tríade ✅ Completa", completas)
    with col3:
        st.metric("Tríade ⚠️ Parcial", parciais)


def exibir_dataframe_colorido(df_resultado):
    """Exibe DataFrame com configuração de colunas e cores."""
    if df_resultado is None or df_resultado.empty:
        st.info("Nenhum ativo encontrado com os filtros atuais.")
        return

    # Ordenar por Score descendente
    df_resultado = df_resultado.sort_values('Score', ascending=False).reset_index(drop=True)

    # Column config para melhor visualização
    column_config = {
        'Preço': st.column_config.NumberColumn('Preço (R$)', format="R$ %.2f"),
        'Vol Ratio': st.column_config.NumberColumn('Vol Ratio', format="%.2f"),
        'RSI': st.column_config.NumberColumn('RSI', format="%.1f"),
        'ADX': st.column_config.NumberColumn('ADX', format="%.1f"),
        '+DI': st.column_config.NumberColumn('+DI', format="%.1f"),
        '-DI': st.column_config.NumberColumn('-DI', format="%.1f"),
        'Score': st.column_config.ProgressColumn(
            'Score',
            min_value=0,
            max_value=110,
            format="%d",
        ),
    }

    # Adicionar configs para colunas RR se existirem
    if 'Stop' in df_resultado.columns:
        column_config['Stop'] = st.column_config.NumberColumn('Stop (R$)', format="R$ %.2f")
        column_config['Alvo 1:2'] = st.column_config.NumberColumn('Alvo 1:2 (R$)', format="R$ %.2f")
        column_config['Alvo 1:3'] = st.column_config.NumberColumn('Alvo 1:3 (R$)', format="R$ %.2f")
        column_config['RR'] = st.column_config.NumberColumn('RR', format="%.1f")

    st.dataframe(
        df_resultado,
        width='stretch',
        hide_index=True,
        column_config=column_config,
    )

    st.success(f"{len(df_resultado)} ativos encontrados")


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


# ===================== HELPER: EXPORTAR MARKDOWN (.md) =====================
def df_para_markdown(df):
    """Converte DataFrame em tabela markdown (GitHub-flavored), sem dependências externas."""
    if df is None or df.empty:
        return "_Nenhum ativo encontrado com os filtros atuais._"

    cols = df.columns.tolist()
    cabecalho = "| " + " | ".join(str(c) for c in cols) + " |"
    separador = "| " + " | ".join("---" for _ in cols) + " |"

    linhas = []
    for _, row in df.iterrows():
        celulas = []
        for col in cols:
            val = row[col]
            if pd.isna(val):
                celulas.append("N/A")
            elif isinstance(val, float):
                celulas.append(f"{val:.2f}")
            else:
                # Escapa pipes e qubra de linha para não quebrar a tabela
                celulas.append(str(val).replace("|", "\\|").replace("\n", " "))
        linhas.append("| " + " | ".join(celulas) + " |")

    return "\n".join([cabecalho, separador] + linhas)


def gerar_markdown_relatorio(df, label="resultado", vol_ratio=1.6, adx_min=23, rsi_min=52, rsi_max=70, usa_sliders=True, perfil=""):
    """Gera um relatório em markdown (.md) do resultado do scanner, pronto para download."""
    if df is None or df.empty:
        return f"# {label}\n\n_Nenhum ativo encontrado com os filtros atuais._\n"

    df_md = df.copy()
    if "Score" in df_md.columns:
        df_md = df_md.sort_values("Score", ascending=False).reset_index(drop=True)

    perfil_linha = f"\n**Perfil:** {perfil}" if perfil else ""
    datahora = datetime.now().strftime("%d/%m/%Y %H:%M")

    if usa_sliders:
        filtros = (
            f"- Volume Ratio Mínimo: {vol_ratio}\n"
            f"- ADX Mínimo: {adx_min}\n"
            f"- RSI Mínimo: {rsi_min}\n"
            f"- RSI Máximo: {rsi_max}\n"
        )
    else:
        filtros = "- Filtros internos próprios (configurações fixas incorporadas no scanner)\n"

    tabela = df_para_markdown(df_md)

    return (
        f"# {label}\n\n"
        f"**Gerado em:** {datahora}{perfil_linha}\n"
        f"**Ativos encontrados:** {len(df_md)}\n\n"
        f"## Filtros utilizados\n\n"
        f"{filtros}\n"
        f"## Resultados\n\n"
        f"{tabela}\n"
    )


def adicionar_botao_download_md(df, label="resultado", vol_ratio=1.6, adx_min=23, rsi_min=52, rsi_max=70, usa_sliders=True, perfil=""):
    """Adiciona um botão nativo para baixar o resultado do scanner como arquivo .md."""
    if df is None or df.empty:
        return

    md = gerar_markdown_relatorio(
        df, label=label, vol_ratio=vol_ratio, adx_min=adx_min,
        rsi_min=rsi_min, rsi_max=rsi_max, usa_sliders=usa_sliders, perfil=perfil,
    )

    # Nome de arquivo seguro (apenas alfanuméricos, - e _)
    nome_arquivo = "".join(c if (c.isalnum() or c in "-_") else "_" for c in label).strip("_")[:60]
    if not nome_arquivo:
        nome_arquivo = "scanner"

    st.download_button(
        label="📄 Baixar .md",
        data=md.encode("utf-8"),
        file_name=f"{nome_arquivo}.md",
        mime="text/markdown",
        help="Baixa um relatório em markdown com os resultados deste scanner.",
    )


def adicionar_botao_copiar(df, label="resultado", vol_ratio=1.6, adx_min=23, rsi_min=52, rsi_max=70, usa_sliders=True, perfil=""):
    """Adiciona o botão para copiar a análise com o prompt do trader."""
    if df is None or df.empty:
        return

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

    # Configuração dos filtros usados na análise
    perfil_info = f"\n**Perfil:** {perfil}" if perfil else ""
    if usa_sliders:
        config_sliders = f"""

---
**Scanner:** {label}{perfil_info}

**Configuração dos Filtros Utilizados:**
• Volume Ratio Mínimo: {vol_ratio}
• ADX Mínimo: {adx_min}
• RSI Mínimo: {rsi_min}
• RSI Máximo: {rsi_max}
"""
    else:
        config_sliders = f"""

---
**Scanner:** {label}

**Filtros:** Este scanner utiliza filtros internos próprios (configurações fixas incorporadas no scanner)
"""

    # Combinar prompt + dados + configuração
    texto_completo = prompt_trader + dados_textuais + config_sliders

    # Escapar para HTML seguro (textarea)
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


# ===================== EXECUÇÃO DOS SCANNERS =====================

def run_scanner(nome, funcao, key, descricao="", vol_ratio=1.6, adx_min=23, rsi_min=52, rsi_max=70, perfil=""):
    """Executa e exibe um scanner dentro de um expander."""
    with st.expander(nome, expanded=True):
        if descricao:
            st.caption(descricao)

        if rodar_todos or st.session_state[key] is None:
            with st.spinner(f"Analisando {nome}..."):
                st.session_state[key] = funcao()

        mostrar_resumo_triade(st.session_state[key])
        exibir_dataframe_colorido(st.session_state[key])
        if st.session_state[key] is not None and not st.session_state[key].empty:
            adicionar_botao_copiar(st.session_state[key], label=nome, vol_ratio=vol_ratio, adx_min=adx_min, rsi_min=rsi_min, rsi_max=rsi_max, perfil=perfil)


# Scanner 0: 🔥 Swing Trade Fusion (HERO SCANNER)
with st.expander("🔥 Swing Trade Fusion — Best of Legacy + Evolved", expanded=True):
    st.caption(f"Multi-TF completo (D+1H+30M) | Score ponderado (D×0.3 + 1H×0.4 + 30M×0.3) | Tríade + DI + ADX Rising + Stop/Alvos | {len(ativos_global)} ativos ({lista_global})")

    if rodar_todos or st.session_state['df_fusion'] is None:
        with st.spinner("Analisando Swing Trade Fusion..."):
            st.session_state['df_fusion'] = scanner_swing_trade_fusion(ativos_global, adx_min, rsi_min, rsi_max, min_vol_ratio, vol_medio_min)

    df_fusion = st.session_state['df_fusion']
    if df_fusion is not None and not df_fusion.empty:
        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Ativos", len(df_fusion))
        with col2:
            excelentes = len(df_fusion[df_fusion['Confluência'] == 'Excelente ✅✅'])
            st.metric("Confluência Excelente", excelentes)
        with col3:
            boas = len(df_fusion[df_fusion['Confluência'].isin(['Boa ✅', 'Excelente ✅✅'])])
            st.metric("Confluência Boa+", boas)
        with col4:
            triade_full = len(df_fusion[(df_fusion['Tríade D'] == '✅') & (df_fusion['Tríade 1H'] == '✅')])
            st.metric("Tríade D+1H ✅", triade_full)

        # Sort by Score Total descending
        df_sorted = df_fusion.sort_values('Score Total', ascending=False).reset_index(drop=True)

        column_config_fusion = {
            'Preço': st.column_config.NumberColumn('Preço (R$)', format="R$ %.2f"),
            'Stop': st.column_config.NumberColumn('Stop (R$)', format="R$ %.2f"),
            'Alvo 1:2': st.column_config.NumberColumn('Alvo 1:2 (R$)', format="R$ %.2f"),
            'Alvo 1:3': st.column_config.NumberColumn('Alvo 1:3 (R$)', format="R$ %.2f"),
            'Vol Ratio': st.column_config.NumberColumn('Vol Ratio', format="%.2f"),
            'RSI D': st.column_config.NumberColumn('RSI D', format="%.1f"),
            'RSI 1H': st.column_config.NumberColumn('RSI 1H', format="%.1f"),
            'RSI 30M': st.column_config.NumberColumn('RSI 30M', format="%.1f"),
            'ADX D': st.column_config.NumberColumn('ADX D', format="%.1f"),
            'ADX 1H': st.column_config.NumberColumn('ADX 1H', format="%.1f"),
            'ADX 30M': st.column_config.NumberColumn('ADX 30M', format="%.1f"),
            '+DI': st.column_config.NumberColumn('+DI', format="%.1f"),
            '-DI': st.column_config.NumberColumn('-DI', format="%.1f"),
            'Score D': st.column_config.NumberColumn('Score D', format="%d"),
            'Score 1H': st.column_config.NumberColumn('Score 1H', format="%d"),
            'Score 30M': st.column_config.NumberColumn('Score 30M', format="%d"),
            'Score Total': st.column_config.ProgressColumn(
                'Score Total',
                min_value=0,
                max_value=100,
                format="%d",
            ),
        }

        st.dataframe(
            df_sorted,
            width='stretch',
            hide_index=True,
            column_config=column_config_fusion,
        )

        st.success(f"{len(df_sorted)} ativos encontrados")
        adicionar_botao_copiar(df_sorted, label="🔥 Swing Trade Fusion — Best of Legacy + Evolved", vol_ratio=min_vol_ratio, adx_min=adx_min, rsi_min=rsi_min, rsi_max=rsi_max, perfil=perfil_selecionado)
    else:
        st.info("Nenhum ativo encontrado com os filtros atuais.")

# Scanner 1: Swing Híbrido
run_scanner(
    "🔀 Scanner Swing Híbrido (Daily + 1H)",
    lambda: scanner_swing_hibrido(ativos_global, adx_min, rsi_min, rsi_max, min_vol_ratio, vol_medio_min),
    'df_hibrido',
    descricao="Análise Daily com confirmação 1H. Tríade básica.",
    vol_ratio=min_vol_ratio, adx_min=adx_min, rsi_min=rsi_min, rsi_max=rsi_max, perfil=perfil_selecionado
)

# Scanner 2: Swing RR
run_scanner(
    "🎯 Scanner Swing RR (Daily + ATR Targets)",
    lambda: scanner_swing_rr(ativos_global, adx_min, rsi_min, rsi_max, min_vol_ratio, vol_medio_min),
    'df_rr',
    descricao="Base Híbrido + Stop (ATR×1.8), Alvos 1:2 e 1:3.",
    vol_ratio=min_vol_ratio, adx_min=adx_min, rsi_min=rsi_min, rsi_max=rsi_max, perfil=perfil_selecionado
)

# Scanner 3: Swing Profissional
run_scanner(
    "🏆 Scanner Swing Profissional (Daily + 1H + 30M)",
    lambda: scanner_swing_profissional(ativos_global, adx_min, rsi_min, rsi_max, min_vol_ratio, vol_medio_min),
    'df_pro',
    descricao="Multi-timeframe completo. ADX Rising + DI+ > DI- + Tríade obrigatórios.",
    vol_ratio=min_vol_ratio, adx_min=adx_min, rsi_min=rsi_min, rsi_max=rsi_max, perfil=perfil_selecionado
)

# Scanner 4: Swing Expandido
run_scanner(
    "🌐 Scanner Swing Expandido (Mid + Small Caps)",
    lambda: scanner_swing_expandido(adx_min, rsi_min, rsi_max, min_vol_ratio, vol_medio_min),
    'df_exp',
    descricao="Lista completa (Blue Chips + Mid/Small). Volume médio mínimo controlado pelo perfil.",
    vol_ratio=min_vol_ratio, adx_min=adx_min, rsi_min=rsi_min, rsi_max=rsi_max, perfil=perfil_selecionado
)

# Feedback visual após atualização
if rodar_todos:
    st.toast("✅ Scanners atualizados com sucesso!", icon="🎉")

st.markdown("---")
st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

# ===================== LEGACY PANEL =====================
st.markdown("---")
st.markdown("## 📚 LEGACY - VERSÕES ANTIGAS (COMPARAÇÃO)")
st.caption(f"Compare os resultados dos scanners evoluídos com as versões antigas/legadas | {len(ativos_global)} ativos ({lista_global})")

# Botão de refresh INDEPENDENTE dos scanners Legacy. Invalida APENAS os caches
# Legacy (+ baixar_dados para snapshot fresco) — não afeta os scanners Evolved,
# que só rodam ao trocar de perfil/seletores ou no botão "Atualizar Scanners".
rodar_legacy = st.button(
    "📚 Atualizar Legacy",
    type="secondary",
    help="Recalcula apenas os scanners Legacy com dados frescos. Independente dos seletores de perfil.",
)
if rodar_legacy:
    for key in LEGACY_CACHE_KEYS:
        st.session_state[key] = None
    data_layer.invalidate()

# Legacy Scanner 1: Profissional
with st.expander("🔮 Legacy - Profissional (Final Corrigida)", expanded=True):
    st.caption(f"Multi-timeframe: Daily + 1H + 30M | Filtros: Vol>1.5x, EMA20/50, ADX>20, RSI 45-75 | {len(ativos_global)} ativos ({lista_global})")

    if rodar_legacy or st.session_state['df_legacy_prof'] is None:
        with st.spinner("Analisando Legacy Profissional..."):
            st.session_state['df_legacy_prof'] = legacy_profissional(ativos_global)

    if st.session_state['df_legacy_prof'] is not None and not st.session_state['df_legacy_prof'].empty:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Ativos", len(st.session_state['df_legacy_prof']))
        with col2:
            forte = len(st.session_state['df_legacy_prof'][st.session_state['df_legacy_prof']['Alinhamento'] == '✅ FORTE'])
            st.metric("Alinhamento Forte", forte)

        # Ordenar por Score Total
        df_sorted = st.session_state['df_legacy_prof'].sort_values('Score Total', ascending=False).reset_index(drop=True)

        column_config_legacy = {
            'Preço': st.column_config.NumberColumn('Preço (R$)', format="R$ %.2f"),
            'Vol Ratio': st.column_config.NumberColumn('Vol Ratio', format="%.2f"),
            'RSI Daily': st.column_config.NumberColumn('RSI Daily', format="%.1f"),
            'ADX Daily': st.column_config.NumberColumn('ADX Daily', format="%.1f"),
            'RSI 1H': st.column_config.NumberColumn('RSI 1H', format="%.1f"),
            'ADX 1H': st.column_config.NumberColumn('ADX 1H', format="%.1f"),
            'RSI 30M': st.column_config.NumberColumn('RSI 30M', format="%.1f"),
            'ADX 30M': st.column_config.NumberColumn('ADX 30M', format="%.1f"),
            'Score Daily': st.column_config.NumberColumn('Score Daily', format="%d"),
            'Score 1H': st.column_config.NumberColumn('Score 1H', format="%d"),
            'Score 30M': st.column_config.NumberColumn('Score 30M', format="%d"),
            'Score Total': st.column_config.NumberColumn('Score Total', format="%d"),
        }

        st.dataframe(
            df_sorted,
            width='stretch',
            hide_index=True,
            column_config=column_config_legacy,
        )

        st.success(f"{len(df_sorted)} ativos encontrados")
        adicionar_botao_copiar(df_sorted, label="🔮 Legacy - Profissional (Final Corrigida)", vol_ratio=min_vol_ratio, adx_min=adx_min, rsi_min=rsi_min, rsi_max=rsi_max, usa_sliders=False)
    else:
        st.info("Nenhum ativo encontrado com os filtros da versão Profissional.")


# Legacy Scanner 2: Intraday/Swing Curto Prazo
with st.expander("⏰ Legacy - Intraday/Swing Curto Prazo", expanded=True):
    st.caption(f"Filtros rigorosos: Vol>1.7x, Liquidez>8M, ADX≥22, RSI 47-73 | Score ponderado: Daily×1.6 + 1H + 30M | {len(ativos_global)} ativos ({lista_global})")

    if rodar_legacy or st.session_state['df_legacy_intra'] is None:
        with st.spinner("Analisando Legacy Intraday/Swing..."):
            st.session_state['df_legacy_intra'] = legacy_intraday_swing(ativos_global)

    if st.session_state['df_legacy_intra'] is not None and not st.session_state['df_legacy_intra'].empty:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Ativos", len(st.session_state['df_legacy_intra']))
        with col2:
            forte = len(st.session_state['df_legacy_intra'][st.session_state['df_legacy_intra']['Alinhamento'] == '✅ FORTE'])
            st.metric("Alinhamento Forte", forte)

        # Ordenar por Score Total
        df_sorted = st.session_state['df_legacy_intra'].sort_values('Score Total', ascending=False).reset_index(drop=True)

        column_config_legacy2 = {
            'Preço': st.column_config.NumberColumn('Preço (R$)', format="R$ %.2f"),
            'Vol Ratio D': st.column_config.NumberColumn('Vol Ratio D', format="%.2f"),
            'Vol Ratio H': st.column_config.NumberColumn('Vol Ratio H', format="%.2f"),
            'RSI Daily': st.column_config.NumberColumn('RSI Daily', format="%.1f"),
            'ADX Daily': st.column_config.NumberColumn('ADX Daily', format="%.1f"),
            'RSI 1H': st.column_config.NumberColumn('RSI 1H', format="%.1f"),
            'ADX 1H': st.column_config.NumberColumn('ADX 1H', format="%.1f"),
            'Score 30M': st.column_config.NumberColumn('Score 30M', format="%d"),
            'Score Total': st.column_config.NumberColumn('Score Total', format="%d"),
        }

        st.dataframe(
            df_sorted,
            width='stretch',
            hide_index=True,
            column_config=column_config_legacy2,
        )

        st.success(f"{len(df_sorted)} ativos encontrados")
        adicionar_botao_copiar(df_sorted, label="⏰ Legacy - Intraday/Swing Curto Prazo", vol_ratio=min_vol_ratio, adx_min=adx_min, rsi_min=rsi_min, rsi_max=rsi_max, usa_sliders=False)
    else:
        st.info("Nenhum ativo encontrado com os filtros da versão Intraday/Swing.")


# Legacy Scanner 3: Expandida
with st.expander("🌐 Legacy - Expandida (Mid + Small Caps)", expanded=True):
    st.caption(f"Vol médio relaxado (≥2.5M) | Confluência multi-TF detalhada | {len(ativos_global)} ativos ({lista_global})")

    if rodar_legacy or st.session_state['df_legacy_exp'] is None:
        with st.spinner("Analisando Legacy Expandida..."):
            st.session_state['df_legacy_exp'] = legacy_expandida(ativos_global)

    if st.session_state['df_legacy_exp'] is not None and not st.session_state['df_legacy_exp'].empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Ativos", len(st.session_state['df_legacy_exp']))
        with col2:
            excelentes = len(st.session_state['df_legacy_exp'][st.session_state['df_legacy_exp']['Confluência Geral'] == 'Excelente ✅✅'])
            st.metric("Confluência Excelente", excelentes)
        with col3:
            boas = len(st.session_state['df_legacy_exp'][st.session_state['df_legacy_exp']['Confluência Geral'].isin(['Boa ✅', 'Excelente ✅✅'])])
            st.metric("Confluência Boa+", boas)

        # Ordenar por Score Diário
        df_sorted = st.session_state['df_legacy_exp'].sort_values('Score Diário', ascending=False).reset_index(drop=True)

        column_config_legacy3 = {
            'Preço': st.column_config.NumberColumn('Preço (R$)', format="R$ %.2f"),
            'Vol Ratio': st.column_config.NumberColumn('Vol Ratio', format="%.2f"),
            'Vol Médio (M)': st.column_config.NumberColumn('Vol Médio (M)', format="%.1f"),
            'RSI Daily': st.column_config.NumberColumn('RSI Daily', format="%.1f"),
            'ADX Daily': st.column_config.NumberColumn('ADX Daily', format="%.1f"),
            'RSI 1H': st.column_config.NumberColumn('RSI 1H', format="%.1f"),
            'ADX 1H': st.column_config.NumberColumn('ADX 1H', format="%.1f"),
            'RSI 30M': st.column_config.NumberColumn('RSI 30M', format="%.1f"),
            'ADX 30M': st.column_config.NumberColumn('ADX 30M', format="%.1f"),
            'Score Diário': st.column_config.NumberColumn('Score Diário', format="%d"),
        }

        st.dataframe(
            df_sorted,
            width='stretch',
            hide_index=True,
            column_config=column_config_legacy3,
        )

        st.success(f"{len(df_sorted)} ativos encontrados")
        adicionar_botao_copiar(df_sorted, label="🌐 Legacy - Expandida (Mid + Small Caps)", vol_ratio=min_vol_ratio, adx_min=adx_min, rsi_min=rsi_min, rsi_max=rsi_max, usa_sliders=False)
    else:
        st.info("Nenhum ativo encontrado com os filtros da versão Expandida.")


# Painel de falhas de aquisição — base para blacklist e diagnóstico por ativo.
with st.expander("⚠️ Ativos com falha de dados (potencial blacklist)", expanded=False):
    _falhas = data_layer.list_failures()
    if _falhas is None or _falhas.empty:
        st.caption("Nenhuma falha registrada — todos os ativos foram baixados com sucesso.")
    else:
        st.caption(
            f"{len(_falhas)} (symbol, interval) com falha persistente de download. "
            "Ordene por fail_count para identificar candidatos a blacklist."
        )
        st.dataframe(_falhas, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")