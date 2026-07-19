# -*- coding: utf-8 -*-
"""
symbols_fallback.py — Fonte única (local, hardcoded) do universo de ativos da B3.

Centraliza as listas de tickers que ANTES viviam duplicadas em
`scanner_interface_Streamlit.py` (linhas 77-244) e `scanner_abertura.py` (linhas 14-45).
Ambos os scanners passam a importar daqui → acaba a divergência entre eles.

Também é o **fallback** do `symbol_store.load_universe()`: quando o Supabase está
indisponível (ou ainda não configurado), o scanner degrada graciosa e deterministicamente
para este universo bundled — o scan **nunca** quebra por falta de Supabase.

E ainda é a **seed** inicial do catálogo Supabase: `build_seed_catalog()` produz a lista de
{símbolo, nome, categoria, asset_type, status} para popular a tabela `symbols` uma única vez
(veja `seed_symbols.py`).

Módulo puro de dados: sem import de streamlit/pandas/yfinance — leve e sem efeito colateral.
"""

# ===================== AÇÕES — por setor =====================

# Bancos / Financeiras / Seguros
UNIV_BANCOS = [
    'ITUB4.SA', 'BBAS3.SA', 'BBDC4.SA', 'BBDC3.SA', 'SANB11.SA',
    'BPAC11.SA', 'ITSA4.SA', 'BBSE3.SA', 'PSSA3.SA', 'BRSR6.SA',
    'ABCB4.SA', 'BMGB4.SA', 'IRBR3.SA',
]

# Energia Elétrica
UNIV_ENERGIA = [
    'EQTL3.SA', 'CMIG4.SA', 'CPFE3.SA',
    'ENGI11.SA', 'CPLE3.SA', 'AURE3.SA', 'TAEE11.SA',
    'EGIE3.SA', 'COCE5.SA', 'ENEV3.SA',
    'CSMG3.SA', 'SBSP3.SA', 'SAPR11.SA',
]

# Petróleo / Gás / Distribuição
UNIV_PETROLEO = [
    'PETR4.SA', 'PETR3.SA', 'PRIO3.SA', 'CSAN3.SA', 'UGPA3.SA',
    'VBBR3.SA', 'RECV3.SA', 'RAIZ4.SA',
]

# Mineração / Siderurgia / Metalurgia
UNIV_MINERACAO = [
    'VALE3.SA', 'GGBR4.SA', 'GGBR3.SA', 'GOAU4.SA', 'USIM5.SA',
    'CSNA3.SA', 'CMIN3.SA', 'FESA4.SA', 'BRKM5.SA', 'UNIP6.SA',
]

# Varejo / Consumo
UNIV_VAREJO = [
    'LREN3.SA', 'MGLU3.SA', 'GRND3.SA', 'ALPA4.SA', 'CEAB3.SA',
    'RIAA3.SA', 'LJQQ3.SA', 'BHIA3.SA', 'AMAR3.SA', 'VULC3.SA',
]

# Saúde / Farmacêutica
UNIV_SAUDE = [
    'HAPV3.SA', 'RDOR3.SA', 'FLRY3.SA', 'HYPE3.SA', 'RADL3.SA',
    'ONCO3.SA', 'BLAU3.SA', 'AALR3.SA',
]

# Imobiliário / Construção
UNIV_IMOBILIARIO = [
    'MRVE3.SA', 'CYRE3.SA', 'EVEN3.SA', 'EZTC3.SA', 'DIRR3.SA',
    'TEND3.SA', 'LAVV3.SA', 'TRIS3.SA', 'MDNE3.SA', 'CURY3.SA',
    'PLPL3.SA', 'MELK3.SA', 'MTRE3.SA', 'GFSA3.SA',
]

# Alimentos / Agro / Bebidas
UNIV_ALIMENTOS = [
    'ABEV3.SA', 'JBSS32.SA', 'BRFT11.SA', 'MBRF3.SA', 'BEEF3.SA',
    'MDIA3.SA', 'SMTO3.SA', 'SLCE3.SA', 'AGRO3.SA', 'CAML3.SA',
    'JALL3.SA',
]

# Transportes / Logística / Aéreas
UNIV_TRANSPORTES = [
    'ECOR3.SA', 'EMBJ3.SA',
    'RAIL3.SA', 'TGMA3.SA', 'HBSA3.SA', 'LOGN3.SA',
]

# Telecom / Tecnologia
UNIV_TECH = [
    'VIVT3.SA', 'TIMS3.SA', 'TOTS3.SA', 'LWSA3.SA', 'POSI3.SA',
    'INTB3.SA', 'CASH3.SA', 'BMOB3.SA', 'MLAS3.SA',
    'DESK3.SA', 'SEQL3.SA',
]

# Industrial / Bens de Capital
UNIV_INDUSTRIAL = [
    'WEGE3.SA', 'B3SA3.SA', 'RENT3.SA', 'VAMO3.SA', 'SIMH3.SA',
    'KEPL3.SA', 'TUPY3.SA', 'POMO4.SA', 'RAPT4.SA', 'LEVE3.SA',
    'MILS3.SA', 'WIZC3.SA', 'MULT3.SA', 'IGTI11.SA',
]

# Papel / Celulose
UNIV_PAPEL = [
    'KLBN11.SA', 'SUZB3.SA', 'DXCO3.SA',
]

# Educação
UNIV_EDUCACAO = [
    'COGN3.SA', 'YDUQ3.SA', 'ANIM3.SA', 'SEER3.SA',
]

# ===================== BDRs (Brazilian Depositary Receipts) =====================

# Tecnologia
BDR_TECH = [
    'AAPL34.SA', 'MSFT34.SA', 'AMZO34.SA', 'GOGL34.SA', 'NVDC34.SA',
    'TSLA34.SA', 'NFLX34.SA', 'ADBE34.SA', 'ORCL34.SA',
    'CSCO34.SA', 'AVGO34.SA', 'QCOM34.SA', 'A1MD34.SA',
    'PYPL34.SA', 'U1BE34.SA', 'S1PO34.SA',
]

# Finanças
BDR_FINANCAS = [
    'JPMC34.SA', 'BOAC34.SA', 'GSGI34.SA', 'MSBR34.SA', 'BERK34.SA',
    'VISA34.SA',
]

# Consumo / Varejo
BDR_CONSUMO = [
    'COCA34.SA', 'PEPB34.SA', 'MCDC34.SA', 'NIKE34.SA', 'SBUB34.SA',
    'PGCO34.SA', 'WALM34.SA', 'HOME34.SA', 'DISB34.SA',
]

# Saúde / Farma
BDR_SAUDE = [
    'JNJB34.SA', 'PFIZ34.SA', 'MRCK34.SA', 'ABBV34.SA', 'LILY34.SA',
]

# Industrial / Energia / Outros
BDR_INDUSTRIAL = [
    'CATP34.SA', 'HONB34.SA', 'MMMC34.SA',
    'EXXO34.SA', 'CHVX34.SA', 'DHER34.SA',
]

# ===================== ETFs =====================
ETFS_B3 = [
    # Índices Brasil
    'BOVA11.SA', 'BOVV11.SA', 'SMAL11.SA', 'XBOV11.SA', 'DIVO11.SA',
    'MATB11.SA', 'FIND11.SA', 'GOVE11.SA', 'PIBB11.SA',
    # Índices Internacionais
    'IVVB11.SA', 'SPXI11.SA', 'NASD11.SA',
    # Temáticos / Setoriais
    'HASH11.SA', 'QBTC11.SA', 'ETHE11.SA', 'GOLD11.SA',
    'TECK11.SA', 'JURO11.SA',
    # Renda Fixa
    'IMAB11.SA', 'IRFM11.SA', 'B5P211.SA', 'FIXA11.SA',
]

# ===================== FIIs (Fundos Imobiliários) =====================
FIIS_B3 = [
    # Logístico
    'HGLG11.SA', 'BTLG11.SA', 'XPLG11.SA', 'VILG11.SA', 'BRCO11.SA',
    # Shopping / Varejo
    'XPML11.SA', 'VISC11.SA', 'HSML11.SA',
    # Lajes Corporativas
    'KNRI11.SA', 'PVBI11.SA', 'JSRE11.SA', 'BRCR11.SA', 'RCRB11.SA',
    # Papel (CRI / CRA)
    'MXRF11.SA', 'CPTS11.SA', 'RBRR11.SA', 'RECR11.SA',
    'VGIP11.SA', 'KNCR11.SA', 'HGCR11.SA',
    # Híbridos / Diversificados
    'HGBS11.SA', 'ALZR11.SA', 'TRXF11.SA', 'TGAR11.SA',
]

# ===================== LISTA MASTER COMBINADA =====================
_ACOES_UNIVERSAL = (
    UNIV_BANCOS + UNIV_ENERGIA + UNIV_PETROLEO + UNIV_MINERACAO +
    UNIV_VAREJO + UNIV_SAUDE + UNIV_IMOBILIARIO + UNIV_ALIMENTOS +
    UNIV_TRANSPORTES + UNIV_TECH + UNIV_INDUSTRIAL + UNIV_PAPEL + UNIV_EDUCACAO
)
_BDRS_UNIVERSAL = BDR_TECH + BDR_FINANCAS + BDR_CONSUMO + BDR_SAUDE + BDR_INDUSTRIAL
_ETFS_UNIVERSAL = ETFS_B3
_FIIS_UNIVERSAL = FIIS_B3

# Universo ativo deduplicado ( Blue Chips + Mid/Small + BDRs + ETFs + FIIs).
# Este é o fallback do symbol_store quando o Supabase está indisponível.
ATIVOS_B3_AMPLIADO = list(set(
    _ACOES_UNIVERSAL + _BDRS_UNIVERSAL + _ETFS_UNIVERSAL + _FIIS_UNIVERSAL
))

# Contadores por categoria (para exibição na interface)
CONTAGEM_CATEGORIAS = {
    'Ações': len(set(_ACOES_UNIVERSAL)),
    'BDRs': len(set(_BDRS_UNIVERSAL)),
    'ETFs': len(set(_ETFS_UNIVERSAL)),
    'FIIs': len(set(_FIIS_UNIVERSAL)),
}

# ===================== SÍMBOLOS DELISTADOS (seed/fallback) =====================
# (symbol, nome, categoria) — fonte histórica: DELISTED_SYMBOLS.md.
# Hoje só alimentam o diagnóstico 🧪; no Supabase viram status='delisted'.
# Não há overlap com o universo ativo acima (verificado).
_SIMBOLOS_DELISTADOS = [
    # 2026-07-07 — falha persistente de download (empty/truncated)
    ("NEOE3.SA",  "Neoenergia",      "Ações — Energia"),
    ("IRDM11.SA", "FII Iridium",     "FII"),
    # Confirmados delistados/ausentes no Yahoo (verificação 2026-07-04)
    ("BPAN4.SA",  "Banco Pan",       "Bancos"),
    ("CIEL3.SA",  "Cielo",           "Serviços Financeiros"),
    ("AZUL4.SA",  "Azul",            "Aéreas"),
    ("GOLL4.SA",  "Gol",             "Aéreas"),
    ("ELET3.SA",  "Elektro",         "Energia"),
    ("ELET6.SA",  "Eletrobras",      "Energia"),
    ("AESB3.SA",  "AES Sul",         "Energia"),
    ("TRPL4.SA",  "Transmissão",     "Energia"),
    ("CCRO3.SA",  "CCR",             "Logística"),
    ("STBP3.SA",  "Wilson Sons",     "Industrial"),
    ("SQIA3.SA",  "Sinqia",          "Tecnologia"),
    ("GEOO41.SA", "Geo",             "Industrial"),
    ("ARZZ3.SA",  "Arezzo",          "Varejo"),
    ("SOMA3.SA",  "Grupo Soma",      "Varejo"),
    ("PETZ3.SA",  "Petz",            "Varejo"),
    ("NTCO3.SA",  "Natura &Co",      "Consumo"),
    ("META34.SA", "Meta",            "BDR Tech"),
    ("P1LT34.SA", "Palantir",        "BDR Tech"),
    ("A1XP34.SA", "Adobe",           "BDR Tech"),
    ("COST34.SA", "Costco",          "BDR Consumo"),
    ("INTC34.SA", "Intel",           "BDR Tech"),
    ("MAST34.SA", "Mastercard",      "BDR Finanças"),
    ("C1RM34.SA", "Ciena",           "BDR Tech"),
    ("BOING34.SA","Boeing",          "BDR Industrial"),
    ("S1NO34.SA", "Sony",            "BDR Tech"),
    ("A1MG34.SA", "Abbott",          "BDR Saúde"),
    ("BCFF11.SA", "FII BC FF",       "FII"),
    ("SHOT11.SA", "ETF SHOT",        "ETF"),
    ("MALL11.SA", "FII MALL",        "FII"),
    ("EURP11.SA", "ETF Europa",      "ETF"),
    ("RRRP3.SA",  "3R Petroleum",    "Petróleo"),
]

# ===================== Catálogo de seed (Supabase) =====================
# Mapeia cada lista para (categoria, asset_type) — base para popular `symbols`.
_STOCK_GROUPS = [
    (UNIV_BANCOS,      "Bancos",       "Ação"),
    (UNIV_ENERGIA,     "Energia",      "Ação"),
    (UNIV_PETROLEO,    "Petróleo",     "Ação"),
    (UNIV_MINERACAO,   "Mineração",    "Ação"),
    (UNIV_VAREJO,      "Varejo",       "Ação"),
    (UNIV_SAUDE,       "Saúde",        "Ação"),
    (UNIV_IMOBILIARIO, "Imobiliário",  "Ação"),
    (UNIV_ALIMENTOS,   "Alimentos",    "Ação"),
    (UNIV_TRANSPORTES, "Transportes",  "Ação"),
    (UNIV_TECH,        "Tecnologia",   "Ação"),
    (UNIV_INDUSTRIAL,  "Industrial",   "Ação"),
    (UNIV_PAPEL,       "Papel",        "Ação"),
    (UNIV_EDUCACAO,    "Educação",     "Ação"),
]
_BDR_GROUPS = [
    (BDR_TECH,       "BDR Tech",       "BDR"),
    (BDR_FINANCAS,   "BDR Finanças",   "BDR"),
    (BDR_CONSUMO,    "BDR Consumo",    "BDR"),
    (BDR_SAUDE,      "BDR Saúde",      "BDR"),
    (BDR_INDUSTRIAL, "BDR Industrial", "BDR"),
]

# Nome curto quando não há nome curado (fallback = ticker sem .SA).
NAME_MAP = {s: n for s, n, _c in _SIMBOLOS_DELISTADOS}


def _asset_type_for(category):
    """Infere asset_type a partir do texto de categoria (usado só p/ delistados)."""
    if not category:
        return "Ação"
    c = category.upper()
    if "BDR" in c:
        return "BDR"
    if "FII" in c:
        return "FII"
    if "ETF" in c:
        return "ETF"
    return "Ação"


def build_seed_catalog():
    """Lista de dicts {symbol, name, category, asset_type, status} prontos para upsert
    na tabela `symbols` do Supabase. Universo ativo = 'listed'; delistados = 'delisted'."""
    catalog = {}  # symbol -> dict (dedup; primeira ocorrência vence a categoria)

    def add(sym, category, asset_type):
        catalog.setdefault(sym, {
            "symbol": sym,
            "name": NAME_MAP.get(sym, sym.replace(".SA", "")),
            "category": category,
            "asset_type": asset_type,
            "status": "listed",
        })

    for lst, cat, at in _STOCK_GROUPS:
        for s in lst:
            add(s, cat, at)
    for lst, cat, at in _BDR_GROUPS:
        for s in lst:
            add(s, cat, at)
    for s in ETFS_B3:
        add(s, "ETF", "ETF")
    for s in FIIS_B3:
        add(s, "FII", "FII")

    # Delistados: sem overlap com o universo ativo → entram com a categoria curada.
    for sym, name, cat in _SIMBOLOS_DELISTADOS:
        catalog[sym] = {
            "symbol": sym,
            "name": name,
            "category": cat or NAME_MAP.get(sym, sym.replace(".SA", "")),
            "asset_type": _asset_type_for(cat),
            "status": "delisted",
        }

    return list(catalog.values())


if __name__ == "__main__":  # diagnóstico rápido: imprime contagens
    cat = build_seed_catalog()
    from collections import Counter
    by_status = Counter(r["status"] for r in cat)
    by_type = Counter(r["asset_type"] for r in cat)
    print(f"total seed: {len(cat)}  |  ATIVOS_B3_AMPLIADO: {len(ATIVOS_B3_AMPLIADO)}")
    print("por status:", dict(by_status))
    print("por asset_type:", dict(by_type))
