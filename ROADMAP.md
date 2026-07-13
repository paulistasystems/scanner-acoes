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

## 🗄️ Roadmap Futuro: Supabase — Gestão Dinâmica de Símbolos

> **Objetivo:** mover o **universo de ativos e o ciclo de vida (list/delist)** para fora das
> listas Python hardcoded e de `DELISTED_SYMBOLS.md`, usando o **Supabase (Postgres)** como
> única fonte de verdade — com **listagem/delistagem automatizada com base em testes de
> download** (a lógica que hoje é 100% manual).

> **✅ Status (2026-07-11) — Fase 0–3 implementadas em código.** Novos arquivos:
> `symbol_store.py` (leitura anon + escrita service_role + motor de regras K/D/M),
> `symbols_fallback.py` (universo único compartilhado, fim da duplicação entre scanners, +
> seed), `seed_symbols.py` e `supabase_schema.sql`. Ambos os scanners leem o universo do
> Supabase com fallback bundled; o painel de BD (`painel_bd.py`) ganhou seção Supabase só
> leitura; o painel 🧪 virou o job in-app (teste + probe HTTP `"No results for"` + regras
> automáticas + override manual). **Pendente (execução manual):** (1) rodar
> `supabase_schema.sql` no SQL Editor do Supabase; (2) preencher `SUPABASE_SERVICE_KEY` no
> `.env` (e `st.secrets` no Cloud); (3) rodar `venv313/bin/python seed_symbols.py`. A Fase 4
> (depreciar `_SIMBOLOS_DELISTADOS`/`DELISTED_SYMBOLS.md` como export) fica para depois do
> seed + validação em produção.

### 🔴 Problema atual

Hoje o universo é gerenciado em três lugares desconectados, todos manuais:

| Onde | O quê | Problema |
|---|---|---|
| `UNIV_*` / `ATIVOS_B3_AMPLIADO` em `scanner_interface_Streamlit.py` | Listas hardcoded (~220+ ativos) | Duplicado em `scanner_abertura.py`; divergem entre scanners |
| `_SIMBOLOS_DELISTADOS` (final do scanner) | Lista hardcoded de delistados | Mantida à mão a partir do `DELISTED_SYMBOLS.md` |
| `data_layer.fetch_failures` (`scanner.db`) | Falhas persistentes (`fail_count`) | Apenas **sintoma**; virar blacklist exige ação humana |
| `_testar_download_delistados()` (painel 🧪) | Re-testa delistados via `yf.download` | Só diagnóstico **somente leitura** — relistar é manual |

Consequências: o mesmo ativo aparece listado num scanner e delistado noutro; mudança de
ticker (ex.: `CPLE6`→`CPLE3`) exige editar código + doc à mão; e no **Streamlit Cloud**
(filesystem efêmero) o estado de delisting **não persiste** entre redeploys — cada container
parte do zero.

### ✅ Objetivo com Supabase

1. **Única fonte de verdade** para quais símbolos estão listados/delistados, remotos e
   persistentes — sobrevive a redeploys e é compartilhado por todos os containers/scanners.
2. **List/delist automático por teste**: um job roda os testes de download periódicos e o
   estado (`listed` / `watch` / `delisted`) transiciona por regras (N falhas → delist; M
   sucessos → relist), sem edição de código.
3. **Remoção das listas hardcoded** e do `DELISTED_SYMBOLS.md` como fontes ativas (passam a
   ser só fallback/seed inicial).
4. **Universe idêntico** entre `scanner_interface_Streamlit.py` e `scanner_abertura.py`
   (ambos leem do Supabase) — acaba a divergência.

> **Escopo:** apenas **metadados e ciclo de vida de símbolos**. A tabela de **barras**
> (OHLCV, ~35 MB) continua no SQLite local (`scanner.db`) — o volume e o padrão de acesso
> (leitura determinística por `(symbol, interval)`) não justificam migrar agora.

### 🧱 Schema proposto (Postgres / Supabase)

```sql
-- Catálogo de símbolos: fonte de verdade do universo
CREATE TABLE symbols (
    symbol          TEXT PRIMARY KEY,           -- ex.: 'PETR4.SA' (ticker Yahoo vigente)
    name            TEXT NOT NULL,              -- 'Petrobras'
    category        TEXT,                       -- 'Bancos', 'Energia', 'Petróleo', ...
    asset_type      TEXT,                       -- 'Ação' | 'BDR' | 'ETF' | 'FII'
    liquidity_tier  TEXT,                       -- 'blue_chip' | 'mid_small' | 'universal'
    status          TEXT NOT NULL DEFAULT 'listed',  -- 'listed' | 'watch' | 'delisted'
    prior_symbols   TEXT[] DEFAULT '{}',        -- histórico de tickers antigos (CPLE6, ...)
    listed_at       TIMESTAMPTZ,
    delisted_at     TIMESTAMPTZ,
    delist_reason   TEXT,
    notes           TEXT
);

-- Resultado de cada teste de download (auditoria + base das regras)
CREATE TABLE symbol_tests (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL REFERENCES symbols(symbol),
    tested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    interval    TEXT NOT NULL,                  -- '1d' | '1h' | '30m' | '15m'
    period      TEXT,                           -- '1mo', '3mo', ...
    bars        INTEGER,                        -- qtd de candles retornados
    ok          BOOLEAN NOT NULL,               -- True se veio dado usável
    error       TEXT                            -- ex.: 'empty/truncated response'
);
CREATE INDEX idx_symbol_tests_symbol_time ON symbol_tests(symbol, tested_at DESC);

-- Trilha de auditoria das transições de status (quem/quando/porquê)
CREATE TABLE symbol_status_log (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL REFERENCES symbols(symbol),
    from_status TEXT,
    to_status   TEXT NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason      TEXT,                           -- 'auto: 5 falhas consecutivas' | 'manual'
    source      TEXT                            -- 'rule-engine' | 'ui' | 'seed'
);
```

O scanner reconstrói o universo ativo com uma query simples:
`SELECT symbol FROM symbols WHERE status = 'listed'` (agrupado por `liquidity_tier` para
manter as opções de rádio Blue Chips / Todos / Universal).

### 🔄 Workflow de list/delist por teste

```
   ┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
   │  Job de teste   │────▶│  symbol_tests    │────▶│  Motor de regras │
   │ download + HTTP │     │  (insert linhas) │     │ (transições)     │
   └─────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                             │
                                       ┌─────────────────────▼──────────────────────┐
                                       │ symbols.status: listed ⇄ watch ⇄ delisted  │
                                       │ + symbol_status_log (auditoria)            │
                                       └─────────────────────┬──────────────────────┘
                                                             │ lê em runtime
                                                   ┌─────────▼─────────┐
                                                   │  Scanners (UI)    │
                                                   │ universo ativo    │
                                                   └───────────────────┘
```

**Regras de transição (sugestão, configurável):**
- `listed → watch`: K falhas consecutivas em qualquer intervalo (ex.: 3).
- `watch → delisted`: persiste falhando por D dias (ex.: 7) → sai do universo ativo.
- `delisted → listed`: M sucessos consecutivos no teste de re-ativação (relançamento /
  ticker restabelecido / fim de throttling) → volta automaticamente.

### 🔬 Detecção de delisting via HTTP API — string indicadora (configurável pelo usuário)

O teste atual é só **quantitativo** (`yf.download` → contou candles?), o que não separa
delisting real do throttling/`empty-truncated` transitório do Yahoo. A verificação original
do `DELISTED_SYMBOLS.md` já usava a **Search/Quote API do Yahoo** para distinguir os dois.

Na versão Supabase, o job de teste fará **também** uma chamada HTTP direta ao endpoint do
Yahoo (chart/quote/search) e procurará na resposta uma **string indicadora de delisting** —
o campo/valor que, quando presente, confirma que o símbolo saiu de pregão.

> **Essa string é digitada pelo usuário (prompt de texto no painel) e guardada no Supabase**,
> não hardcoded — assim a heurística evolui sem deploy quando o Yahoo muda o formato da
> resposta. Tabela de configuração (nova, parte do schema Supabase):

```sql
-- Strings indicadoras de delisting (informadas pelo usuário, persistidas no Supabase)
CREATE TABLE delist_indicators (
    id          SMALLSERIAL PRIMARY KEY,
    pattern     TEXT NOT NULL,        -- string/valor que sinaliza delisting no response
    field       TEXT,                 -- onde procurar: 'body' (bruto) | 'quoteType' | 'marketState' | ...
    is_regex    BOOLEAN DEFAULT FALSE,
    enabled     BOOLEAN DEFAULT TRUE,
    created_by  TEXT,                 -- 'ui' (digitado pelo usuário) | 'seed'
    created_at  TIMESTAMPTZ DEFAULT now(),
    notes       TEXT
);
```

**Fluxo:**
1. Usuário digita a string indicadora (+ campo opcional) no painel → `INSERT` em `delist_indicators`.
2. Job de teste: além do `yf.download`, faz `GET` no endpoint HTTP do Yahoo para o símbolo.
3. Casa o corpo/campo da resposta contra cada `pattern` ativo → achou = **sinal forte de
   delisting**, gravado em `symbol_tests` (nova coluna `delist_signal`).
4. Motor de regras (Fase 3) combina **sinal forte (HTTP) + falhas de download** → transiciona
   `listed → delisted` com `reason` documentado.

---

### 🛣️ Plano de migração (fases — sem quebrar call sites)

> Restrição dura: **preservar as assinaturas de `baixar_dados` / `baixar_dados_15m`**
> (~22 call sites) e o contrato do `data_layer` (SQLite continua como source-of-truth de
> **barras**). O Supabase afeta só a **camada de universo**.

- **Fase 0 — Setup & decisões**
  - [ ] Criar projeto Supabase; definir variáveis (`SUPABASE_URL`, `SUPABASE_KEY`) em
        `st.secrets` / env — **nunca commitar**.
  - [ ] Decidir **onde roda o job de teste**: GitHub Actions (cron) vs Supabase Edge
        Function vs botão in-app. Ver *Questões em aberto*.
  - [ ] Seed inicial: popular `symbols` a partir das `UNIV_*` atuais + `_SIMBOLOS_DELISTADOS`.

- **Fase 1 — Mirror somente leitura (sem mudança de comportamento)**
  - [ ] Novo módulo `symbol_store.py` com `load_universe() → {tier: [symbols]}` lendo do
        Supabase. Scanners passam a **ler** o universo de lá, com **fallback** para as listas
        hardcoded se o Supabase estiver indisponível.
  - [ ] Validar que universo retornado == universo hardcoded atual (paridade total).

- **Fase 2 — Write path (testes gravam, status ainda manual)**
  - [ ] Job de teste grava em `symbol_tests` (usando a mesma filosofia do `data_layer`:
        `empty/truncated` é sintoma, não delisting confirmado — respeitar retries/backoff).
  - [ ] Painel 🧪 atual passa a ler/escrever no Supabase em vez de `_SIMBOLOS_DELISTADOS`.
  - [ ] Job de teste também consulta a **HTTP API do Yahoo** e casa a resposta contra as
        strings indicadoras em `delist_indicators` (string digitada pelo usuário no painel).
  - [ ] Status (`listed`/`delisted`) ainda é alterado à mão via UI do Supabase.

- **Fase 3 — Transições automáticas**
  - [ ] Implementar o motor de regras (K/D/M) → `symbols.status` + `symbol_status_log`.
  - [ ] List/delist passam a ser automáticos, auditados, e refletidos no scanner no run
        seguinte.

- **Fase 4 — Deprecar fontes legadas**
  - [ ] Remover `UNIV_*` / `_SIMBOLOS_DELISTADOS` do código (viram apenas seed/fallback).
  - [ ] `DELISTED_SYMBOLS.md` passa a ser **export** gerado do Supabase, não fonte manual.

### ⚠️ Considerações e riscos

- **Streamlit Cloud (FS efêmero):** o Supabase é **remoto e persistente** — aqui está o
  maior ganho: o estado de delisting finalmente sobrevive a redeploys e é consistente entre
  containers (hoje cada um recomeça do zero e os dois scanners divergem).
- **Fallback offline:** se o Supabase estiver inacessível, degradar para o último universo
  em cache (`@st.cache_data`) ou à lista bundled — nunca quebrar o scan.
- **Rate limit do Yahoo:** o job de teste herdará o tratamento de `empty/truncated` já
  consolidado no `data_layer` (retries + failure log) — **não** tratar resposta vazia como
  delisting imediato.
- **Secrets:** `SUPABASE_URL`/`SUPABASE_KEY` via `st.secrets` (local + Cloud); row-level
  security no Postgres se a chave for exposta no client.
- **Custo:** Supabase free tier cobre folgadamente o volume (~300 símbolos, testes diários).

### ❓ Questões em aberto (decidir na Fase 0)

1. **Onde roda o job de teste?** GitHub Actions cron (simples, grátis), Supabase Edge
   Function (serverless, perto do dado) ou botão in-app (manual)?
2. **Limiares de auto-delisting:** valores de K (falhas → watch), D (dias → delist) e M
   (sucessos → relist)?
3. **Porta de aprovação humana:** relist 100% automático, ou exige um *gate* manual para
   voltar ao universo ativo?
4. **Mover as barras (OHLCV) também?** Por ora **não** (ficam no SQLite); reavaliar só se
   houver necessidade de histórico persistente multi-container.
5. **Taxonomia de categorias:** alinhar `category`/`asset_type` com o particionamento
   `UNIV_*` atual ou adotar classificação nova?
6. **Qual endpoint/string do Yahoo?** Definir o endpoint HTTP exato (chart vs quote vs
   search) e a string indicadora de delisting — é **domínio do usuário**: digitada no painel
   e persistida em `delist_indicators`, não hardcoded.

---

## 🔌 Egress PHP (Yahoo Chart API) — arquitetura adotada + investigação remota pendente

### Contexto (2026-07-12)
O `yfinance` falha no IP do servidor paulista.dev: o bootstrap cookie/crumb
(`fc.yahoo.com` → `query2.../v1/test/getcrumb`) recebe **401 "Invalid Crumb"**, então
`yf.download` devolve vazio para todos os tickers (`Expecting value: line 1 column 1`,
"symbol may be delisted"). O endpoint público **Chart API v8** (`/v8/finance/chart`)
**não exige crumb** e responde 200+dados só com User-Agent de browser — confirmado por
probe PHP que cobriu os **214/214 símbolos** do universo (0 delistados de verdade; o
`DELISTED_SYMBOLS.md` é não-confiável, gerado pelo yfinance quebrado).

### Solução adotada (validada localmente)
- **`php/yahoo_chart.php`** — proxy direto ao Chart API v8 (browser UA, sem crumb).
  Egress único, usado em local e remoto. `php/yahoo_probe.php` + `php/symbols.json`
  (gerado por `php/gen_symbols.py`) = diagnóstico de cobertura.
- **`data_layer._fetch_chart_direct`** — quando `SCANNER_CHART_URL` está setada, busca
  via esse proxy em vez de Yahoo direto. `run_web.sh` sobe `php -S` local (PHP 8.3) e
  exporta a URL; o `.env` local aponta para ele.
- **Local 100% funcional**: prewarm preencheu 1.214 barras via proxy, 0 falhas; leitura
  determinística; boot do scanner OK nos 4 intervalos.

### 🔴 Pendente — o warm **remoto** não progride (investigação futura)
Em produção o warm worker **trava**: `done` para de subir (ex.: 31/642 congelado em
`XBOV11.SA`), `stderr.log` sem crescer (nenhum erro novo de yfinance). A proxy em si
funciona — self-probe `https://paulista.dev/yahoo_chart.php` = 200 em ~0.6s.

**Hipótese forte:** o processo Passenger **não está lendo `SCANNER_CHART_URL`** porque
`app.py` chamava `load_dotenv()` sem path — o python-dotenv busca a partir do CWD, que no
Passenger pode não ser o app root → `.env` não carregado → `_fetch_chart_direct` cai no
Yahoo direto + fallback `yfinance` (lento/trava).

**Plano de investigação (executar via DirectAdmin):**
1. Confirmar o fix do `load_dotenv` no `app.py` (path explícito via `__file__`) — **já no
   working tree**.
2. Deploy via FTP de `app.py` + `data_layer.py` (egress + fix 30m) — `data_layer.py` já
   deployed; `app.py` com o fix + endpoint de diagnóstico precisa subir.
3. **Restart pelo DirectAdmin** (NÃO via FTP `tmp/restart.txt` — preferência do usuário).
4. Bater em `/api/egress_diag` (endpoint já adicionado): deve mostrar `SCANNER_CHART_URL`
   setada e `fetch_rows>0` em <2s. Se vier `null`, o `.env` ainda não está sendo lido.
5. Disparar `POST /api/warm` e confirmar `done/total` subindo rápido (~0.6s/item, ~6 min
   no total) — sinal de que o egress PHP está ativo.

### Por que o yfinance/Python falha no servidor (investigação separada, depois)
Confirmar se `requests` direto ao Yahoo, a partir do processo Python no servidor, se
comporta diferente do `curl` do PHP (mesmo IP, mesmo endpoint, mesmo UA). Se sim, isolar
TLS/UA/throttle. Fora de escopo agora — o egress PHP resolve o sintoma.

---

## Próximos Passos (Roadmap Futuro)

### Curto Prazo
- [ ] **[Supabase] Gestão dinâmica de símbolos** — ver seção dedicada acima (Fase 0 → 4)
- [x] Otimizar cache de dados (prevenção de timeout em modo Universal)

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
