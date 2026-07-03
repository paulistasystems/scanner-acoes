# Scanner de Ações - Mercado Brasileiro

Scanner consolidado para análise técnica de ações do mercado brasileiro, combinando estratégias de **scalping** e **swing trade** em um único script.

## 📋 Descrição

Este projeto consolida 6 scanners diferentes em um único script Python:

### Scanners de Scalping
| Modo | Timeframes | Foco |
|------|------------|------|
| `scalping` | 5m + 15m + 1H | Scalping profissional com VWAP e tendência |
| `scalping_fast` | 5m + 15m + 1m | Scalping rápido com timing de 1 minuto |

### Scanners de Swing Trade
| Modo | Timeframes | Foco |
|------|------------|------|
| `swing` | Daily + 1H + 30M | Swing híbrido com alinhamento multi-TF |
| `swing_rr` | Daily + 1H + 30M | Swing com níveis de RR (stop/alvos) |
| `swing_pro` | Daily + 1H + 30M | Swing profissional com pontuação completa |
| `swing_exp` | Daily + 1H + 30M | Swing expandido (Mid + Small caps) |

## 🚀 Instalação

```bash
cd ~/projects/scanner_acoes
pip install -r requirements.txt
```

## 🐍 Versão do Python (3.13)

O app Streamlit (`scanner_interface_Streamlit.py`) depende de `pandas_ta` → `numba`/`llvmlite`, o que restringe a versão do Python:

- `pandas_ta` (`0.4.71b0`) exige **Python >= 3.12**
- `numba` (`0.61.2`) exige **Python < 3.14** (não compila no 3.14)

➡️ Use **Python 3.13** (faixa viável: 3.12 ou 3.13).

- ❌ **3.11**: falha — `pandas_ta` precisa de `>=3.12`
- ❌ **3.14**: falha — `numba`/`llvmlite` não compilam
- ✅ **3.12 / 3.13**: instala e roda normalmente

**Streamlit Community Cloud:** painel do app → ⋮ → Settings → Advanced settings → **Python version: 3.13**.

**Local:** o arquivo `.python-version` marca a versão do projeto. Crie o ambiente com:

```bash
python3.13 -m venv venv313
source venv313/bin/activate
pip install -r requirements.txt
streamlit run scanner_interface_Streamlit.py
```

## 💻 Uso

### Executar com modo padrão (scalping):
```bash
python scanner_consolidado.py
```

### Executar modo específico:
```bash
python scanner_consolidado.py scalping      # Scalping profissional
python scanner_consolidado.py scalping_fast # Scalping rápido
python scanner_consolidado.py swing         # Swing híbrido
python scanner_consolidado.py swing_rr      # Swing com RR
python scanner_consolidado.py swing_pro     # Swing profissional
python scanner_consolidado.py swing_exp     # Swing expandido
```

### Executar todos os scanners:
```bash
python scanner_consolidado.py todos
```

## 📊 Ativos Monitorados

### Blue Chips
PETR4, VALE3, ITUB4, PRIO3, BBAS3, B3SA3, BBDC4, BPAC11, NVDC34, TSLA34, AAPL34, AMZO34, GOGL34, MSFT34, MELI34, ROXO34, IVVB11, NASD11, GOLD11, BOVA11

### Mid & Small Caps (scalping e swing_exp)
RENT3, LREN3, MGLU3, HAPV3, EQTL3, SBSP3, TOTS3, RAIL3, CSNA3, GGBR4, USIM5, ALPA4, TTEN3, POMO4, PLPL3, VULC3, IRBR3, EVEN3, DIRR3, CURY3, BMOB3, ALUP11, BRBI11, TAEE11, BRSR6, LEVE3, RANI3, SEQL3, TUPY3, CVCB3, GMAT3, GRND3, POMO3, CEAB3, VIVA3, PGMN3, SMFT3

## 🛠️ Tecnologias

- **yfinance** - Download de dados de mercado
- **pandas** - Manipulação de dados
- **pandas_ta** - Indicadores técnicos (EMA, RSI, MACD, ADX, ATR, VWAP)

## 📈 Indicadores Utilizados

- **EMA** (8, 9, 20, 21, 50) - Médias móveis exponenciais
- **RSI** (14) - Índice de força relativa
- **MACD** (12, 26, 9) - Convergência/divergência de médias móveis
- **ADX** (14) - Índice direcional médio (força da tendência)
- **ATR** (14) - True Range médio (volatilidade)
- **VWAP** - Preço médio ponderado por volume (scalping)

## ⚠️ Aviso

Este código é apenas para fins educacionais. Não constitui recomendação de investimento. Sempre faça sua própria análise e consulte um profissional qualificado antes de tomar decisões de investimento.
