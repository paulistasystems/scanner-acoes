# -*- coding: utf-8 -*-
"""
Scanner de Abertura (Intraday 15m)
Focado na análise de volume e estabilização (Confluência).
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import data_layer
import painel_bd

# ===================== LISTAS POR CATEGORIA (BUSCA UNIVERSAL) =====================
UNIV_BANCOS = ['ITUB4.SA', 'BBAS3.SA', 'BBDC4.SA', 'BBDC3.SA', 'SANB11.SA', 'BPAC11.SA', 'ITSA4.SA', 'BBSE3.SA', 'PSSA3.SA', 'BRSR6.SA', 'ABCB4.SA', 'BMGB4.SA', 'IRBR3.SA']
UNIV_ENERGIA = ['EQTL3.SA', 'CMIG4.SA', 'CPFE3.SA', 'ENGI11.SA', 'CPLE3.SA', 'AURE3.SA', 'TAEE11.SA', 'EGIE3.SA', 'COCE5.SA', 'ENEV3.SA', 'CSMG3.SA', 'SBSP3.SA', 'SAPR11.SA']
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

# BDRs
BDR_TECH = ['AAPL34.SA', 'MSFT34.SA', 'AMZO34.SA', 'GOGL34.SA', 'NVDC34.SA', 'TSLA34.SA', 'NFLX34.SA', 'ADBE34.SA', 'ORCL34.SA', 'CSCO34.SA', 'AVGO34.SA', 'QCOM34.SA', 'A1MD34.SA', 'PYPL34.SA', 'U1BE34.SA', 'S1PO34.SA']
BDR_FINANCAS = ['JPMC34.SA', 'BOAC34.SA', 'GSGI34.SA', 'MSBR34.SA', 'BERK34.SA', 'VISA34.SA']
BDR_CONSUMO = ['COCA34.SA', 'PEPB34.SA', 'MCDC34.SA', 'NIKE34.SA', 'SBUB34.SA', 'PGCO34.SA', 'WALM34.SA', 'HOME34.SA', 'DISB34.SA']
BDR_SAUDE = ['JNJB34.SA', 'PFIZ34.SA', 'MRCK34.SA', 'ABBV34.SA', 'LILY34.SA']
BDR_INDUSTRIAL = ['CATP34.SA', 'HONB34.SA', 'MMMC34.SA', 'EXXO34.SA', 'CHVX34.SA', 'DHER34.SA']
_BDRS_UNIVERSAL = BDR_TECH + BDR_FINANCAS + BDR_CONSUMO + BDR_SAUDE + BDR_INDUSTRIAL

# ETFs e FIIs
_ETFS_UNIVERSAL = ['BOVA11.SA', 'BOVV11.SA', 'SMAL11.SA', 'XBOV11.SA', 'DIVO11.SA', 'MATB11.SA', 'FIND11.SA', 'GOVE11.SA', 'PIBB11.SA', 'IVVB11.SA', 'SPXI11.SA', 'NASD11.SA', 'HASH11.SA', 'QBTC11.SA', 'ETHE11.SA', 'GOLD11.SA', 'TECK11.SA', 'JURO11.SA', 'IMAB11.SA', 'IRFM11.SA', 'B5P211.SA', 'FIXA11.SA']
_FIIS_UNIVERSAL = ['HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VILG11.SA', 'BRCO11.SA', 'XPML11.SA', 'VISC11.SA', 'HSML11.SA', 'KNRI11.SA', 'PVBI11.SA', 'JSRE11.SA', 'BRCR11.SA', 'RCRB11.SA', 'MXRF11.SA', 'CPTS11.SA', 'RBRR11.SA', 'RECR11.SA', 'VGIP11.SA', 'KNCR11.SA', 'HGCR11.SA', 'HGBS11.SA', 'ALZR11.SA', 'TRXF11.SA', 'TGAR11.SA', 'RBRF11.SA']

ATIVOS_B3_AMPLIADO = list(set(_ACOES_UNIVERSAL + _BDRS_UNIVERSAL + _ETFS_UNIVERSAL + _FIIS_UNIVERSAL))

# Configs de interface Streamlit
st.set_page_config(page_title="Scanner de Abertura", layout="wide", page_icon="🌅")
st.title("🌅 SCANNER DE ABERTURA - ESTABILIZAÇÃO (15M)")
st.markdown("Analisa o **volume do primeiro candle (10:00)** vs **candle das 10:15** para encontrar ativos em estabilização após gap/euforia inicial. Ideal para ser rodado a partir das 10:30.")

# ===================== FUNÇÕES =====================
def baixar_dados_15m(symbol):
    """Candles 15m via banco SQLite (data_layer). yfinance só preenche dados ausentes."""
    return data_layer.get_bars(symbol, "15m", "5d")


def baixar_dados_30m(symbol):
    """Candles 30m via banco SQLite (data_layer). yfinance só preenche dados ausentes.

    Usado pelo bloco de confluência 30M+15M (confirmação de vela de alta)."""
    return data_layer.get_bars(symbol, "30m", "15d")


def _prewarm_com_progresso(ativos, intervals, rotulo="Baixando dados"):
    """Aquisição antes da análise via data_layer.prewarm, com barra de progresso."""
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

    progresso_texto = st.empty()
    barra_progresso = st.progress(0)

    # Limite mais permissivo (Agressivo) -> não descarta candidatos antes da filtragem por perfil
    min_vol_fin_floor = 300_000
    min_rvol_floor = 0.8

    _prewarm_com_progresso(ativos, ['15m'])

    total = len(ativos)
    for i, symbol in enumerate(ativos):
        progresso_texto.text(f"Analisando {symbol} ({i+1}/{total})...")
        barra_progresso.progress((i + 1) / total)

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

    progresso_texto.empty()
    barra_progresso.empty()
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


# ===================== CONFLUÊNCIA 30M + 15M (vela de alta forte + volume) =====================
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
    progresso_texto = st.empty()
    barra_progresso = st.progress(0)

    _prewarm_com_progresso(ativos, ['15m', '30m'])

    total = len(ativos)
    for i, symbol in enumerate(ativos):
        progresso_texto.text(f"Confluência 15m/30m: {symbol} ({i+1}/{total})...")
        barra_progresso.progress((i + 1) / total)
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

    progresso_texto.empty()
    barra_progresso.empty()
    return pd.DataFrame(resultados)


# ===================== PERFIS DE RISCO =====================
# O scanner roda automaticamente no carregamento da página (sem seleção de perfil)
# e exibe os resultados já separados por cada perfil de risco abaixo.
PERFIS = [
    {
        "nome": "🛡️ Conservador",
        "min_rvol": 1.5,
        "min_vol": 1_000_000,
        "desc": "Exige alto fluxo institucional na abertura (RVOL > 1.5x e Vol. Fin. > R$ 1 Mi).",
    },
    {
        "nome": "⚖️ Moderado",
        "min_rvol": 1.2,
        "min_vol": 500_000,
        "desc": "Equilíbrio para boas oportunidades (RVOL > 1.2x e Vol. Fin. > R$ 500 mil).",
    },
    {
        "nome": "🔥 Agressivo",
        "min_rvol": 0.8,
        "min_vol": 300_000,
        "desc": "Permite fluxo médio e antecipações (RVOL > 0.8x e Vol. Fin. > R$ 300 mil).",
    },
]

# ===================== INTERFACE =====================
st.sidebar.header("Decay Ratio (Estabilização)")
st.sidebar.markdown("Após a explosão inicial, o volume precisa acalmar para uma entrada segura.")
max_ratio = st.sidebar.slider("Máximo Ratio", 0.1, 1.0, 0.60, 0.05)
min_ratio = st.sidebar.slider("Mínimo Ratio", 0.0, 0.5, 0.10, 0.05)

st.sidebar.markdown("---")
st.sidebar.header("Confluência 30M + 15M")
st.sidebar.markdown(
    "Vela de abertura (10:00) de alta forte nos dois timeframes + confirmação de volume."
)
rvol_min = st.sidebar.slider("RVOL mínimo (volume)", 0.5, 3.0, 1.0, 0.1)

st.sidebar.markdown("---")
st.sidebar.info(
    "🔄 O scanner roda automaticamente ao abrir a página e mostra os resultados "
    "separados por perfil de risco. Recomendado executar às 10:30 ou 10:45."
)

# ===================== EXECUÇÃO AUTOMÁTICA (PAGE LOAD) =====================
with st.spinner(f"Analisando confirmações de swing trade em {len(ATIVOS_B3_AMPLIADO)} ativos..."):
    df_todos = coletar_candidatos(ATIVOS_B3_AMPLIADO, min_ratio, max_ratio)
    df_todos = classificar_perfil(df_todos, PERFIS)

if df_todos.empty:
    if data_layer.session_today() is None:
        st.warning("Hoje não há pregão na B3 (fim de semana). Rode em dia útil, a partir das 10:15.")
    else:
        st.warning("Nenhum ativo atendeu aos critérios de estabilização hoje.")
else:
    st.success(
        f"{len(df_todos)} ativo(s) em estabilização encontrados. "
        "Resultados separados por perfil de risco 👇"
    )

    col_config = {
        "Preço Atual": st.column_config.NumberColumn(format="R$ %.2f"),
        "Var. desde Abertura (%)": st.column_config.NumberColumn(format="%.2f %%"),
        "Volume Ratio (RVOL)": st.column_config.NumberColumn(format="%.1fx"),
    }

    # Resultados em blocos empilhados (um por perfil), tudo na mesma página — sem abas.
    for perfil in PERFIS:
        df_perfil = df_todos[df_todos['perfil'] == perfil['nome']] \
            .drop(columns='perfil') \
            .sort_values(by='Volume Ratio (RVOL)', ascending=False) \
            .reset_index(drop=True)
        st.subheader(perfil["nome"])
        st.caption(perfil["desc"])
        if df_perfil.empty:
            st.info(f"Nenhum ativo no perfil {perfil['nome']} hoje.")
            st.divider()
            continue

        st.markdown(f"**{len(df_perfil)} ativo(s)** neste perfil.")
        st.dataframe(
            df_perfil,
            width=1000,
            hide_index=True,
            column_config=col_config,
        )

        # Lista para copiar (ProfitChart)
        lista_str = ",".join(df_perfil['Ativo'].tolist())
        st.markdown("##### Lista para copiar (ProfitChart):")
        st.code(lista_str, language="text")
        st.divider()

# ===================== Bloco: Confluência 30M + 15M (vela de alta forte + volume) =====================
st.header("📈 CONFLUÊNCIA 30M + 15M — Vela de abertura (10:00) de alta")
st.markdown(
    f"Lista ativos cuja **primeira vela do dia (abertura 10:00)** é de **alta forte** em "
    f"**ambos os timeframes** (15m E 30m) **com confirmação de volume** "
    f"(RVOL ≥ {rvol_min:.1f}x na vela de abertura de cada timeframe). Confluência "
    "multi-timeframe de compradores logo na abertura — gatilho conservador de entrada."
)

with st.spinner(f"Buscando vela de alta forte + volume em {len(ATIVOS_B3_AMPLIADO)} ativos..."):
    df_conf = coletar_confluencia_15m_30m(ATIVOS_B3_AMPLIADO, rvol_min)

if df_conf.empty:
    if data_layer.session_today() is None:
        st.warning("Hoje não há pregão na B3 (fim de semana). Rode em dia útil, a partir das 10:30.")
    else:
        st.info(
            f"Nenhum ativo com vela de ABERTURA (10:00) de alta forte em 15m E 30m com "
            f"volume ≥ {rvol_min:.1f}x hoje. Rode a partir das 10:30 (quando fecha a vela de 30m)."
        )
else:
    st.success(f"{len(df_conf)} ativo(s) em confluência 15m + 30m.")
    df_conf = df_conf.sort_values(by='RVOL 30m', ascending=False).reset_index(drop=True)

    col_config_conf = {
        'Preço': st.column_config.NumberColumn(format="R$ %.2f"),
        'RVOL 30m': st.column_config.NumberColumn(format="%.2fx"),
        'RVOL 15m': st.column_config.NumberColumn(format="%.2fx"),
        'Fech. 30m (%)': st.column_config.NumberColumn(format="%.0f %%"),
        'Fech. 15m (%)': st.column_config.NumberColumn(format="%.0f %%"),
        'Var. Abertura 30m (%)': st.column_config.NumberColumn(format="%.2f %%"),
    }
    st.dataframe(df_conf, width=1100, hide_index=True, column_config=col_config_conf)
    st.caption(
        "Tudo medido na vela de ABERTURA (10:00) de hoje. Fech. (%) = posição do fechamento "
        "no range da vela (≥ 67% = forte, compradores no controle). RVOL = volume da vela de "
        "abertura / média de 20 períodos do candle anterior. Tendência 30m é informativa "
        "(close vs EMA20). Recomendado rodar a partir das 10:30 (quando fecha a vela de 30m)."
    )

    lista_conf = ",".join(df_conf['Ativo'].tolist())
    st.markdown("##### Lista para copiar (ProfitChart):")
    st.code(lista_conf, language="text")

st.divider()

# ===================== Painel: inspeção do banco de dados (somente leitura) =====================
# Embutido no MESMO app disparado por run_abertura.sh para compartilhar
# filesystem/banco com o scanner. No deploy (Streamlit Cloud: cada app tem seu
# próprio container/filesystem efêmero), um painel como app separado veria um
# scanner.db vazio; aqui, no mesmo processo, ele enxerga o que o scanner acabou
# de preencher.
painel_bd.render_db_panel()
