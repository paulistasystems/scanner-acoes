# Scanner Ações BR - Roadmap

## Visão Geral

Este projeto é um **scanner multi-timeframe** para análise técnica de ações brasileiras (B3). Combina indicadores clássicos (RSI, ADX, EMAs, MACD, Volume) com análise de confluência entre timeframes (Daily, 1H, 30M) para identificar oportunidades de compra.

### Scanner Principal: 🔥 Swing Trade Fusion

O scanner **hero** da aplicação. Combina o melhor dos scanners Legacy (granularidade multi-TF, scoring por timeframe, confluência em 4 níveis) com recursos evoluídos (Tríade, DI+/DI-, ADX Rising, Stop/Alvos ATR, sinais de saída, controle via sliders).

**Por que usar o Fusion:**
- **Multi-TF completo**: Analisa Daily, 1H e 30M simultaneamente
- **Score ponderado**: Daily×30% + 1H×40% + 30M×30% (1H = timeframe principal)
- **Confluência em 4 níveis**: Excelente ✅✅ / Boa ✅ / Parcial ⚠️ / Fraca ❌
- **Tríade por timeframe**: ADX + RSI + Volume na zona ideal
- **Gestão de risco**: Stop (ATR×1.8) + Alvos 1:2 e 1:3
- **Sinais de saída**: Alertas quando ADX cai ou RSI entra em sobrecompra

---

## Scanners Disponíveis

### 1. 🔥 Swing Trade Fusion (HERO SCANNER) ⭐
**Status**: Principal / Recomendado  
**Timeframes**: Daily + 1H + 30M  
**Output**: RSI D/1H/30M, ADX D/1H/30M, Score D/1H/30M/Total, Confluência, Tríade D+1H, Stop, Alvos 1:2/1:3, +DI/-DI, ADX Rising D+1H, Sinais de Saída  
**Controle via Sliders**: ✅ Sim  
**Melhor uso**: **Scanner principal para trading de swing curto prazo (1-3 dias)**

**Características:**
- Filtro de liquidez: Volume médio ≥ R$ 5M
- Tríade Multi-TF: Verifica ADX/RSI/Volume na zona ideal para cada TF
- Score por timeframe (max: D=100, H=100, 30M=70) ponderado para Total
- Confluência 4 níveis baseada em alinhamento de preço/EMA20, ADX>20, RSI na zona, MACD>0
- Stop Loss ATR-based (1.8×ATR)
- Alvos RR 1:2 e 1:3
- Sinais de saída automática (ADX↓, RSI↑)

---

### 2. 🔀 Scanner Swing Híbrido (Daily + 1H)
**Status**: Evoluído  
**Timeframes**: Daily + 1H (confirmação)  
**Output**: RSI, ADX, ADX Rising, +DI/-DI, Tríade, Score  
**Controle via Sliders**: ✅ Sim  
**Melhor uso**: Análise Daily com confirmação de tendência 1H

**Características:**
- Tríade básica (ADX + RSI + Volume)
- Confirmação de tendência 1H
- Score único (Daily)

---

### 3. 🎯 Scanner Swing RR (Daily + ATR Targets)
**Status**: Evoluído  
**Timeframes**: Daily  
**Output**: RSI, ADX, ADX Rising, +DI/-DI, Tríade, Stop, Alvo 1:2, Alvo 1:3, RR  
**Controle via Sliders**: ✅ Sim  
**Melhor uso**: Foco em risco/retorno com stop e alvos pré-definidos

**Características:**
- Mesma base do Híbrido
- Stop = Preço - (ATR × 1.8)
- Alvo 1:2 = Preço + (Risco × 2)
- Alvo 1:3 = Preço + (Risco × 3)
- RR Ratio calculado automaticamente

---

### 4. 🏆 Scanner Swing Profissional (Daily + 1H + 30M)
**Status**: Evoluído  
**Timeframes**: Daily + 1H + 30M  
**Output**: RSI, ADX, ADX Rising, +DI/-DI, Tríade, Tendência 1H, Tendência 30M, Score  
**Controle via Sliders**: ✅ Sim  
**Melhor uso**: Multi-timeframe completo com filtros rigorosos

**Características:**
- ADX Rising obrigatório
- +DI > -DI obrigatório
- Tríade completa obrigatória
- Filtros mais rigorosos (preço > EMA50)

---

### 5. 🌐 Scanner Swing Expandido (Mid + Small Caps)
**Status**: Evoluído  
**Timeframes**: Daily  
**Output**: RSI, ADX, ADX Rising, +DI/-DI, Tríade, Score  
**Controle via Sliders**: ✅ Sim  
**Melhor uso**: Varredura em Mid/Small Caps com volume relaxado

**Características:**
- Volume médio relaxado: ≥ R$ 2.5M (vs padrão)
- Usa ATIVOS_COMPLETO (Blue Chips + Mid/Small)
- Tríade completa

---

## Legacy Scanners (Comparação)

### 🔮 Legacy - Profissional (Final Corrigida)
**Status**: Legacy (hardcoded filters)  
**Timeframes**: Daily + 1H + 30M  
**Output**: RSI/ADX por TF, Score por TF, Score Total, Alinhamento  
**Controle via Sliders**: ❌ Não (filtros fixos)  
**Filtros fixos**: Vol>1.5x, EMA20/50, ADX>20, RSI 45-75  
**Melhor uso**: Comparação com evoluídos — referência de versão estável

**Características:**
- Score por timeframe (Daily, 1H, 30M) + Total
- Alinhamento multi-TF (✅ FORTE / ⚠️ PARCIAL)
- Indicadores numéricos completos por TF

---

### ⏰ Legacy - Intraday/Swing Curto Prazo
**Status**: Legacy (hardcoded filters)  
**Timeframes**: Daily + 1H + 30M  
**Output**: RSI/ADX por TF, Score por TF, Score Total, Alinhamento  
**Controle via Sliders**: ❌ Não (filtros fixos)  
**Filtros fixos**: Vol>1.7x, Liquidez>8M, ADX≥22, RSI 47-73  
**Score**: Ponderado (Daily×1.6 + 1H + 30M)  
**Melhor uso**: Filtros rigorosos para swing curto (1-3 dias)

---

### 🌐 Legacy - Expandida (Mid + Small Caps)
**Status**: Legacy (hardcoded filters)  
**Timeframes**: Daily + 1H + 30M  
**Output**: RSI/ADX/Confluência por TF, Score Diário, Tendência 1H/30M  
**Controle via Sliders**: ❌ Não (filtros fixos)  
**Filtros fixos**: Vol>1.5x, vol_medio≥2.5M, ADX>20, RSI 45-75  
**Melhor uso**: Small caps voláteis com análise de confluência detalhada

**Características:**
- Confluência por timeframe (Boa ✅ / Parcial / Fraca)
- Confluência Geral (Excelente ✅✅ / Boa ✅ / Parcial / Fraca)
- Tendência qualitativa (Alta forte / Alta moderada / Consolidação)

---

## Painel de Controle Global

### Controles Disponíveis

| Controle | Afeta | Uso |
|---|---|---|
| **Lista de ativos** (radio) | Todos os scanners | Seleciona universo: Blue Chips / Todos / Universal |
| **Volume Ratio Mínimo** (slider) | Fusion + Evoluídos | Ratio vol atual vs média 20 períodos (padrão: 1.6) |
| **ADX Mínimo** (slider) | Fusion + Evoluídos | Força mínima de tendência (padrão: 23) |
| **RSI Mínimo** (slider) | Fusion + Evoluídos | RSI mínimo para momentum de alta (padrão: 52) |
| **RSI Máximo** (slider) | Fusion + Evoluídos | RSI máximo antes de sobrecompra (padrão: 70) |
| **Atualizar Scanners** (botão) | Todos | Dispara recálculo de todos scanners |

### Controle de Cache

- **Dados de mercado**: TTL 300s (5 minutos) via `@st.cache_data(ttl=300)` em `baixar_dados()`
- **Botão "Atualizar"**: Limpa o cache do yfinance para forçar download de dados frescos

---

## Listas de Ativos

### Blue Chips (9 ativos)
`PETR4.SA, VALE3.SA, ITUB4.SA, PRIO3.SA, BBAS3.SA, B3SA3.SA, BBDC4.SA, BPAC11.SA, BOVA11.SA`

### Mid/Small Caps (15 ativos)
`RENT3.SA, LREN3.SA, MGLU3.SA, HAPV3.SA, EQTL3.SA, SBSP3.SA, TOTS3.SA, RAIL3.SA, CSNA3.SA, GGBR4.SA, PLPL3.SA, CURY3.SA, BMOB3.SA, TAEE11.SA, SEQL3.SA`

### Universal (B3 Ampliado)
**Total**: ~220+ ativos categorizados:
- Ações (~120): Bancos, Energia, Petróleo, Mineração, Varejo, Saúde, Imobiliário, Alimentos, Transportes, Tech, Industrial, Papel, Educação
- BDRs (~60): Tech, Finanças, Consumo, Saúde, Industrial
- ETFs (~20): Índices Brasil/Internacional, Temáticos, Renda Fixa
- FIIs (~30): Logísticos, Shopping, Lajes, Papel, Híbridos

---

## Arquitetura

### Dependências Principais

```
streamlit (UI)
pandas (data manipulation)
yfinance (dados de mercado)
pandas_ta (indicadores técnicos)
```

### Funções Core

```python
# Baixa dados do yfinance com cache
@st.cache_data(ttl=300)
baixar_dados(symbol, interval, period) → df

# Análise completa de um ativo (Daily)
analisar_ativo_completo(df, adx_min, rsi_min, rsi_max, vol_ratio_min) → dict

# Análise de tendência de TF auxiliar (1H/30M)
analisar_tendencia_tf(df) → "✅ Alta" / "⚠️ Neutra" / "❌ Baixa"
```

### Estrutura de Indicadores

**Por Timeframe:**
- EMAs: 9, 20, 50
- RSI: 14 períodos
- ADX/+DI/-DI: 14 períodos
- MACD: 12/26/9
- ATR: 14 períodos
- Volume Ratio: vol atual vs média 20

**Scores por Timeframe:**
- Daily max: 100
- 1H max: 100
- 30M max: 70 (normalizado para 100)

---

## Histórico de Evolução

### v1.0 - Scanners Evoluídos
- Implementação de scanners com Tríade (ADX + RSI + Volume)
- ADX Rising, +DI/-DI
- Controle via sliders (ADX, RSI, Volume)

### v1.5 - Painel Legado
- Adição de scanners Legacy para comparação
- Filtros hardcoded (Volume, ADX, RSI fixos)
- Multi-timeframe completo com scores por TF

### v2.0 - Swing Trade Fusion ⭐ (HERO SCANNER)
- Combina o melhor dos dois mundos: granularidade Legacy + recursos Evoluídos
- Score ponderado por TF (1H = principal)
- Confluência em 4 níveis
- Tríade multi-TF
- Stop/Alvos ATR-based
- Sinais de saída automáticos
- Expandido por padrão como scanner principal

### v2.1 - Interface Expandida
- Todos os painéis expandidos por padrão para máxima visibilidade
- Legenda e lista de ativos sempre visíveis
- Facilita cópia e análise

---

## Próximos Passos (Roadmap Futuro)

### Curto Prazo
- [ ] Otimizar cache de dados (prevenção de timeout em modo Universal)
- [ ] Adicionar alertas em tempo real (via WebSocket)
- [ ] Exportar resultados para CSV/Excel

### Médio Prazo
- [ ] Machine Learning para previsão de movimentos
- [ ] Backtesting visual de estratégias
- [ ] Sistema de notificações (Telegram/Email)

### Longo Prazo
- [ ] API REST para integração com bots de trading
- [ ] Versão mobile (PWA)
- [ ] Multi-mercado (Forex, Crypto)

---

## Performance

### Cache Strategy
- **yfinance dados**: 5 minutos TTL
- **Compartilhamento de cache**: Mesma (symbol, interval, period) reutilizada entre scanners
- **Botão Atualizar**: Limpa cache + redownload

### Tempos de Execução (estimados)
| Modo | Ativos | Tempo |
|---|---|---|
| Blue Chips | 9 | ~10-20s |
| Todos | 24 | ~30-60s |
| Universal | 220+ | ~5-15min |

---

## Troubleshooting

### Problema: Sem ativos encontrados
**Soluções:**
1. Reduzir `ADX Mínimo` (padrão 23 → 20)
2. Reduzir `Volume Ratio` (padrão 1.6 → 1.4)
3. Aumentar range `RSI` (52-70 → 48-75)

### Problema: Timeout em modo Universal
**Soluções:**
1. Usar cache (primeira run é lenta, seguintes rápidas)
2. Tentar horários fora do pico (antes de 10h ou depois de 17h)
3. Dividir em categorias (só Ações, só FIIs)

### Problema: Dados desatualizados
**Solução:**
- Clicar botão "🔄 Atualizar Scanners" para limpar cache e baixar dados frescos

---

## Licença e Contribuições

**Project**: Scanner Ações BR  
**Language**: Python 3.13  
**License**: Verificar arquivo LICENSE  

Para contribuir:
1. Fork do repositório
2. Criar branch feature/`seu-recurso`
3. Commit com mensagens claras
4. Push e abrir Pull Request

---

**Última atualização**: 2026-07-04  
**Versão**: 2.1
