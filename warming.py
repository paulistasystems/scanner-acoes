# -*- coding: utf-8 -*-
"""
warming.py — Dispara o aquecimento do scanner.db.

Produção (Phusion Passenger)
----------------------------
Uma **thread daemon** morre quando o Passenger recicla o processo após a request
HTTP — o warm trava no 1º ativo. Por isso `start_warm` lança `warm_cron.py` como
**subprocesso destacado** (`start_new_session=True`): sobrevive ao recycle, usa o
mesmo lock/fcntl + heartbeat JSON do cron, e grava progresso em `warm_state`
(para o frontend pollar `/api/status`).

Dev (`run_web.sh` / `python app.py`)
------------------------------------
Mesmo caminho (subprocess) — um único mecanismo em todos os ambientes.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime

import data_layer

HERE = os.path.dirname(os.path.abspath(__file__))
_WARM_SCRIPT = os.path.join(HERE, "warm_cron.py")
_WARM_LOG = os.path.join(HERE, "tmp", "warm_cron.log")


def status():
    return data_layer.get_warm_state()


def _already_running():
    """True se warm_state diz running (heartbeat fresco) ou se o lock do warm_cron
    está ocupado por outro processo."""
    st = data_layer.get_warm_state()
    if st.get("running"):
        return True
    lock_path = os.path.join(HERE, "tmp", "warm_cron.lock")
    if not os.path.isfile(lock_path):
        return False
    try:
        import fcntl
        import errno
        fh = open(lock_path, "a+")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fh, fcntl.LOCK_UN)
            return False  # conseguiu o lock → ninguém segurando
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EACCES):
                return True
            return False
        finally:
            fh.close()
    except Exception:
        return False


def start_warm(symbols, intervals):
    """Inicia warm_cron.py em background (processo autônomo).

    `symbols` é aceito por compatibilidade com a API antiga; o universo efetivo
    é o de `warm_cron.py` (ATIVOS_B3_AMPLIADO) — o mesmo do cron de produção.

    Retorna True se o subprocesso foi spawnado, False se já há warm ativo.
    """
    if _already_running():
        return False

    if not os.path.isfile(_WARM_SCRIPT):
        print(f"warming: script não encontrado: {_WARM_SCRIPT}")
        return False

    ivs = [str(i).strip() for i in (intervals or []) if str(i).strip()]
    if not ivs:
        ivs = ["1d", "1h", "30m", "15m"]

    os.makedirs(os.path.dirname(_WARM_LOG), exist_ok=True)
    # Append marker so o log mostre spawns da API vs cron do SO
    try:
        with open(_WARM_LOG, "a", encoding="utf-8") as lf:
            lf.write(
                f"\n--- API/spawn {datetime.now().isoformat(timespec='seconds')} "
                f"intervals={ivs} pid_parent={os.getpid()} ---\n"
            )
    except OSError as e:
        print(f"warming: não abriu log ({e!r})")

    env = os.environ.copy()
    # Garante CWD/paths iguais ao app (Passenger às vezes tem env enxuto)
    cmd = [sys.executable, _WARM_SCRIPT] + ivs

    try:
        # stdout/stderr → warm_cron.log; sessão nova → sobrevive ao recycle Passenger
        logf = open(_WARM_LOG, "a", encoding="utf-8")
        subprocess.Popen(
            cmd,
            cwd=HERE,
            stdout=logf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
            env=env,
        )
    except Exception as e:
        print(f"warming: falha ao spawnar warm_cron: {e!r}")
        return False

    return True
