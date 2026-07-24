import os
import math
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

# Load env variables (FTP_HOST, SCANNER_CHART_URL, etc.). Path explicito: no Passenger
# o CWD pode nao ser o app root, e load_dotenv() padrao busca a partir do CWD — sem
# isto o .env (e SCANNER_CHART_URL) pode nao ser carregado no servidor.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import threading
import time as _time

import data_layer
import warming
import scanners_core
import warm_cron_status
from symbols_fallback import ATIVOS_B3_AMPLIADO

app = Flask(__name__, static_folder='static')

# Cache curto de resultados de /api/scan: evita que polls concorrentes (várias
# abas/tabs) re-executem o scan pesado sobre ~300 ativos × 4 timeframes e
# esgotem os workers do LSAPI (busy:8). TTL pequeno; invalidado por warm/refresh.
_SCAN_CACHE = {}  # key -> (timestamp, payload)
_SCAN_CACHE_TTL = 15  # segundos
_SCAN_CACHE_LOCK = threading.Lock()


def _scan_cache_key(scanner_id, args):
    parts = [scanner_id]
    for k in sorted(args.keys()):
        if k == "scanner":
            continue
        parts.append(f"{k}={args.get(k)}")
    return "&".join(parts)


def _scan_cache_get(key):
    with _SCAN_CACHE_LOCK:
        entry = _SCAN_CACHE.get(key)
        if not entry:
            return None
        ts, payload = entry
        if _time.time() - ts > _SCAN_CACHE_TTL:
            _SCAN_CACHE.pop(key, None)
            return None
        return payload


def _scan_cache_put(key, payload):
    with _SCAN_CACHE_LOCK:
        _SCAN_CACHE[key] = (_time.time(), payload)


def invalidate_scan_cache():
    with _SCAN_CACHE_LOCK:
        _SCAN_CACHE.clear()

# Map of available scanners
SCANNERS_REGISTRY = {
    "legacy_profissional": {
        "name": "Legacy Profissional",
        "func": scanners_core.legacy_profissional,
        "uses_profile": False
    },
    "legacy_intraday_swing": {
        "name": "Legacy Intraday Swing",
        "func": scanners_core.legacy_intraday_swing,
        "uses_profile": False
    },
    "legacy_expandida": {
        "name": "Legacy Expandida",
        "func": scanners_core.legacy_expandida,
        "uses_profile": False
    },
    "scanner_swing_hibrido": {
        "name": "Swing Híbrido",
        "func": scanners_core.scanner_swing_hibrido,
        "uses_profile": True
    },
    "scanner_swing_rr": {
        "name": "Swing Risk/Reward",
        "func": scanners_core.scanner_swing_rr,
        "uses_profile": True
    },
    "scanner_swing_profissional": {
        "name": "Swing Profissional",
        "func": scanners_core.scanner_swing_profissional,
        "uses_profile": True
    },
    "scanner_swing_expandido": {
        "name": "Swing Expandido",
        "func": scanners_core.scanner_swing_expandido,
        "uses_profile": True
    },
    "scanner_swing_trade_fusion": {
        "name": "Trade Fusion",
        "func": scanners_core.scanner_swing_trade_fusion,
        "uses_profile": True
    },
    "abertura_candidatos": {
        "name": "Abertura - Candidatos 15m",
        "func": scanners_core.coletar_candidatos,
        "uses_profile": False,
        "uses_symbols": True,
        "requires_symbols": True,
        "group": "intraday"
    },
    "abertura_confluencia": {
        "name": "Abertura - Confluência 15m/30m",
        "func": scanners_core.coletar_confluencia_15m_30m,
        "uses_profile": False,
        "uses_symbols": True,
        "requires_symbols": True,
        "group": "intraday"
    },
    "monitoramento_intraday": {
        "name": "Monitoramento Intraday",
        "func": scanners_core.monitoramento_intraday,
        "uses_profile": False,
        "uses_symbols": True,
        "requires_symbols": True,
        "group": "intraday"
    },
    "estrategia_b3_intraday": {
        "name": "Estratégia B3 (Segunda) - 1H+30M 10-13h",
        "func": scanners_core.estrategia_b3_intraday,
        "uses_profile": False,
        "uses_symbols": True,
        "group": "intraday"
    },
    "sinal_intraday_24jul": {
        "name": "24 de Julho Intraday — BOAC34 + A1MD34",
        "func": scanners_core.sinal_intraday_24jul,
        "uses_profile": False,
        "uses_symbols": False,
        "group": "intraday"
    },
    "monitorar_juho": {
        "name": "23/07 Intraday Juho — WEGE3 + VIVT3 + GGBR3 + PYPL34 + DIVO11",
        "func": scanners_core.monitorar_juho,
        "uses_profile": False,
        "uses_symbols": True,
        "group": "intraday"
    }
}

# --- Routes ---

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/day')
def intraday():
    return send_from_directory('static', 'intraday.html')

@app.route('/<path:path>')
def static_proxy(path):
    # Serve other static files
    return send_from_directory('static', path)

@app.route('/api/scanners')
def get_scanners():
    scanners = []
    for k, v in SCANNERS_REGISTRY.items():
        scanners.append({
            "id": k,
            "name": v["name"],
            "uses_profile": v["uses_profile"],
            "uses_symbols": v.get("uses_symbols", False),
            "requires_symbols": v.get("requires_symbols", False),
            "group": v.get("group", "swing")
        })
    return jsonify({"scanners": scanners})

def clean_nan(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    elif isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(x) for x in obj]
    return obj

@app.route('/api/scan')
def api_scan():
    scanner_id = request.args.get('scanner')
    exclude_failures = request.args.get('exclude_failures', 'false').lower() == 'true'

    if scanner_id not in SCANNERS_REGISTRY:
        return jsonify({"error": "Scanner not found"}), 400

    s = SCANNERS_REGISTRY[scanner_id]

    # Check if warm is running
    w_status = warming.status()
    if w_status["running"]:
        return jsonify({
            "warming": True,
            "warm_progress": w_status,
            "data_ready": data_layer.data_ready(exclude_failures=exclude_failures),
        })

    # Gate: não analisa se o universo × intervalos não está completo
    ready = data_layer.data_ready(exclude_failures=exclude_failures)
    if not ready.get("ready"):
        return jsonify({
            "not_ready": True,
            "warming": False,
            "data_ready": ready,
            "error": ready.get("message") or "Dados incompletos — rode o warm.",
        }), 503

    # Cache curto: polls concorrentes do mesmo scanner retornam o payload em
    # cache em vez de re-rodar o scan pesado (reduz hold-time de worker).
    cache_key = _scan_cache_key(scanner_id, request.args)
    cached = _scan_cache_get(cache_key)
    if cached is not None:
        return jsonify(cached)

    # Prepare args
    from symbols_fallback import ATIVOS_B3_AMPLIADO
    ativos = ATIVOS_B3_AMPLIADO

    custom_symbols_str = request.args.get('symbols', '').strip()
    if custom_symbols_str and s.get("uses_symbols"):
        # Se vier lista do frontend e o scanner aceitar, usamos essa lista ao inves da completa.
        # Format "PETR4.SA,VALE3.SA"
        custom_symbols = [x.strip() for x in custom_symbols_str.split(',') if x.strip()]
        if custom_symbols:
            ativos = custom_symbols
    elif s.get("requires_symbols"):
        # Scanners marcados como requires_symbols (ex: Monitoramento Intraday,
        # Abertura Candidatos/Confluência) não rodam contra a lista cheia do
        # mercado — exigem input explícito do usuário.
        payload = {"columns": [], "rows": [], "warming": False,
                   "requires_symbols": True}
        _scan_cache_put(cache_key, payload)
        return jsonify(payload)
    else:
        # Se o modo restrito foi acionado, remove os que tiverem qualquer falha pontual
        if exclude_failures and ready.get("ready"):
            df_fill = data_layer.read_fill_state()
            if not df_fill.empty:
                filled_set = set(zip(df_fill['symbol'], df_fill['interval']))
                intervals = data_layer.REQUIRED_INTERVALS
                ativos = [sym for sym in ativos if all((sym, iv) in filled_set for iv in intervals)]

    try:
        if s["uses_profile"]:
            adx_min = float(request.args.get('adx_min', 20))
            rsi_min = float(request.args.get('rsi_min', 45))
            rsi_max = float(request.args.get('rsi_max', 65))
            vol_ratio_min = float(request.args.get('vol_ratio_min', 1.5))
            vol_medio_min = float(request.args.get('vol_medio_min', 1_000_000))
            
            if scanner_id == "scanner_swing_expandido":
                df = s["func"](adx_min, rsi_min, rsi_max, vol_ratio_min, vol_medio_min, ativos)
            else:
                df = s["func"](ativos, adx_min, rsi_min, rsi_max, vol_ratio_min, vol_medio_min)
        else:
            if scanner_id == "abertura_candidatos":
                min_ratio = float(request.args.get('vol_ratio_min', 0.8))
                max_ratio = 100.0  # open-ended
                df = s["func"](ativos, min_ratio, max_ratio)
            elif scanner_id == "abertura_confluencia":
                min_ratio = float(request.args.get('vol_ratio_min', 0.8))
                df = s["func"](ativos, min_ratio)
            elif scanner_id == "monitoramento_intraday":
                df = s["func"](ativos)
            elif scanner_id == "estrategia_b3_intraday":
                # Combina a lista própria da estratégia com eventuais símbolos
                # extras informados no frontend (campo de ativos), evitando
                # duplicatas e preservando a ordem.
                if custom_symbols_str and s.get("uses_symbols"):
                    base = list(scanners_core.ESTRATEGIA_B3_SYMBOLS)
                    for sym in ativos:
                        if sym not in base:
                            base.append(sym)
                    df = s["func"](base)
                else:
                    df = s["func"](None)
            elif scanner_id == "sinal_intraday_24jul":
                risk_pct = float(request.args.get('risk_pct', 1.0))
                df = s["func"](risk_pct=risk_pct)
            elif scanner_id == "monitorar_juho":
                if custom_symbols_str and s.get("uses_symbols"):
                    base = list(scanners_core.JUHO_SYMBOLS)
                    for sym in ativos:
                        if sym not in base:
                            base.append(sym)
                    df = s["func"](base)
                else:
                    df = s["func"](scanners_core.JUHO_SYMBOLS)
            else:
                df = s["func"](ativos)
                
        if df is None or df.empty:
            payload = {"columns": [], "rows": [], "warming": False}
            _scan_cache_put(cache_key, payload)
            return jsonify(payload)
            
        columns = [{"key": str(c), "label": str(c)} for c in df.columns]
        rows = df.to_dict(orient='records')
        
        # Clean NaNs and Infs for JSON serialization
        rows = clean_nan(rows)
        
        payload = {"columns": columns, "rows": rows, "warming": False}
        _scan_cache_put(cache_key, payload)
        return jsonify(payload)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/api/status')
def api_status():
    exclude_failures = request.args.get('exclude_failures', 'false').lower() == 'true'
    w_status = warming.status()
    ready = data_layer.data_ready(exclude_failures=exclude_failures)

    # Calculate today's missing requirements to supersede the raw overall counts
    from symbols_fallback import ATIVOS_B3_AMPLIADO
    intervals = list(data_layer.REQUIRED_INTERVALS)

    now_brt = data_layer._now_brt()
    ativos_validos = list(ATIVOS_B3_AMPLIADO)

    missing_items = 0
    missing_items_list = []
    total_items = len(ativos_validos) * len(intervals)

    # If the gate is already ready, there's nothing missing
    if not ready.get("ready"):
        for sym in ativos_validos:
            for iv in intervals:
                if not data_layer._is_filled(sym, iv, now_brt):
                    missing_items += 1
                    if len(missing_items_list) < 10:
                        missing_items_list.append(f"{sym}({iv})")

    today_requirements = {
        "total_assets_to_scan_today": total_items,
        "amount_still_missing": missing_items,
        "amount_fresh": total_items - missing_items,
        "missing_items_list": missing_items_list
    }

    return jsonify({
        "summary": data_layer.db_summary(),
        "warming": w_status["running"],
        "warm_progress": w_status,
        "today_requirements": today_requirements,
        "data_ready": ready,
    })

@app.route('/api/probe')
def api_probe():
    """Diagnóstico do prewarm: dispara o aquecimento (caso não esteja rodando)
    e mostra EXATAMENTE o que AINDA FALTA baixar/atualizar para a sessão de hoje."""

    from symbols_fallback import ATIVOS_B3_AMPLIADO
    intervals = list(data_layer.REQUIRED_INTERVALS)

    # Inicia o warmup (worker roda em background) se não houver nenhum rodando.
    warm_started = warming.start_warm(ATIVOS_B3_AMPLIADO, intervals)

    w_status = warming.status()

    # Importamos data_layer e usamos a lógica exata de "dados frescos" para a sessão corrente.
    import data_layer
    data_layer._ensure_schema()
    now_brt = data_layer._now_brt()

    ativos_validos = list(ATIVOS_B3_AMPLIADO)

    # Levanta rapidamente todos as falhas que ocorreram nos fetches.
    df_fail = data_layer.list_failures()
    failed_map = {}
    if not df_fail.empty:
        for _, row in df_fail.iterrows():
            failed_map[(row['symbol'], row['interval'])] = row['last_error']

    items_to_fetch = []

    # Avaliamos usando o is_filled() oficial do prewarm.
    # O Python dirá extamente quem precisa ir para o Yahoo na data e hora atuais.
    for sym in ativos_validos:
        for iv in intervals:
            # Se for Falso, significa que está faltando (ou desatualizado pro horário).
            if not data_layer._is_filled(sym, iv, now_brt):
                # Se falhou numa tentativa recenete, puxa a mensagem do erro logada.
                err_msg = failed_map.get((sym, iv))

                info = {
                    "symbol": sym,
                    "interval": iv
                }
                if err_msg:
                    info["last_failed_error"] = str(err_msg)

                items_to_fetch.append(info)

    return jsonify({
        "status": {
            "background_worker_running": w_status["running"],
            "triggered_just_now": warm_started,
            "overall_progress_done": w_status["done"],
            "overall_progress_total": w_status["total"]
        },
        "today_requirements": {
            "total_assets_to_scan_today": len(ativos_validos) * len(intervals),
            "amount_still_missing": len(items_to_fetch)
        },
        "missing_items_to_fetch": items_to_fetch
    })

@app.route('/api/warm_cron_status')
def api_warm_cron_status():
    """Heartbeat do warm_cron.py + timestamps fill_state no SQLite.
    Mesmo payload conceitual do php/warm_cron_status.php (sem precisar de PHP).
    HTTP 200 = ok/running (ou DB fresco sem heartbeat); 503 = late/never/error.
    """
    payload, code = warm_cron_status.build_report()
    return jsonify(payload), code

@app.route('/api/warm', methods=['POST'])
def api_warm():
    req = request.get_json() or {}
    intervals_str = req.get('intervals', '1d,1h,30m,15m')
    intervals = [i.strip() for i in intervals_str.split(',') if i.strip()]
    ativos = ATIVOS_B3_AMPLIADO
    invalidate_scan_cache()
    started = warming.start_warm(ativos, intervals)
    return jsonify({"started": started, "status": warming.status()})

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    data_layer.invalidate()
    invalidate_scan_cache()
    return jsonify({"success": True})

@app.route('/api/retry_failures', methods=['POST'])
def api_retry_failures():
    count = data_layer.retry_failures()
    return jsonify({"success": True, "retried": count})

@app.route('/api/retry_symbol', methods=['POST'])
def api_retry_symbol():
    req = request.get_json() or {}
    sym = req.get('symbol', '')
    if not sym:
        return jsonify({"success": False, "error": "Nenhum símbolo informado"}), 400
    data_layer.retry_symbol(sym)
    return jsonify({"success": True})

@app.route('/api/bars')
def api_bars():
    symbol = request.args.get('symbol')
    interval = request.args.get('interval')
    if not symbol or not interval:
        return jsonify({"error": "Missing symbol or interval"}), 400
    df = data_layer.read_bars(symbol, interval)
    if df is None or df.empty:
        return jsonify([])
    # Only return last 50 for panel
    df = df.tail(50).copy()
    # convert datetime to string
    df['ts'] = df['ts'].astype(str)
    return jsonify(clean_nan(df.to_dict(orient='records')))

@app.route('/api/fill_state')
def api_fill_state():
    df = data_layer.read_fill_state()
    if df.empty: return jsonify([])
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/failures')
def api_failures():
    df = data_layer.list_failures()
    if df.empty: return jsonify([])
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/egress_diag')
def api_egress_diag():
    """Diagnóstico: confirma se o processo ativo enxerga SCANNER_CHART_URL e
    mede uma chamada do _fetch_chart_direct (egress PHP)."""
    import time as _t
    url = os.environ.get('SCANNER_CHART_URL', '')
    t0 = _t.time()
    df, err = data_layer._fetch_chart_direct('SLCE3.SA', '1d', '1y')
    dt = round(_t.time() - t0, 3)
    return jsonify({
        'SCANNER_CHART_URL': url or None,
        'fetch_rows': 0 if (df is None or df.empty) else len(df),
        'fetch_err': err,
        'elapsed_s': dt,
    })


if __name__ == '__main__':
    # Dev apenas: o Passenger importa `app` sem rodar o __main__, então isto só roda
    # localmente (python app.py / run_web.sh). Aquece o scanner.db no boot — além do
    # cron horário — para a UI já ter dados sem depender de um browser abrir a página.
    # Best-effort: se já houver um warm em execução (ex.: cron), start_warm retorna
    # False e segue. Depende do proxy PHP (subido pelo run_web.sh) para o egress.
    try:
        started = warming.start_warm(ATIVOS_B3_AMPLIADO, ['1d', '1h', '30m', '15m'])
        print(f"startup prewarm: {'iniciado' if started else 'já há um warm em execução'}")
    except Exception as e:
        print(f"startup prewarm falhou (não fatal): {e!r}")
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, use_reloader=False, port=port)

