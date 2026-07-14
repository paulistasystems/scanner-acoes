#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
warm_cron.py — Aquecimento do scanner.db via cron (FORA do Passenger).

Por que este script existe
--------------------------
O aquecimento (`warming.py`) roda como uma **thread daemon** dentro do processo
Phusion Passenger. Neste hosting (LiteSpeed + Passenger + CageFS), o processo é
reciclado logo após a request HTTP terminar, e a thread é ceifada: o
`requests.get` do egress trava até o read-timeout (25s), registra a falha do
primeiro ativo e o processo morre antes de completar (o `finally: release_warm`
não chega a rodar). Sintoma observado em produção:

    warm_state: running=1, done=1, total=642, finished_at=None
    fetch_failures: ReadTimeout("paulista.dev:443 ... read timeout=25")
    bars=0  → scanners vazios

Este script resolve rodando o `prewarm` como **processo autônomo** agendado pelo
cron do DirectAdmin. Sem thread background, sem Passenger, sem freeze — o processo
do cron faz os fetches normalmente (como ocorre localmente e em /api/egress_diag).
O app web apenas LÊ o scanner.db compartilhado.

Heartbeat
---------
A cada execução grava `tmp/warm_cron_status.json` (start/end/skip/error). O PHP
`php/warm_cron_status.php` (deploy na raiz do domínio) lê esse arquivo e diz se
o cron está "em dia" — mais confiável do que tentar ler o crontab via web.

Idempotente
-----------
`data_layer.prewarm` só busca (symbol, interval) cujo `_is_filled` é falso para a
sessão atual; repetir o cron apenas completa o que falta (diário fica preenchido o
dia todo; intraday avança candle a candle durante o pregão). Seguro para rodar a
cada poucos minutos com `flock` contra sobreposição.

Uso
---
Cron do DirectAdmin (Python 3.9 do virtualenv do app, B3 10h-18h em dias úteis):

    */10 10-17 * * 1-5  cd /home/paulista/scanner && \\
        /home/paulista/virtualenv/scanner/3.9/bin/python warm_cron.py \\
        >> /home/paulista/scanner/tmp/warm_cron.log 2>&1

Hourly (horário cheio, qualquer dia — útil pós-fechamento/diário):

    3 * * * *  cd /home/paulista/scanner && \\
        /home/paulista/virtualenv/scanner/3.9/bin/python warm_cron.py \\
        >> /home/paulista/scanner/tmp/warm_cron.log 2>&1

Bootstrap manual (primeira carga, logo após deploy):

    cd /home/paulista/scanner && /home/paulista/virtualenv/scanner/3.9/bin/python warm_cron.py

O script adquire um lock exclusivo (fcntl, portável Linux/macOS): se uma execução
anterior ainda estiver rodando, a nova sai em silêncio — dispensa `flock` no shell.

Args opcionais: passe os intervalos para sobrescrever o default.
Ex.: `warm_cron.py 1d` faz só o diário (rápido, pós-fechamento).
"""
import errno
import json
import os
import sys
import time
from datetime import datetime

# CWD = diretório do script: garante que scanner.db e .env resolvem igual ao app,
# mesmo quando o cron roda a partir de $HOME.
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

_STATUS_PATH = os.path.join(HERE, "tmp", "warm_cron_status.json")
_LOCK_PATH = os.path.join(HERE, "tmp", "warm_cron.lock")
os.makedirs(os.path.dirname(_LOCK_PATH), exist_ok=True)


try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    _TZ = None  # fallback: relógio local do host


def _now_iso():
    if _TZ is not None:
        return datetime.now(_TZ).isoformat(timespec="seconds")
    return datetime.now().isoformat(timespec="seconds")


def _write_status(update):
    """Merge parcial no JSON de heartbeat (best-effort; nunca derruba o cron)."""
    try:
        prev = {}
        if os.path.isfile(_STATUS_PATH):
            with open(_STATUS_PATH, "r", encoding="utf-8") as fh:
                prev = json.load(fh) or {}
        prev.update(update)
        prev["updated_at"] = _now_iso()
        tmp = _STATUS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(prev, fh, ensure_ascii=False, indent=2, default=str)
            fh.write("\n")
        os.replace(tmp, _STATUS_PATH)
    except Exception as e:
        sys.stderr.write(f"[warm_cron] aviso: não gravou status ({e!r})\n")


# Lock exclusivo não-bloqueante: cron (especialmente o diário/intraday de 10 em
# 10 min) pode deflagrar uma execução antes da anterior terminar. fcntl funciona
# em Linux (servidor) e macOS (dev) — alternativas como o `flock` do shell não
# existem no macOS. O lock é liberado quando o processo encerra (FH fechado).
_lock_fh = open(_LOCK_PATH, "w")
try:
    import fcntl
    fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
except ImportError:
    pass  # plataforma sem fcntl (ex.: Windows) — segue sem lock
except OSError as e:
    if e.errno in (errno.EAGAIN, errno.EACCES):
        msg = (
            f"[{_now_iso()}] warm_cron: outra instância em execução "
            f"(lock ocupado), saindo."
        )
        print(msg, flush=True)
        _write_status({
            "last_skip": _now_iso(),
            "last_status": "skipped_lock",
            "last_message": "outra instância em execução (lock ocupado)",
            "pid": os.getpid(),
        })
        sys.exit(0)
    raise

# Carrega .env (SCANNER_CHART_URL etc.) ANTES de importar data_layer, que lê a env
# em tempo de uso. Mesmo padrão do app.py (path explícito — o CWD do cron vazio).
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(HERE, ".env"))
except Exception as e:
    # Se python-dotenv não estiver instalado, data_layer ainda funciona se a env
    # já vier populada (ex.: export no wrapper). Avisamos e seguimos.
    sys.stderr.write(f"[warm_cron] aviso: não carregou .env ({e!r}); usando env do shell\n")

import data_layer
from symbols_fallback import ATIVOS_B3_AMPLIADO

DEFAULT_INTERVALS = ["1d", "1h", "30m", "15m"]

# Frequência do log de progresso (a cada N itens processados).
_PROGRESS_EVERY = 25


def _progress(done, total, symbol, ok):
    # Sempre atualiza warm_state (UI /api/status) — barato, 1 UPDATE.
    try:
        data_layer.tick_warm(done, symbol)
    except Exception:
        pass
    if done == 1 or done % _PROGRESS_EVERY == 0 or done == total:
        flag = "ok" if ok else "FAIL"
        print(f"  [{done}/{total}] {symbol} ({flag})", flush=True)
        if done == 1 or done % _PROGRESS_EVERY == 0:
            _write_status({
                "last_status": "running",
                "progress_done": done,
                "progress_total": total,
                "progress_symbol": symbol,
            })


def main(argv):
    intervals = argv[1:] if len(argv) > 1 else DEFAULT_INTERVALS
    symbols = list(ATIVOS_B3_AMPLIADO)
    total = len(symbols) * len(intervals)

    t0 = time.time()
    started = _now_iso()
    _write_status({
        "last_start": started,
        "last_end": None,
        "last_status": "running",
        "last_exit_code": None,
        "last_error": None,
        "intervals": list(intervals),
        "symbols_count": len(symbols),
        "items_total": total,
        "progress_done": 0,
        "progress_total": total,
        "progress_symbol": "",
        "pid": os.getpid(),
        "cwd": HERE,
        "python": sys.executable,
    })
    # Espelha progresso no warm_state (poll do frontend /api/status).
    try:
        from datetime import timedelta
        now = data_layer._now_brt()
        cutoff = (now - timedelta(seconds=getattr(data_layer, "WARM_STALE_SECONDS", 90))).isoformat()
        data_layer.claim_warm(total, started, cutoff)
        data_layer.tick_warm(0, "")
    except Exception as e:
        sys.stderr.write(f"[warm_cron] aviso: claim_warm falhou ({e!r})\n")
    print(
        f"[{started}] warm_cron inicio: {len(symbols)} ativos x "
        f"{len(intervals)} intervalos ({intervals}) = {total} items",
        flush=True,
    )

    # prewarm é o passo de aquisição puro (sem claim/heartbeat do warming.py):
    # busca só o que _is_filled diz faltar, faz retry/backoff e registra falhas.
    failures = data_layer.prewarm(symbols, intervals, progress=_progress)

    elapsed = time.time() - t0
    s = data_layer.db_summary()
    ended = _now_iso()
    print(
        f"[{ended}] warm_cron fim: "
        f"{elapsed:.0f}s | barras={s['bars']} fill_state={s['fill_state']} "
        f"distinct_symbols={s['distinct_symbols']} failures={s['fetch_failures']}",
        flush=True,
    )
    if failures:
        print(
            f"  {len(failures)} (symbol, interval) falharam — ver painel "
            f"/api/failures no app.",
            flush=True,
        )
    _write_status({
        "last_end": ended,
        "last_status": "ok",
        "last_exit_code": 0,
        "elapsed_s": round(elapsed, 1),
        "failures_count": len(failures) if failures else 0,
        "summary": {
            "bars": s.get("bars"),
            "fill_state": s.get("fill_state"),
            "distinct_symbols": s.get("distinct_symbols"),
            "fetch_failures": s.get("fetch_failures"),
        },
        "progress_done": total,
        "progress_total": total,
    })
    try:
        data_layer.tick_warm(total, "")
        data_layer.release_warm(ended)
    except Exception as e:
        sys.stderr.write(f"[warm_cron] aviso: release_warm falhou ({e!r})\n")
    # Exit code: 0 mesmo com falhas individuais (são esperadas/registradas);
    # não-zero só em erro fatal do próprio script (exceção abaixo).
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as e:
        import traceback
        sys.stderr.write(f"[warm_cron] erro fatal: {e!r}\n")
        traceback.print_exc()
        ended = _now_iso()
        _write_status({
            "last_end": ended,
            "last_status": "error",
            "last_exit_code": 1,
            "last_error": repr(e),
        })
        try:
            data_layer.release_warm(ended)
        except Exception:
            pass
        sys.exit(1)
