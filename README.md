# 📈 Scanner de Ações - Mercado Brasileiro

Scanner consolidado para análise técnica do mercado brasileiro (B3), combinando estratégias de **swing trade** em uma interface Streamlit interativa.

---

## 📋 Descrição

Interface web que analisa ativos da B3 em tempo real usando indicadores técnicos (ADX, RSI, Volume, EMAs) para identificar oportunidades de swing trade. Inclui 4 scanners evoluídos, 3 scanners legados e uma **Busca Universal** que varre ~248 ativos (ações, BDRs, ETFs e FIIs).

---

## 🚀 Instalação e Execução

```bash
cd ~/projects/scanner_acoes
python3.13 -m venv venv313
source venv313/bin/activate
pip install -r requirements.txt
streamlit run scanner_interface_Streamlit.py
```

### 🐍 Versão do Python

| Versão | Status | Motivo |
|--------|--------|--------|
| 3.11   | ❌     | `pandas_ta` exige `>=3.12` |
| 3.12   | ✅     | Funciona |
| **3.13** | ✅ **Recomendado** | Funciona |
| 3.14   | ❌     | `numba`/`llvmlite` não compilam |

---

## ⚙️ Painel de Controle Global — Parâmetros

O painel de controle no topo da interface contém os parâmetros que controlam **todos os scanners** (exceto Legacy que têm filtros fixos). Estes valores são configurados via sliders.

### Lista de Ativos

| Opção | Descrição |
|-------|-----------|
| **Todos** | Blue Chips (9) + Mid/Small Caps (15) = 24 ativos |
| **Blue Chips** | Apenas 9 ativos de alta liquidez (PETR4, VALE3, ITUB4, etc.) |

> A **Busca Universal** (final da página) usa uma lista própria de ~248 ativos independente desta seleção.

### 📊 Volume Ratio Mínimo

| Aspecto | Detalhe |
|---------|---------|
| **O que é** | Razão entre o volume atual do candle e a média de volume dos últimos 20 períodos |
| **Fórmula** | `Volume Ratio = Volume Atual / Média(Volume, 20)` |
| **Faixa** | 1.0 a 3.0 |
| **Padrão** | **1.6** |
| **Significado** | Um ratio de 1.6 significa que o volume atual é 60% acima da média. Quanto maior, mais participação e confirmação do movimento |

| Valor | Interpretação |
|-------|--------------|
| < 1.0 | Volume abaixo da média — pouca participação |
| 1.0–1.5 | Volume normal |
| **1.5–2.0** | **Volume acima da média — interesse crescente** |
| > 2.0 | Volume muito alto — forte interesse institucional |
| > 3.0 | Volume explosivo — evento especial (notícia, earnings) |

### 📈 ADX Mínimo (Average Directional Index)

| Aspecto | Detalhe |
|---------|---------|
| **O que é** | Mede a **força** da tendência, independente da direção (alta ou baixa) |
| **Cálculo** | ADX(14) — baseado em 14 períodos |
| **Faixa do slider** | 15 a 35 |
| **Padrão** | **23** |
| **Significado** | Quanto maior o ADX, mais forte a tendência. Não indica direção, apenas força |

| Valor | Interpretação |
|-------|--------------|
| 0–15 | Sem tendência — mercado lateral |
| 15–20 | Tendência fraca — início possível |
| **20–25** | **Tendência moderada — aceitável para swing** |
| **25–35** | **Tendência forte — ideal para swing** |
| > 35 | Tendência muito forte — pode estar próximo da exaustão |

**ADX Rising**: Indica se o ADX está **crescendo** (valor atual > valor de 5 períodos atrás). ADX Rising = tendência ganhando força.

### ⬇️ RSI Mínimo (Relative Strength Index)

| Aspecto | Detalhe |
|---------|---------|
| **O que é** | Limite inferior do RSI para considerar momentum de alta |
| **Cálculo** | RSI(14) — baseado em 14 períodos |
| **Faixa do slider** | 40 a 60 |
| **Padrão** | **52** |
| **Significado** | Ativos com RSI abaixo deste valor são descartados — sem momentum suficiente |

### ⬆️ RSI Máximo

| Aspecto | Detalhe |
|---------|---------|
| **O que é** | Limite superior do RSI antes de considerar sobrecompra |
| **Faixa do slider** | 60 a 80 |
| **Padrão** | **70** |
| **Significado** | Ativos com RSI acima deste valor são descartados ou sinalizados como alerta de saída |

| Zona RSI | Interpretação |
|----------|--------------|
| < 30 | Sobrevendido — possível reversão de alta |
| 30–40 | Fraco — sem momentum |
| 40–50 | Neutro |
| **52–70** | **Zona ideal de momentum para swing** |
| 70–80 | Sobrecomprado — risco de correção |
| > 80 | Fortemente sobrecomprado — evitar compras |

---

## 📐 Sistema de Pontuação (Score)

O **Score** é uma pontuação de 0 a 110 que avalia a qualidade do setup de um ativo. **Quanto maior o score, mais critérios positivos o ativo atende simultaneamente.**

### Como o Score é calculado

| Critério | Pontos | Descrição |
|----------|--------|-----------|
| Preço > EMA20 | +20 | Preço acima da média de 20 períodos (tendência de curto prazo) |
| Preço > EMA50 | +15 | Preço acima da média de 50 períodos (tendência de médio prazo) |
| ADX ≥ mínimo do slider | +20 | Tendência com força suficiente |
| RSI na zona ideal | +20 | RSI entre o mínimo e máximo configurados nos sliders |
| Volume Ratio ≥ mínimo | +15 | Volume acima do limiar configurado |
| ADX Rising | +10 | ADX crescente — tendência ganhando força |
| +DI > -DI | +10 | Direção bullish — pressão compradora maior que vendedora |
| **Total máximo** | **110** | Todos os critérios atendidos |

### Score Mínimo (Busca Universal)

| Aspecto | Detalhe |
|---------|---------|
| **O que é** | Filtro pós-busca que esconde ativos com score abaixo do valor definido |
| **Faixa** | 0 a 80 |
| **Padrão** | **30** |
| **Quando usar** | Aumente para ver apenas os melhores setups; diminua para ver mais oportunidades |

| Score | Qualidade |
|-------|-----------|
| 0–30 | Fraco — poucos critérios atendidos |
| 30–50 | Razoável — vale monitorar |
| **50–70** | **Bom — setup com boa confluência** |
| **70–90** | **Muito bom — alta probabilidade** |
| 90–110 | Excelente — todos os critérios alinhados |

> **Importante**: O Score Mínimo da Busca Universal é um **filtro de exibição** — ele não altera a busca em si, apenas esconde da tabela os ativos que ficaram abaixo do valor. Você pode ajustar após a busca sem re-executar.

---

## 🔺 Tríade (ADX + RSI + Volume)

A Tríade é uma avaliação combinada dos 3 pilares de um bom setup de swing:

| Status | Significado |
|--------|-------------|
| ✅ **Completa** | ADX ≥ mínimo **E** RSI na zona ideal **E** Volume ≥ mínimo — todos alinhados |
| ⚠️ **Parcial** | Pelo menos um dos 3 critérios está fora da zona ideal |

---

## 🔄 +DI / -DI (Indicadores Direcionais)

| Indicador | Significado |
|-----------|-------------|
| **+DI** (Positive Directional Indicator) | Mede a força do movimento de **alta** |
| **-DI** (Negative Directional Indicator) | Mede a força do movimento de **baixa** |
| **+DI > -DI** | Pressão compradora dominante — **bullish** |
| **+DI < -DI** | Pressão vendedora dominante — **bearish** |

---

## 🚨 Sinais de Saída

| Sinal | Significado |
|-------|-------------|
| ✅ | Sem alertas — setup seguro |
| ⚠️ ADX↓ | ADX caindo — tendência perdendo força, considerar encerrar posição |
| ⚠️ RSI↑ | RSI acima do máximo configurado — sobrecompra, risco de correção |

---

## 📊 Scanners Evoluídos

Estes scanners usam os parâmetros dos sliders do Painel de Controle:

### 🔀 Scanner Swing Híbrido (Daily + 1H)

| Aspecto | Detalhe |
|---------|---------|
| **Timeframes** | Daily (análise) + 1H (confirmação) |
| **Filtros** | Preço > EMA20, ADX ≥ slider, RSI na faixa, Vol ≥ slider, ADX Rising |
| **Uso ideal** | Visão geral rápida de ativos em tendência |

### 🎯 Scanner Swing RR (Daily + ATR Targets)

| Aspecto | Detalhe |
|---------|---------|
| **Base** | Mesmos filtros do Híbrido |
| **Extra** | Cálculo de Stop Loss (ATR × 1.8) e alvos 1:2 e 1:3 |
| **Stop** | `Preço - (ATR × 1.8)` |
| **Alvo 1:2** | `Preço + (Risco × 2)` |
| **Alvo 1:3** | `Preço + (Risco × 3)` |
| **Uso ideal** | Dimensionamento de posição e gestão de risco |

### 🏆 Scanner Swing Profissional (Daily + 1H + 30M)

| Aspecto | Detalhe |
|---------|---------|
| **Timeframes** | Daily + 1H + 30M (multi-timeframe completo) |
| **Filtros** | Mais rigorosos — exige: Preço > EMA50, ADX Rising, +DI > -DI, Tríade completa |
| **Uso ideal** | Setups de alta convicção — menos resultados, melhor qualidade |

### 🌐 Scanner Swing Expandido (Mid + Small Caps)

| Aspecto | Detalhe |
|---------|---------|
| **Lista** | Sempre usa lista completa (24 ativos) |
| **Filtros** | Semelhantes ao Híbrido mas com volume médio mínimo relaxado (2.5M) |
| **Uso ideal** | Descobrir oportunidades em ativos menos óbvios |

---

## 📚 Scanners Legacy

Scanners das versões anteriores mantidos para comparação. Têm **filtros fixos** (não usam os sliders):

| Scanner | Filtros Fixos |
|---------|---------------|
| **Profissional** | Vol > 1.5x, EMA20/50, ADX > 20, RSI 45-75 |
| **Intraday/Swing** | Vol > 1.7x, Liquidez > 8M, ADX ≥ 22, RSI 47-73 |
| **Expandida** | Vol > 1.5x, Vol Médio ≥ 2.5M, EMA20/50, ADX > 20, RSI 45-75 |

---

## 🔍 Busca Universal — Todos os Ativos da B3

Seção no final da página que executa os **mesmos 4 scanners primários** (Híbrido, RR, Profissional, Expandido) em **~248 ativos** da B3, usando os **mesmos filtros e parâmetros dos sliders**.

### Como funciona

1. Os ativos já analisados nos scanners principais (9 ou 24) são **excluídos** para evitar duplicidade
2. Os 4 scanners rodam com **metodologia idêntica** nos ~224 ativos restantes
3. Resultados são exibidos em 4 expanders separados, mesmo formato dos scanners primários
4. Cada scanner tem seu próprio **botão de copiar** com prompt de trader

### Universo de Ativos

| Categoria | Qtd | Exemplos |
|-----------|-----|----------|
| **Ações** | ~143 | Bancos, Energia, Petróleo, Mineração, Varejo, Saúde, Imobiliário, Alimentos, Transportes, Tech, Industrial, Papel, Educação |
| **BDRs** | ~53 | Apple, Microsoft, Nvidia, Google, Meta, Tesla, JPMorgan, Visa, Coca-Cola, Pfizer... |
| **ETFs** | ~24 | BOVA11, SMAL11, IVVB11, HASH11, GOLD11, NASD11, IMAB11... |
| **FIIs** | ~28 | HGLG11, XPML11, KNRI11, MXRF11, CPTS11, VISC11, BTLG11... |

### Scanners executados

| Scanner | Filtros (idênticos aos primários) |
|---------|-----------------------------------|
| 🔀 **Híbrido** | Preço > EMA20, ADX ≥ slider, RSI na faixa, Vol ≥ slider, ADX Rising + confirmação 1H |
| 🎯 **RR** | Mesmos do Híbrido + Stop (ATR×1.8) e Alvos 1:2, 1:3 |
| 🏆 **Profissional** | Preço > EMA50, ADX Rising, +DI > -DI, Tríade completa + tendência 1H e 30M |
| 🌐 **Expandido** | Preço > EMA20, ADX Rising, Vol médio ≥ 2.5M |

### Botão Independente

A Busca Universal tem seu **próprio botão** "🔍 Executar 4 Scanners em X Ativos Adicionais" porque:
- Varre ~224 ativos extras (vs 9–24 dos scanners normais)
- Executa 4 scanners sequencialmente → pode demorar **5–10 minutos**
- Mostra **barra de progresso** por scanner (1/4, 2/4, 3/4, 4/4)
- **Não bloqueia** os scanners normais que rodam com "🔄 Atualizar Scanners"

---

## 📈 Indicadores Técnicos Utilizados

| Indicador | Período | Uso |
|-----------|---------|-----|
| **EMA** (Exponential Moving Average) | 9, 20, 50 | Direção da tendência por timeframe |
| **RSI** (Relative Strength Index) | 14 | Momentum e sobrecompra/sobrevenda |
| **ADX** (Average Directional Index) | 14 | Força da tendência |
| **+DI / -DI** (Directional Indicators) | 14 | Direção da tendência (bullish/bearish) |
| **ATR** (Average True Range) | 14 | Volatilidade — usado para stops e alvos |
| **MACD** (Moving Average Convergence Divergence) | 12, 26, 9 | Momentum e cruzamentos (Legacy scanners) |
| **Volume Ratio** | Média de 20 | Participação relativa ao normal |

---

## 🛠️ Tecnologias

| Tecnologia | Uso |
|------------|-----|
| **Streamlit** | Interface web interativa |
| **yfinance** | Download de dados de mercado em tempo real |
| **pandas** | Manipulação e análise de dados |
| **pandas_ta** | Cálculo de indicadores técnicos |

---

## ⚠️ Aviso

Este código é apenas para fins educacionais. Não constitui recomendação de investimento. Sempre faça sua própria análise e consulte um profissional qualificado antes de tomar decisões de investimento.
