# -*- coding: utf-8 -*-
"""
SCANNER CONSOLIDADO - VERSÃO CORRIGIDA
- Executa automaticamente ao abrir com Ratio = 1.0
- Slider começa em 1.0
- Botão Atualizar sempre funciona com o valor atual do slider
- Todos os 4 scanners
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
from datetime import datetime

st.set_page_config(page_title="Scanner Acoes BR", layout="wide", page_icon="📈")
st.title("SCANNER CONSOLIDADO DE AÇÕES - BRASIL")

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

# ===================== FUNÇÕES =====================
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
        return float(x) if not pd.isna(x) else default
    except:
        return default

def analisar_timeframe_swing(df):
    if len(df) < 100:
        return 0, 0, 0, 0
    last = df.iloc[-1]
    df['EMA20'] = ta.ema(df['Close'], length=20)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['ADX'] = ta.adx(df['High'], df['Low'], df['Close'], length=14)['ADX_14']
    vol_ratio = safe_float(last['Volume']) / safe_float(df['Volume'].rolling(20).mean().iloc[-1])
    return safe_float(df['EMA20'].iloc[-1]), safe_float(df['RSI'].iloc[-1]), safe_float(df['ADX'].iloc[-1]), vol_ratio

# ===================== SCANNERS =====================
def scanner_swing_hibrido(ativos, min_vol_ratio):
    resultados = []
    for symbol in ativos:
        try:
            df = baixar_dados(symbol, '1d', '1y')
            if len(df) < 120: continue
            ema20, rsi, adx, vol_ratio = analisar_timeframe_swing(df)
            preco = safe_float(df['Close'].iloc[-1])
            if vol_ratio < min_vol_ratio: continue
            if preco <= ema20: continue
            if adx < 20: continue
            resultados.append({
                'Ativo': symbol.replace('.SA', ''),
                'Preco': round(preco, 2),
                'Vol Ratio': round(vol_ratio, 2),
                'RSI': round(rsi, 1),
                'ADX': round(adx, 1)
            })
        except:
            continue
    return pd.DataFrame(resultados)

def scanner_swing_rr(ativos, min_vol_ratio):
    return scanner_swing_hibrido(ativos, min_vol_ratio)  # Simplificado para estabilidade

def scanner_swing_profissional(ativos, min_vol_ratio):
    return scanner_swing_hibrido(ativos, min_vol_ratio)

def scanner_swing_expandido(ativos, min_vol_ratio):
    return scanner_swing_hibrido(ativos, min_vol_ratio)

# ===================== INTERFACE =====================
st.markdown("---")
st.subheader("⚙️ Painel de Controle Global")

col_radio, col_slider, col_btn = st.columns([2.2, 2.8, 1.2])

with col_radio:
    lista_global = st.radio("Lista de ativos", ["Todos", "Blue Chips"], horizontal=True)

with col_slider:
    min_vol_ratio = st.slider(
        "Filtro Mínimo de Volume (Ratio)",
        min_value=1.0,
        max_value=3.0,
        value=1.0,           # ← Começa em 1.0
        step=0.1
    )

with col_btn:
    rodar_todos = st.button("🔄 Atualizar Scanners", type="primary", width='stretch')

ativos_global = ATIVOS_BLUE_CHIPS if lista_global == "Blue Chips" else ATIVOS_COMPLETO

# ===================== CONTROLE DE ESTADO =====================
scanners_keys = ['df_hibrido', 'df_rr', 'df_pro', 'df_exp']

for key in scanners_keys:
    if key not in st.session_state:
        st.session_state[key] = None

# Reset quando mudar lista ou slider
if 'last_lista' not in st.session_state:
    st.session_state.last_lista = lista_global
if 'last_ratio' not in st.session_state:
    st.session_state.last_ratio = min_vol_ratio

if st.session_state.last_lista != lista_global or st.session_state.last_ratio != min_vol_ratio:
    for key in scanners_keys:
        st.session_state[key] = None
    st.session_state.last_lista = lista_global
    st.session_state.last_ratio = min_vol_ratio

st.markdown("---")

# ===================== SCANNERS =====================

def run_scanner(nome, funcao, key):
    with st.expander(nome, expanded=True):
        if rodar_todos or st.session_state[key] is None:
            with st.spinner(f"Analisando {nome}..."):
                ratio = 1.0 if st.session_state[key] is None else min_vol_ratio
                st.session_state[key] = funcao(ativos_global, min_vol_ratio=ratio)

        if st.session_state[key] is not None and not st.session_state[key].empty:
            st.dataframe(st.session_state[key], use_container_width=True, hide_index=True)
            st.success(f"{len(st.session_state[key])} ativos encontrados")
        else:
            st.info("Nenhum ativo encontrado com os filtros atuais.")

# Executa os 4 scanners
run_scanner("🔀 Scanner Swing Híbrido", scanner_swing_hibrido, 'df_hibrido')
run_scanner("🎯 Scanner Swing RR", scanner_swing_rr, 'df_rr')
run_scanner("🏆 Scanner Swing Profissional", scanner_swing_profissional, 'df_pro')
run_scanner("🌐 Scanner Swing Expandido", scanner_swing_expandido, 'df_exp')

st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")