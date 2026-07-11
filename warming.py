# -*- coding: utf-8 -*-
import threading
import time
from datetime import datetime
import data_layer

_state_lock = threading.Lock()
_state = {
    "running": False,
    "done": 0,
    "total": 0,
    "last_symbol": "",
    "intervals": [],
    "started_at": None,
    "finished_at": None
}

def _update_progress(done, total, symbol, ok):
    with _state_lock:
        _state["done"] = done
        _state["total"] = total
        _state["last_symbol"] = symbol

def _warm_worker(symbols, intervals):
    try:
        data_layer.prewarm(symbols, intervals, progress=_update_progress)
    except Exception as e:
        print(f"Erro no background warm_worker: {e}")
    finally:
        with _state_lock:
            _state["running"] = False
            _state["finished_at"] = datetime.now().isoformat()

def start_warm(symbols, intervals):
    with _state_lock:
        if _state["running"]:
            return False  # Already running
        
        _state["running"] = True
        _state["done"] = 0
        _state["total"] = len(symbols) * len(intervals)
        _state["last_symbol"] = ""
        _state["intervals"] = intervals
        _state["started_at"] = datetime.now().isoformat()
        _state["finished_at"] = None

    t = threading.Thread(target=_warm_worker, args=(symbols, intervals), daemon=True)
    t.start()
    return True

def status():
    with _state_lock:
        return dict(_state)
