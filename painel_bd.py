# -*- coding: utf-8 -*-
"""
painel_bd.py — Módulo do painel de inspeção do banco de dados (SQLite) do scanner.

Biblioteca importada pelos apps de scanner (scanner_interface_Streamlit.py e
scanner_abertura.py) — NÃO é um app standalone. Expõe render_db_panel(), que
apresenta TODOS os dados persistidos em scanner.db (bars/fill_state/fetch_failures)
em uma visualização SOMENTE LEITURA (não aciona yfinance, não escreve, não invalida).

Por que embutido (e não um app separado): no Streamlit Cloud cada app roda num
container/filesystem próprio, então um painel implantado como app separado veria um
scanner.db VAZIO. Embutido nos apps disparados por run.sh / run_abertura.sh, o painel
compartilha o MESMO processo/banco do scanner — enxerga o que ele acabou de preencher.

Uso (a partir de um app de scanner):

    import painel_bd
    painel_bd.render_db_panel()
"""

import streamlit as st
import pandas as pd

import data_layer


def render_db_panel():
    """Renderiza o painel do banco (resumo + abas) no container atual.

    Somente leitura. Pode ser chamado dentro de qualquer app Streamlit — NÃO chama
    `st.set_page_config`/`st.title` (essas são decisões por app, chamadas uma vez no
    topo). Renderiza dentro de um expander recolhido para não poluir a página."""
    with st.expander("🗄️ Banco de dados (scanner.db) — somente leitura", expanded=False):
        st.caption(
            "Visualização **somente leitura** de tudo que foi materializado no banco. "
            f"Banco: `{data_layer.db_path()}`. **Inerte durante o scan** — clique para carregar."
        )
        # Gate sob demanda: NÃO consulta o banco no run normal / scan automático — só ao
        # clicar. Persiste em session_state para não recolher ao mexer nos filtros abaixo.
        if st.button("📊 Carregar dados do banco", type="primary", key="pbd_load"):
            st.session_state["pbd_loaded"] = True
        if not st.session_state.get("pbd_loaded"):
            return

        with st.spinner("Lendo o banco…"):
            s = data_layer.db_summary()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Candles (bars)", f"{s['bars']:,}".replace(",", "."))
        c2.metric("Símbolos distintos", f"{s['distinct_symbols']:,}".replace(",", "."))
        c3.metric("Pares preenchidos", f"{s['fill_state']:,}".replace(",", "."))
        c4.metric("Falhas de fetch", f"{s['fetch_failures']:,}".replace(",", "."))

        if s["ts_min"] and s["ts_max"]:
            st.caption(f"Janela temporal dos candles: **{s['ts_min']}** → **{s['ts_max']}**")

        df_int = pd.DataFrame(s["by_interval"], columns=["interval", "candles"])
        if not df_int.empty:
            df_int["candles"] = df_int["candles"].map(lambda v: f"{v:,}".replace(",", "."))
            st.markdown("**Candles por intervalo:**")
            st.dataframe(df_int, hide_index=True, use_container_width=True)

        tab_bars, tab_fill, tab_fail = st.tabs(
            ["🕯️ Candles (bars)", "✅ Estado de preenchimento", "⚠️ Falhas de fetch"]
        )

        # ----------------------------- bars -----------------------------
        with tab_bars:
            fc1, fc2, fc3 = st.columns([2, 1, 2])
            with fc1:
                symbol = st.text_input("Ativo (ex.: PETR4.SA — vazio = todos)", "", key="pbd_symbol")
            with fc2:
                interval = st.selectbox("Intervalo", ["", "1d", "1h", "30m", "15m"], index=0, key="pbd_interval")
            with fc3:
                datas = st.date_input("Janela de datas (abertura do candle)", [], key="pbd_dates")
            start = datas[0].isoformat() if len(datas) >= 1 else None
            end = datas[1].isoformat() if len(datas) >= 2 else None

            # Sem opção "0 = ilimitado": carregar a tabela bars inteira (~35 MB)
            # trava a aplicação. O limite é sempre um valor positivo.
            limit = st.slider("Limite de linhas", 50, 5000, 50, step=50, key="pbd_limit")

            df_bars = data_layer.read_bars(
                symbol=symbol.strip() or None,
                interval=interval or None,
                start=start,
                end=end,
                limit=limit,
            )
            if df_bars.empty:
                st.info("Nenhum candle para os filtros informados (ou banco ainda vazio — rode um scanner primeiro).")
            else:
                st.markdown(f"**{len(df_bars):,}** linha(s) retornada(s).".replace(",", "."))
                st.dataframe(df_bars, hide_index=True, use_container_width=True)
                st.download_button(
                    "⬇️ Baixar CSV",
                    df_bars.to_csv(index=False).encode("utf-8"),
                    file_name="bars.csv",
                    mime="text/csv",
                    key="pbd_dl_bars",
                )

        # ----------------------------- fill_state -----------------------------
        with tab_fill:
            st.caption("Quais pares (ativo, intervalo) já estão preenchidos para o pregão corrente.")
            df_fill = data_layer.read_fill_state()
            if df_fill.empty:
                st.info("fill_state vazio — rode um scanner para popular o banco.")
            else:
                st.dataframe(df_fill, hide_index=True, use_container_width=True)
                st.download_button(
                    "⬇️ Baixar CSV",
                    df_fill.to_csv(index=False).encode("utf-8"),
                    file_name="fill_state.csv",
                    mime="text/csv",
                    key="pbd_dl_fill",
                )

        # ----------------------------- fetch_failures -----------------------------
        with tab_fail:
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
                    key="pbd_dl_fail",
                )
