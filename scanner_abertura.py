# -*- coding: utf-8 -*-
"""
Scanner de Abertura (Intraday 15m)
Focado na análise de volume e estabilização (Confluência).
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
from datetime import datetime

# ===================== LISTAS POR CATEGORIA (BUSCA UNIVERSAL) =====================
UNIV_BANCOS = ['ITUB4.SA', 'BBAS3.SA', 'BBDC4.SA', 'BBDC3.SA', 'SANB11.SA', 'BPAC11.SA', 'ITSA4.SA', 'BBSE3.SA', 'PSSA3.SA', 'BRSR6.SA', 'ABCB4.SA', 'BMGB4.SA']
UNIV_ENERGIA = ['EQTL3.SA', 'CMIG4.SA', 'CPFE3.SA', 'ENGI11.SA', 'CPLE3.SA', 'NEOE3.SA', 'AURE3.SA', 'TAEE11.SA', 'EGIE3.SA', 'COCE5.SA', 'ENEV3.SA', 'CSMG3.SA', 'SBSP3.SA', 'SAPR11.SA']
UNIV_PETROLEO = ['PETR4.SA', 'PETR3.SA', 'PRIO3.SA', 'CSAN3.SA', 'UGPA3.SA', 'VBBR3.SA', 'RECV3.SA', 'RAIZ4.SA']
UNIV_MINERACAO = ['VALE3.SA', 'GGBR4.SA', 'GGBR3.SA', 'GOAU4.SA', 'USIM5.SA', 'CSNA3.SA', 'CMIN3.SA', 'FESA4.SA', 'BRKM5.SA', 'UNIP6.SA']
UNIV_VAREJO = ['LREN3.SA', 'MGLU3.SA', 'GRND3.SA', 'ALPA4.SA', 'CEAB3.SA', 'RIAA3.SA', 'LJQQ3.SA', 'BHIA3.SA', 'AMAR3.SA', 'VULC3.SA']
UNIV_SAUDE = ['HAPV3.SA', 'RDOR3.SA', 'FLRY3.SA', 'HYPE3.SA', 'RADL3.SA', 'ONCO3.SA', 'BLAU3.SA', 'AALR3.SA']
UNIV_IMOBILIARIO = ['MRVE3.SA', 'CYRE3.SA', 'EVEN3.SA', 'EZTC3.SA', 'DIRR3.SA', 'TEND3.SA', 'LAVV3.SA', 'TRIS3.SA', 'MDNE3.SA', 'CURY3.SA', 'PLPL3.SA', 'MELK3.SA', 'MTRE3.SA', 'GFSA3.SA']
UNIV_ALIMENTOS = ['ABEV3.SA', 'JBSS32.SA', 'BRFT11.SA', 'MBRF3.SA', 'BEEF3.SA', 'MDIA3.SA', 'SMTO3.SA', 'SLCE3.SA', 'AGRO3.SA', 'CAML3.SA', 'JALL3.SA']
UNIV_TRANSPORTES = ['ECOR3.SA', 'EMBJ3.SA', 'RAIL3.SA', 'TGMA3.SA', 'HBSA3.SA', 'LOGN3.SA']
UNIV_TECH = ['VIVT3.SA', 'TIMS3.SA', 'TOTS3.SA', 'LWSA3.SA', 'POSI3.SA', 'INTB3.SA', 'CASH3.SA', 'BMOB3.SA', 'MLAS3.SA', 'DESK3.SA', 'SEQL3.SA']
UNIV_INDUSTRIAL = ['WEGE3.SA', 'B3SA3.SA', 'RENT3.SA', 'VAMO3.SA', 'SIMH3.SA', 'KEPL3.SA', 'TUPY3.SA', 'POMO4.SA', 'RAPT4.SA', 'LEVE3.SA', 'MILS3.SA', 'WIZC3.SA', 'MULT3.SA', 'IGTI11.SA']
UNIV_PAPEL = ['KLBN11.SA', 'SUZB3.SA', 'DXCO3.SA']
UNIV_EDUCACAO = ['COGN3.SA', 'YDUQ3.SA', 'ANIM3.SA', 'SEER3.SA']

_ACOES_UNIVERSAL = (UNIV_BANCOS + UNIV_ENERGIA + UNIV_PETROLEO + UNIV_MINERACAO + 
                    UNIV_VAREJO + UNIV_SAUDE + UNIV_IMOBILIARIO + UNIV_ALIMENTOS + 
                    UNIV_TRANSPORTES + UNIV_TECH + UNIV_INDUSTRIAL + UNIV_PAPEL + UNIV_EDUCACAO)

# Configs de interface Streamlit
st.set_page_config(page_title="Scanner de Abertura", layout="wide", page_icon="🌅")
st.title("🌅 SCANNER DE ABERTURA - ESTABILIZAÇÃO (15M)")
st.markdown("Analisa o **volume do primeiro candle (10:00)** vs **candle das 10:15** para encontrar ativos em estabilização após gap/euforia inicial. Ideal para ser rodado a partir das 10:30.")

# ===================== FUNÇÕES =====================
@st.cache_data(ttl=180) # Cache de 3 minutos
def baixar_dados_15m(symbol):
    try:
        df = yf.download(symbol, period="5d", interval="15m", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(1, axis=1)
        return df
    except Exception:
        return pd.DataFrame()

def processar_ativos(ativos, min_vol_fin, min_ratio, max_ratio, min_rvol):
    resultados = []
    
    progresso_texto = st.empty()
    barra_progresso = st.progress(0)
    
    total = len(ativos)
    for i, symbol in enumerate(ativos):
        progresso_texto.text(f"Analisando {symbol} ({i+1}/{total})...")
        barra_progresso.progress((i + 1) / total)
        
        df = baixar_dados_15m(symbol)
        if df is None or df.empty or len(df) < 10:
            continue
            
        try:
            # Pega apenas os dados do dia de hoje (ou do último dia útil disponível)
            ultimo_dia = df.index.date[-1]
            df_hoje = df[df.index.date == ultimo_dia]
            
            # Precisamos de pelo menos 2 candles hoje (10:00 e 10:15)
            if len(df_hoje) < 2:
                continue
                
            c1 = df_hoje.iloc[0] # Candle 1 (10:00)
            c2 = df_hoje.iloc[1] # Candle 2 (10:15)
            atual = df_hoje.iloc[-1] # Candle mais recente
            
            # Volume Financeiro do C1 (Preço Fechamento * Quantidade)
            vol_fin_c1 = c1['Close'] * c1['Volume']
            
            if vol_fin_c1 < min_vol_fin:
                continue
                
            vol_c1 = float(c1['Volume'])
            vol_c2 = float(c2['Volume'])
            
            if vol_c1 == 0:
                continue
                
            decay_ratio = vol_c2 / vol_c1
            
            # Volume Ratio (RVOL) - Confirmação para Swing
            # Compara o volume recente com a média de volume dos últimos 20 períodos de 15m
            df['Vol_Media_20'] = df['Volume'].rolling(20).mean()
            vol_media = float(df['Vol_Media_20'].iloc[-1])
            
            # Ratio do momento atual (pode ser o C2 ou o atual, vamos usar o acumulado da manhã vs média)
            # Para ser mais dinâmico, vamos pegar o volume da última barra fechada ou a média da manhã
            rvol = vol_c1 / vol_media if vol_media > 0 else 0
            rvol_c2 = vol_c2 / vol_media if vol_media > 0 else 0
            
            # Vamos usar o RVOL do C1 (abertura) como o grande confirmador institucional
            # E o Decay Ratio para saber se estabilizou
            
            if min_ratio <= decay_ratio <= max_ratio and rvol >= min_rvol:
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
                
                resultados.append({
                    'Ativo': symbol.replace('.SA', ''),
                    'Preço Atual': round(close_atual, 2),
                    'Tendência (15m)': tendencia,
                    'Volume Ratio (RVOL)': round(rvol, 2),
                    'Ratio Queda (10:15/10:00)': round(decay_ratio, 2),
                    'Vol Financeiro C1 (R$ Mi)': round(vol_fin_c1 / 1_000_000, 2),
                    'Var. desde Abertura (%)': round(var_percentual, 2),
                    'Hora Últ. Candle': df_hoje.index[-1].strftime('%H:%M')
                })
        except Exception as e:
            continue
            
    progresso_texto.empty()
    barra_progresso.empty()
    return pd.DataFrame(resultados)


# ===================== INTERFACE =====================
st.sidebar.header("Perfis de Confirmação")

perfil = st.sidebar.radio(
    "Escolha o seu perfil de risco:",
    ["🛡️ Conservador", "⚖️ Moderado", "🔥 Agressivo", "⚙️ Personalizado"],
    index=1
)

if perfil == "🛡️ Conservador":
    default_rvol = 1.5
    default_vol = 1_000_000
    st.sidebar.caption("Exige alto fluxo institucional na abertura (>1.5x)")
elif perfil == "⚖️ Moderado":
    default_rvol = 1.2
    default_vol = 500_000
    st.sidebar.caption("Equilíbrio para boas oportunidades (>1.2x)")
elif perfil == "🔥 Agressivo":
    default_rvol = 0.8
    default_vol = 300_000
    st.sidebar.caption("Permite fluxo médio e antecipações (>0.8x)")
else:
    default_rvol = 1.2
    default_vol = 500_000

disabled = perfil != "⚙️ Personalizado"

st.sidebar.markdown("---")
st.sidebar.header("Filtros Numéricos")

min_rvol = st.sidebar.number_input(
    "Volume Ratio Mínimo (RVOL)", 
    value=float(default_rvol), 
    step=0.1,
    disabled=disabled,
    help="Confirmação de Movimento: Quantas vezes o volume foi maior que a média."
)

min_vol = st.sidebar.number_input(
    "Volume Financeiro Mín. (R$)", 
    value=int(default_vol), 
    step=100_000,
    disabled=disabled,
    help="Liquidez mínima no candle das 10:00."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Decay Ratio (Estabilização)")
st.sidebar.markdown("Após a explosão inicial, o volume precisa acalmar para uma entrada segura.")
max_ratio = st.sidebar.slider("Máximo Ratio", 0.1, 1.0, 0.60, 0.05)
min_ratio = st.sidebar.slider("Mínimo Ratio", 0.0, 0.5, 0.10, 0.05)

st.sidebar.markdown("---")
st.sidebar.info("Recomendado executar às 10:30 ou 10:45.")

# Botão para rodar
if st.button("🚀 Rodar Scanner de Abertura (Ações)", type="primary"):
    with st.spinner("Analisando confirmações de swing trade..."):
        df_resultados = processar_ativos(_ACOES_UNIVERSAL, min_vol, min_ratio, max_ratio, min_rvol)
        
        if not df_resultados.empty:
            # Ordena pelos que tem maior RVOL (maior confirmação institucional)
            df_resultados = df_resultados.sort_values(by="Volume Ratio (RVOL)", ascending=False).reset_index(drop=True)
            
            st.success(f"Encontrados {len(df_resultados)} ativos confirmando movimento!")
            
            st.dataframe(
                df_resultados, 
                width=1000,
                hide_index=True,
                column_config={
                    "Preço Atual": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Var. desde Abertura (%)": st.column_config.NumberColumn(format="%.2f %%"),
                    "Volume Ratio (RVOL)": st.column_config.NumberColumn(format="%.1fx")
                }
            )
            
            # Botão de copiar (usando st.code para facilitar)
            lista_str = ",".join(df_resultados['Ativo'].tolist())
            st.markdown("### Lista para copiar (ProfitChart):")
            st.code(lista_str, language="text")
        else:
            st.warning("Nenhum ativo atendeu aos critérios de estabilização hoje.")
