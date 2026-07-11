import re
import ast

def extract_functions(filepath, func_names):
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    
    parsed = ast.parse(source)
    extracted = []
    
    for node in parsed.body:
        if isinstance(node, ast.FunctionDef) and node.name in func_names:
            # We use get_source_segment if available, but Python 3.9 ast module has get_source_segment
            # Let's extract by lines
            start = node.lineno - 1
            end = node.end_lineno
            
            # include decorators
            if node.decorator_list:
                start = node.decorator_list[0].lineno - 1
                
            code = "\n".join(source.splitlines()[start:end])
            extracted.append(code)
            
    return "\n\n".join(extracted)

if __name__ == '__main__':
    funcs_main = [
        'safe_float',
        'analisar_ativo_completo',
        'analisar_tendencia_tf',
        'legacy_profissional',
        'legacy_intraday_swing',
        'legacy_expandida',
        'scanner_swing_hibrido',
        'scanner_swing_rr',
        'scanner_swing_profissional',
        'scanner_swing_expandido',
        'scanner_swing_trade_fusion'
    ]
    
    funcs_abertura = [
        '_candle_por_hora',
        'coletar_candidatos',
        'classificar_perfil',
        '_e_vela_alta_forte',
        '_rvol_na_vela',
        '_tendencia_30m',
        'coletar_confluencia_15m_30m'
    ]
    
    out = []
    out.append("# -*- coding: utf-8 -*-")
    out.append('"""\nCore dos Scanners (sem streamlit, sem pandas_ta).\n"""\n')
    out.append("import pandas as pd")
    out.append("import numpy as np")
    out.append("import indicators as ta")
    out.append("import data_layer")
    out.append("from symbols_fallback import ATIVOS_B3_AMPLIADO")
    out.append("\nADX_RISING_PERIODS = 5\n")
    
    out.append("def baixar_dados(symbol, interval, period):")
    out.append("    return data_layer.get_bars(symbol, interval, period)")
    out.append("\ndef baixar_dados_15m(symbol):")
    out.append("    return data_layer.get_bars(symbol, '15m', '5d')")
    out.append("\ndef baixar_dados_30m(symbol):")
    out.append("    return data_layer.get_bars(symbol, '30m', '10d')")
    out.append("\ndef _prewarm_com_progresso(ativos, intervals, rotulo=''):")
    out.append("    pass  # Pre-warming é feito no background worker na versão web\n")
    
    out.append(extract_functions('scanner_interface_Streamlit.py', funcs_main))
    out.append("\n# === ABERTURA ===\n")
    out.append(extract_functions('scanner_abertura.py', funcs_abertura))
    
    with open('scanners_core.py', 'w', encoding='utf-8') as f:
        f.write("\n".join(out))
    
    print("scanners_core.py gerado com sucesso!")
