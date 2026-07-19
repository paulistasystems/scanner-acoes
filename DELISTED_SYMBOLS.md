# ❌ DELISTED/MISSING SYMBOLS - YAHOO FINANCE VERIFICATION

**Verification Date:** July 4, 2026  
**Method:** Yahoo Finance Search API + yfinance download testing  
**Total Symbols Verified:** 37 failed tickers from scanner logs  

---

## 📊 SUMMARY

- **✅ Symbol Changes Found:** 6 (updated in code)
- **❌ Confirmed Delisted/Missing:** 29 symbols
- **🔍 Verification Method:** Yahoo Finance search API + direct download testing

---

## 🆕 DELISTED 2026-07-07 (2 symbols)

Removidos do scanner após falhas consistentes de download no Yahoo Finance
(`empty/truncated response` em todas as tentativas e intervalos, com `fail_count`
9–10 e 3 tentativas cada). Fonte: `2026-07-07T15-40_export.csv`, export do log de
falhas da camada de dados SQLite (`data_layer.list_failures()`).

| Symbol | Categoria | Origem no scanner | Motivo |
|--------|-----------|-------------------|--------|
| `NEOE3.SA` | Ações — Energia Elétrica | `UNIV_ENERGIA` (scanner_interface_Streamlit.py + scanner_abertura.py) | Neoenergia — empty/truncated (30m, 1h, 1d) |
| `IRDM11.SA` | FII | `_FIIS_UNIVERSAL` / lista de FIIs (ambos os scanners) | FII Iridium — empty/truncated (30m, 1h) |

> **Nota:** a camada de dados trata `empty/truncated response` como o sintoma de
> oscilação/flicker do Yahoo (respostas limitadas/throttled), não necessariamente
> como delisting confirmado via search API. Estes 3 ativos falharam de forma
> persistente e foram retirados do universo como candidatos a blacklist.

---

## 🆕 RE-DELISTED 2026-07-19 (1 símbolo)

`RBRF11.SA` havia sido relistado em 2026-07-07, mas voltou a falhar de forma
persistente no `warm_cron` (log `tmp/warm_cron.log` de 2026-07-19):
`No price data found, symbol may be delisted (period=75d)` em todos os 4
intervalos. Confirmado delistado novamente — removido de
`symbols_fallback.py` e `php/symbols.json`.

| Symbol | Categoria | Motivo |
|--------|-----------|--------|
| `RBRF11.SA` | FII | No price data found / may be delisted (Yahoo) — 2026-07-19 |

---

## ✅ UPDATED SYMBOLS (6 symbols)

These symbols have been successfully updated in `scanner_interface_Streamlit.py`:

| Old Symbol | New Symbol | Company | Verification Status |
|------------|------------|---------|-------------------|
| `CPLE6.SA` | `CPLE3.SA` | Copel | ✅ Working (21 bars) |
| `MRFG3.SA` | `MBRF3.SA` | Marfrig | ✅ Working (21 bars) |
| `EMBR3.SA` | `EMBJ3.SA` | Embraer | ✅ Working (21 bars) |
| `JBSS3.SA` | `JBSS32.SA` | JBS | ✅ Working (21 bars) |
| `GUAR3.SA` | `RIAA3.SA` | Guararapes | ✅ Working (21 bars) |
| `BRFS3.SA` | `BRFT11.SA` | BRF | ✅ Working (22 bars) |

---

## ❌ CONFIRMED DELISTED/MISSING SYMBOLS (29 symbols)

### 🏢 BANKS & FINANCIAL SERVICES (2 symbols)

| Symbol | Company | Category | Notes |
|--------|---------|----------|-------|
| `BPAN4.SA` | Banco Pan | Banks | Known operational issues |
| `CIEL3.SA` | Cielo | Financial Services | Not found in Yahoo Finance |

---

### ✈️ AIRLINES (2 symbols)

| Symbol | Company | Category | Notes |
|--------|---------|----------|-------|
| `AZUL4.SA` | Azul Airlines | Airlines | Financial difficulties |
| `GOLL4.SA` | Gol Airlines | Airlines | **Judicial Recovery** |

---

### 🏭 INDUSTRIAL & ENERGY (8 symbols)

| Symbol | Company | Category | Notes |
|--------|---------|----------|-------|
| `ELET3.SA` | Elektro | Energy | Not found in Yahoo Finance |
| `ELET6.SA` | Eletrobras | Energy | Not found in Yahoo Finance |
| `AESB3.SA` | AES Sul | Energy | Not found in Yahoo Finance |
| `TRPL4.SA` | Paraná Trik | Energy | Not found in Yahoo Finance |
| `CCRO3.SA` | CCR | Logistics | Not found in Yahoo Finance |
| `STBP3.SA` | STBP | Industrial | Not found in Yahoo Finance |
| `SQIA3.SA` | Sinqia | Technology | Not found in Yahoo Finance |
| `GEOO41.SA` | Geo | Industrial | Not found in Yahoo Finance |

---

### 🛍️ RETAIL & CONSUMER GOODS (5 symbols)

| Symbol | Company | Category | Notes |
|--------|---------|----------|-------|
| `ARZZ3.SA` | Arezzo & Co | Retail | Not found in Yahoo Finance |
| `SOMA3.SA` | Soma | Retail | Not found in Yahoo Finance |
| `PETZ3.SA` | Petz | Retail | **Potential symbol change** (search returns AUAU3.SA) |
| `NTCO3.SA` | Nutriplant | Consumer | Not found in Yahoo Finance |
| `MRFG3.SA` | Marfrig | Food | **Updated to MBRF3.SA** |

---

### 🍔 FOOD & AGRICULTURE (2 symbols)

| Symbol | Company | Category | Notes |
|--------|---------|----------|-------|
| `JBSS3.SA` | JBS | Food | **Updated to JBSS32.SA** |
| `BRFS3.SA` | BRF | Food | **Updated to BRFT11.SA** |

---

### 📊 BDRs - BRAZILIAN DEPOSITARY RECEIPTS (10 symbols)

**All BDRs listed below are MISSING from Yahoo Finance:**

| Symbol | Underlying Asset | Type | Notes |
|--------|------------------|------|-------|
| `META34.SA` | Meta Platforms | Tech BDR | Not found |
| `P1LT34.SA` | Palantir | Tech BDR | Not found |
| `A1XP34.SA` | Adobe | Tech BDR | Not found |
| `COST34.SA` | Costco | Retail BDR | Not found |
| `INTC34.SA` | Intel | Tech BDR | Not found |
| `MAST34.SA` | Mastercard | Financial BDR | Not found |
| `C1RM34.SA` | Ciena | Tech BDR | Not found |
| `BOING34.SA` | Boeing | Industrial BDR | Not found |
| `S1NO34.SA` | Sony | Tech BDR | Not found |
| `A1MG34.SA` | Abbott Labs | Healthcare BDR | Not found |

---

### 💰 ETFs & FIIs (4 symbols)

| Symbol | Name | Type | Notes |
|--------|------|------|-------|
| `BCFF11.SA` | FII | Real Estate Fund | Not found in Yahoo Finance |
| `SHOT11.SA` | ETF | Tech/Thematic | Not found in Yahoo Finance |
| `MALL11.SA` | FII | Shopping Centers | Not found in Yahoo Finance |
| `EURP11.SA` | ETF | Europe Index | Not found in Yahoo Finance |

---

### 🛢️ OIL & GAS (1 symbol)

| Symbol | Company | Category | Notes |
|--------|---------|----------|-------|
| `RRRP3.SA` | 3R Petroleum | Oil & Gas | Not found in Yahoo Finance |

---

## 🔧 RECOMMENDED ACTIONS

### 1. IMMEDIATE UPDATES ✅ (COMPLETED)
- **Updated 6 symbols** in `scanner_interface_Streamlit.py` with confirmed working replacements

### 2. REMOVE DELISTED SYMBOLS (RECOMMENDED)
Remove these 31 symbols from the following lists in `scanner_interface_Streamlit.py`:

#### From `UNIV_BANCOS`:
- Remove: `BPAN4.SA`, `CIEL3.SA`

#### From `UNIV_ENERGIA`:
- Remove: `ELET3.SA`, `ELET6.SA`, `AESB3.SA`, `TRPL4.SA`

#### From `UNIV_PETROLEO`:
- Remove: `RRRP3.SA`

#### From `UNIV_VAREJO`:
- Remove: `ARZZ3.SA`, `SOMA3.SA`, `PETZ3.SA`

#### From `UNIV_ALIMENTOS`:
- Remove: `NTCO3.SA` (already updated MRFG3.SA → MBRF3.SA, JBSS3.SA → JBSS32.SA, BRFS3.SA → BRFT11.SA)

#### From `UNIV_TRANSPORTES`:
- Remove: `AZUL4.SA`, `GOLL4.SA`, `CCRO3.SA`, `STBP3.SA`

#### From `UNIV_TECH`:
- Remove: `SQIA3.SA`

#### From `BDR_TECH`:
- Remove: All 10 missing BDRs

#### From `BDR_FINANCAS`:
- Remove: `MAST34.SA`, `A1XP34.SA`

#### From `BDR_CONSUMO`:
- Remove: `COST34.SA`

#### From `BDR_SAUDE`:
- Remove: `A1MG34.SA`

#### From `BDR_INDUSTRIAL`:
- Remove: `BOING34.SA`, `GEOO41.SA`

#### From `ETFS_B3`:
- Remove: `SHOT11.SA`, `EURP11.SA`

#### From `FIIS_B3`:
- Remove: `BCFF11.SA`, `MALL11.SA`

### 3. VERIFICATION NEEDED
Some symbols may require additional verification:
- **PETZ3.SA** - Search returns `AUAU3.SA` and `AUAU3F.SA` - verify correct symbol with broker
- **NTCO3.SA** - Nutriplant, verify if still traded

---

## 📋 VERIFICATION METHODOLOGY

1. **Yahoo Finance Search API**: Used official Yahoo Finance search endpoint to verify symbol existence
2. **Direct Download Testing**: Tested download with 1-year period using yfinance library
3. **Cross-Reference**: Compared results across multiple search methods
4. **Symbol Change Detection**: Searched by company name to identify potential symbol changes

---

## 🔄 UPDATE HISTORY

- **2026-07-04**: Initial verification completed
- **2026-07-04**: Updated 6 symbols with confirmed working replacements
- **2026-07-04**: Documented 31 delisted/missing symbols
- **2026-07-07**: Removidos 3 símbolos com falhas persistentes de download (`NEOE3.SA`, `IRDM11.SA`, `RBRF11.SA`) a partir do export de falhas do data_layer
- **2026-07-07**: Relistados `IRBR3.SA` (UNIV_BANCOS) e `RBRF11.SA` (FIIS_B3 / `_FIIS_UNIVERSAL`) em ambos os scanners — download revalidado via yfinance (22 e 21 barras em 1d/1mo), tickers restabelecidos no Yahoo

---

## 📞 RESOURCES FOR FUTURE VERIFICATION

- **Yahoo Finance**: https://finance.yahoo.com/
- **B3 Official Site**: https://www.b3.com.br/
- **TradingView**: https://www.tradingview.com/
- **Broker Platforms**: Check your broker's symbol database

---

## ⚠️ IMPORTANT NOTES

1. **Delisted vs Symbol Changes**: Some symbols may not be delisted but have had their symbols changed by B3
2. **Yahoo Finance Coverage**: Yahoo Finance may not cover all Brazilian symbols, especially smaller BDRs and FIIs
3. **Alternative Data Sources**: Consider using multiple data sources for comprehensive coverage
4. **Regular Verification**: This list should be re-verified periodically as symbol changes occur

---

*This document was automatically generated as part of the symbol verification process for the Brazilian stock scanner.*