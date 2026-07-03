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

# Page config
st.set_page_config(page_title="Scanner Ações BR", layout="wide", page_icon="📈")
st.title("📈 SCANNER CONSOLIDADO DE AÇÕES - BRASIL")

# ===================== THRESHOLDS PADRÃO =====================
DEFAULT_ADX_MIN = 23
DEFAULT_RSI_MIN = 52
DEFAULT_RSI_MAX = 70
DEFAULT_VOL_RATIO = 1.6
ADX_RISING_PERIODS = 5

# ===================== LISTA DE ATIVOS =====================
ATIVOS_BLUE_CHIPS = [
    'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'PRIO3.SA', 'BBAS3.SA',
    'B3SA3.SA', 'BBDC4.SA', 'BPAC11.SA', 'BOVA11.SA'
]

ATIVOS_MID_SMALL_CAPS = [
    'RENT3.SA', 'LREN3.SA', 'MGLU3.SA', 'HAPV3.SA', 'EQTL3.SA',
    'SBSP3.SA', 'TOTS3.SA', 'RAIL3.SA', 'CSNA3.SA', 'GGBR4.SA',
    'PLPL3.SA', 'CURY3.SA', 'BMOB3.SA', 'TAEE11.SA', 'SEQL3.SA'
]

ATIVOS_COMPLETO = ATIVOS_BLUE_CHIPS + ATIVOS_MID_SMALL_CAPS


# ===================== FUNÇÕES UTILITÁRIAS =====================
@st.cache_data(ttl=300)
def baixar_dados(symbol, interval, period):
    """Baixa dados do yfinance com tratamento de MultiIndex."""
    try:
        df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(1, axis=1)
        return df
    except Exception:
        return pd.DataFrame()


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

    # Score
    score = 0
    if preco > ema20:
        score += 20
    if preco > ema50:
        score += 15
    if triade_adx:
        score += 20
    if triade_rsi:
        score += 20
    if triade_vol:
        score += 15
    if adx_rising:
        score += 10
    if plus_di > minus_di:
        score += 10

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

def scanner_swing_hibrido(ativos, adx_min, rsi_min, rsi_max, vol_ratio_min):
    """
    Scanner Swing Híbrido (Daily + 1H)
    - Análise Daily com thresholds dos sliders
    - Confirmação de tendência 1H
    - Tríade básica
    """
    resultados = []
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


def scanner_swing_rr(ativos, adx_min, rsi_min, rsi_max, vol_ratio_min):
    """
    Scanner Swing RR (Daily + ATR targets)
    - Mesma base do Híbrido
    - Stop Loss = Preço - ATR * 1.8
    - Alvo 1:2 e 1:3 com ATR
    - Colunas de risco/retorno
    """
    resultados = []
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


def scanner_swing_profissional(ativos, adx_min, rsi_min, rsi_max, vol_ratio_min):
    """
    Scanner Swing Profissional (Daily + 1H + 30M)
    - Análise multi-timeframe completa
    - ADX Rising obrigatório
    - +DI > -DI obrigatório
    - Tríade completa exigida
    - Filtros mais rigorosos
    """
    resultados = []
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


def scanner_swing_expandido(adx_min, rsi_min, rsi_max, vol_ratio_min):
    """
    Scanner Swing Expandido (Mid + Small Caps)
    - Usa ATIVOS_COMPLETO
    - Volume threshold levemente relaxado (vol_medio mínimo menor)
    - Tríade completa
    """
    resultados = []
    # Sempre usa a lista completa
    ativos = ATIVOS_COMPLETO

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

            # Vol medio relaxado para small caps (2.5M vs 8M do padrão)
            if analise['vol_medio'] < 2_500_000:
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


# ===================== INTERFACE =====================
st.markdown("---")
st.subheader("⚙️ Painel de Controle Global")

# Row 1: Radio button + Update button
col_radio, col_btn = st.columns([4, 1.2])

with col_radio:
    lista_global = st.radio("Lista de ativos", ["Todos", "Blue Chips"], horizontal=True)

with col_btn:
    rodar_todos = st.button("🔄 Atualizar Scanners", type="primary", use_container_width=True)

# Row 2: Volume + ADX + RSI Min + RSI Max sliders
col_vol, col_adx, col_rsi_min, col_rsi_max = st.columns(4)

with col_vol:
    min_vol_ratio = st.slider(
        "📊 Volume Ratio Mínimo",
        min_value=1.0,
        max_value=3.0,
        value=DEFAULT_VOL_RATIO,
        step=0.1,
        help="Ratio mínimo entre volume atual e média de 20 períodos"
    )

with col_adx:
    adx_min = st.slider(
        "📈 ADX Mínimo",
        min_value=15,
        max_value=35,
        value=DEFAULT_ADX_MIN,
        step=1,
        help="Força mínima da tendência (ADX). Valores > 25 indicam tendência forte"
    )

with col_rsi_min:
    rsi_min = st.slider(
        "⬇️ RSI Mínimo",
        min_value=40,
        max_value=60,
        value=DEFAULT_RSI_MIN,
        step=1,
        help="RSI mínimo para considerar momentum de alta"
    )

with col_rsi_max:
    rsi_max = st.slider(
        "⬆️ RSI Máximo",
        min_value=60,
        max_value=80,
        value=DEFAULT_RSI_MAX,
        step=1,
        help="RSI máximo antes de sobrecompra"
    )

ativos_global = ATIVOS_BLUE_CHIPS if lista_global == "Blue Chips" else ATIVOS_COMPLETO

# ===================== LEGENDA =====================
with st.expander("📖 Legenda dos Indicadores", expanded=False):
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

# ===================== CONTROLE DE ESTADO =====================
scanners_keys = ['df_hibrido', 'df_rr', 'df_pro', 'df_exp']

for key in scanners_keys:
    if key not in st.session_state:
        st.session_state[key] = None

# Reset quando mudar lista ou qualquer slider
if 'last_lista' not in st.session_state:
    st.session_state.last_lista = lista_global
if 'last_ratio' not in st.session_state:
    st.session_state.last_ratio = min_vol_ratio
if 'last_adx' not in st.session_state:
    st.session_state.last_adx = adx_min
if 'last_rsi_min' not in st.session_state:
    st.session_state.last_rsi_min = rsi_min
if 'last_rsi_max' not in st.session_state:
    st.session_state.last_rsi_max = rsi_max

params_changed = (
    st.session_state.last_lista != lista_global
    or st.session_state.last_ratio != min_vol_ratio
    or st.session_state.last_adx != adx_min
    or st.session_state.last_rsi_min != rsi_min
    or st.session_state.last_rsi_max != rsi_max
)

if params_changed:
    for key in scanners_keys:
        st.session_state[key] = None
    st.session_state.last_lista = lista_global
    st.session_state.last_ratio = min_vol_ratio
    st.session_state.last_adx = adx_min
    st.session_state.last_rsi_min = rsi_min
    st.session_state.last_rsi_max = rsi_max

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
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )

    st.success(f"{len(df_resultado)} ativos encontrados")


# ===================== EXECUÇÃO DOS SCANNERS =====================

def run_scanner(nome, funcao, key, descricao=""):
    """Executa e exibe um scanner dentro de um expander."""
    with st.expander(nome, expanded=True):
        if descricao:
            st.caption(descricao)

        if rodar_todos or st.session_state[key] is None:
            with st.spinner(f"Analisando {nome}..."):
                st.session_state[key] = funcao()

        mostrar_resumo_triade(st.session_state[key])
        exibir_dataframe_colorido(st.session_state[key])


# Scanner 1: Swing Híbrido
run_scanner(
    "🔀 Scanner Swing Híbrido (Daily + 1H)",
    lambda: scanner_swing_hibrido(ativos_global, adx_min, rsi_min, rsi_max, min_vol_ratio),
    'df_hibrido',
    descricao="Análise Daily com confirmação 1H. Tríade básica."
)

# Scanner 2: Swing RR
run_scanner(
    "🎯 Scanner Swing RR (Daily + ATR Targets)",
    lambda: scanner_swing_rr(ativos_global, adx_min, rsi_min, rsi_max, min_vol_ratio),
    'df_rr',
    descricao="Base Híbrido + Stop (ATR×1.8), Alvos 1:2 e 1:3."
)

# Scanner 3: Swing Profissional
run_scanner(
    "🏆 Scanner Swing Profissional (Daily + 1H + 30M)",
    lambda: scanner_swing_profissional(ativos_global, adx_min, rsi_min, rsi_max, min_vol_ratio),
    'df_pro',
    descricao="Multi-timeframe completo. ADX Rising + DI+ > DI- + Tríade obrigatórios."
)

# Scanner 4: Swing Expandido
run_scanner(
    "🌐 Scanner Swing Expandido (Mid + Small Caps)",
    lambda: scanner_swing_expandido(adx_min, rsi_min, rsi_max, min_vol_ratio),
    'df_exp',
    descricao="Lista completa (Blue Chips + Mid/Small). Volume médio mínimo relaxado (2.5M)."
)

st.markdown("---")
st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")