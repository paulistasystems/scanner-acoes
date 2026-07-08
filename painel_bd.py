# -*- coding: utf-8 -*-
"""
painel_bd.py — Painel de inspeção do banco de dados (SQLite) do scanner.

Expõe TODOS os dados persistidos em uma única visualização Streamlit:
  • Resumo agregado (contagens por tabela/intervalo, janela temporal)
  • Tabela `bars`          (candles OHLCV) com filtros por ativo/intervalo/data + CSV
  • Tabela `fill_state`    (o que já está preenchido para o pregão corrente)
  • Tabela `fetch_failures` (o que falhou ao buscar no yfinance)

É apenas LEITURA: não escreve, não invalida e não aciona o yfinance. Útil para
auditar o que os scanners efetivamente materializaram no scanner.db.

Execução:
    venv313/bin/streamlit run painel_bd.py
"""

import streamlit as st
import pandas as pd

import data_layer

st.set_page_config(page_title="Painel do Banco", layout="wide", page_icon="🗄️")
st.title("🗄️ PAINEL DO BANCO DE DADOS")
st.caption(
    "Visualização **somente leitura** de todos os dados persistidos. "
    f"Banco: `{data_layer.db_path()}`."
)

# ===================== RESUMO AGREGADO =====================
with st.spinner("Lendo resumo do banco…"):
    s = data_layer.db_summary()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Candles (bars)", f"{s['bars']:,}".replace(",", "."))
c2.metric("Símbolos distintos", f"{s['distinct_symbols']:,}".replace(",", "."))
c3.metric("Pares preenchidos", f"{s['fill_state']:,}".replace(",", "."))
c4.metric("Falhas de fetch", f"{s['fetch_failures']:,}".replace(",", "."))

if s["ts_min"] and s["ts_max"]:
    st.caption(f"Janela temporal dos candles: **{s['ts_min']}** → **{s['ts_max']}**")

df_int = pd.DataFrame(s["by_interval"], columns=["interval", "candles"])
df_int["candles"] = df_int["candles"].map(lambda v: f"{v:,}".replace(",", "."))
if not df_int.empty:
    st.markdown("**Candles por intervalo:**")
    st.dataframe(df_int, hide_index=True, use_container_width=True)

st.divider()

# ===================== TABELAS =====================
tab_bars, tab_fill, tab_fail = st.tabs(
    ["🕯️ Candles (bars)", "✅ Estado de preenchimento", "⚠️ Falhas de fetch"]
)

# ----------------------------- bars -----------------------------
with tab_bars:
    st.subheader("Candles OHLCV")
    fc1, fc2, fc3 = st.columns([2, 1, 2])
    with fc1:
        symbol = st.text_input("Ativo (ex.: PETR4.SA — vazio = todos)", "", key="bars_symbol")
    with fc2:
        interval = st.selectbox("Intervalo", ["", "1d", "1h", "30m", "15m"], index=0, key="bars_interval")
    with fc3:
        datas = st.date_input("Janela de datas (abertura do candle)", [], key="bars_dates")
    start = datas[0].isoformat() if len(datas) >= 1 else None
    end = datas[1].isoformat() if len(datas) >= 2 else None

    limit = st.slider("Limite de linhas (0 = sem limite)", 0, 5000, 1000, step=500, key="bars_limit")

    df_bars = data_layer.read_bars(
        symbol=symbol.strip() or None,
        interval=interval or None,
        start=start,
        end=end,
        limit=limit or None,
    )
    if df_bars.empty:
        st.info("Nenhum candle para os filtros informados.")
    else:
        st.markdown(f"**{len(df_bars):,}** linha(s) retornada(s).".replace(",", "."))
        st.dataframe(df_bars, hide_index=True, use_container_width=True)
        st.download_button(
            "⬇️ Baixar CSV",
            df_bars.to_csv(index=False).encode("utf-8"),
            file_name="bars.csv",
            mime="text/csv",
        )

# ----------------------------- fill_state -----------------------------
with tab_fill:
    st.subheader("Estado de preenchimento (fill_state)")
    st.caption("Quais pares (ativo, intervalo) já estão preenchidos para o pregão corrente.")
    df_fill = data_layer.read_fill_state()
    if df_fill.empty:
        st.info("Tabela fill_state vazia — rode um scanner para popular o banco.")
    else:
        st.dataframe(df_fill, hide_index=True, use_container_width=True)
        st.download_button(
            "⬇️ Baixar CSV",
            df_fill.to_csv(index=False).encode("utf-8"),
            file_name="fill_state.csv",
            mime="text/csv",
        )

# ----------------------------- fetch_failures -----------------------------
with tab_fail:
    st.subheader("Falhas de aquisição (fetch_failures)")
    st.caption("Ativos que falharam ao baixar do yfinance — base para blacklist e diagnóstico.")
    df_fail = data_layer.list_failures()
    if df_fail.empty:
        st.info("Nenhuma falha registrada. 🎉")
    else:
        st.dataframe(df_fail, hide_index=True, use_container_width=True)
        st.download_button(
            "⬇️ Baixar CSV",
            df_fail.to_csv(index=False).encode("utf-8"),
            file_name="fetch_failures.csv",
            mime="text/csv",
        )
