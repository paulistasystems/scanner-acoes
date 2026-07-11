import os
import math
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

# Load env variables (for SUPABASE_URL, etc.)
load_dotenv()

# We set a separate DB for the web version if not specified, 
# to avoid conflicts with the Streamlit 3.13 version locally.
if not os.environ.get("SCANNER_DB"):
    os.environ["SCANNER_DB"] = "scanner_web.db"

import data_layer
import warming
import scanners_core
from symbols_fallback import ATIVOS_B3_AMPLIADO

app = Flask(__name__, static_folder='static')

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
        "uses_profile": False
    },
    "abertura_confluencia": {
        "name": "Abertura - Confluência 15m/30m",
        "func": scanners_core.coletar_confluencia_15m_30m,
        "uses_profile": False
    }
}

# --- Routes ---

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def static_proxy(path):
    # Serve other static files
    return send_from_directory('static', path)

@app.route('/api/scanners')
def get_scanners():
    scanners = []
    for k, v in SCANNERS_REGISTRY.items():
        scanners.append({"id": k, "name": v["name"], "uses_profile": v["uses_profile"]})
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
    if scanner_id not in SCANNERS_REGISTRY:
        return jsonify({"error": "Scanner not found"}), 400
        
    s = SCANNERS_REGISTRY[scanner_id]
    
    # Check if warm is running
    w_status = warming.status()
    if w_status["running"]:
        return jsonify({
            "warming": True,
            "warm_progress": w_status
        })

    # Prepare args
    ativos = ATIVOS_B3_AMPLIADO
    
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
            else:
                df = s["func"](ativos)
                
        if df is None or df.empty:
            return jsonify({"columns": [], "rows": [], "warming": False})
            
        columns = [{"key": str(c), "label": str(c)} for c in df.columns]
        rows = df.to_dict(orient='records')
        
        # Clean NaNs and Infs for JSON serialization
        rows = clean_nan(rows)
        
        return jsonify({"columns": columns, "rows": rows, "warming": False})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/api/status')
def api_status():
    w_status = warming.status()
    return jsonify({
        "summary": data_layer.db_summary(),
        "warming": w_status["running"],
        "warm_progress": w_status
    })

@app.route('/api/warm', methods=['POST'])
def api_warm():
    req = request.get_json() or {}
    intervals_str = req.get('intervals', '1d,1h,30m')
    intervals = [i.strip() for i in intervals_str.split(',') if i.strip()]
    ativos = ATIVOS_B3_AMPLIADO
    started = warming.start_warm(ativos, intervals)
    return jsonify({"started": started, "status": warming.status()})

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    data_layer.invalidate()
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, use_reloader=False, port=port)
