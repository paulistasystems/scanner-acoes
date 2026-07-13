# -*- coding: utf-8 -*-
"""
warming.py — Worker de aquecimento (prewarm) em background.

Estado em disco (tabela warm_state), nao em memoria: o Phusion Passenger roda varios
processos, e cada um teria seu proprio _state em memoria — o que fazia o frontend
desistir do aquecimento ao pollar um processo "frio" (running=False) enquanto outro
aquecia. Com o estado no SQLite, todos os processos enxergam o mesmo running/done/total,
o claim eh atomico (so um processo aquece por vez), e um heartbeat detecta worker morto
(processo reciclado) para outro processo retomar.
"""
import threading
from datetime import datetime, timedelta

import data_layer

_WARM_STALE = data_layer.WARM_STALE_SECONDS


def _warm_worker(symbols, intervals):
    try:
        data_layer.prewarm(symbols, intervals, progress=_update_progress)
    except Exception as e:
        print(f"Erro no background warm_worker: {e}")
    finally:
        data_layer.release_warm(datetime.now(data_layer.B3_TZ).isoformat())


def _update_progress(done, total, symbol, ok):
    # Callback do prewarm: atualiza progresso + heartbeat no banco a cada item.
    data_layer.tick_warm(done, symbol)


def start_warm(symbols, intervals):
    """Inicia o aquecimento se nenhum outro processo estiver rodando (claim atomico).
    Retorna True se este chamador iniciou, False se ja ha um warm ativo/recente."""
    now = datetime.now(data_layer.B3_TZ)
    started_at = now.isoformat()
    cutoff = (now - timedelta(seconds=_WARM_STALE)).isoformat()
    total = len(symbols) * len(intervals)

    if not data_layer.claim_warm(total, started_at, cutoff):
        return False  # outro processo ja esta aquecendo (ou acabou de adquirir)

    t = threading.Thread(target=_warm_worker, args=(symbols, intervals), daemon=True)
    t.start()
    return True


def status():
    return data_layer.get_warm_state()
