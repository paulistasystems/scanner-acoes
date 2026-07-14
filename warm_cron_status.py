# -*- coding: utf-8 -*-
"""
warm_cron_status.py — Relatório "o warm_cron está em dia?".

Usado por GET /api/warm_cron_status (Flask). Espelha a lógica de
php/warm_cron_status.php (heartbeat JSON + SQLite fill_state + mtimes).

Sinais
------
1) Heartbeat: tmp/warm_cron_status.json (gravado por warm_cron.py)
2) SQLite: fill_state.last_filled_at (wall-clock do prewarm, não bars.ts)
3) mtimes: warm_cron.log / warm_cron.lock
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:  # pragma: no cover
    TZ = None  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = os.path.join(HERE, "tmp")
STATUS_PATH = os.path.join(TMP_DIR, "warm_cron_status.json")
LOG_PATH = os.path.join(TMP_DIR, "warm_cron.log")
LOCK_PATH = os.path.join(TMP_DIR, "warm_cron.lock")

EXPECTED_SCHEDULE = {
    "market": (
        "*/10 10-17 * * 1-5  cd /home/paulista/scanner && "
        ".../python warm_cron.py >> .../tmp/warm_cron.log 2>&1"
    ),
    "hourly": (
        "3 * * * *  cd /home/paulista/scanner && "
        ".../python warm_cron.py >> .../tmp/warm_cron.log 2>&1"
    ),
}


def _now() -> datetime:
    if TZ is not None:
        return datetime.now(TZ)
    return datetime.now().astimezone()


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        text = str(s).strip()
        # fromisoformat aceita offset; se naive, assume America/Sao_Paulo
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            if TZ is not None:
                dt = dt.replace(tzinfo=TZ)
            else:
                dt = dt.astimezone()
        elif TZ is not None:
            dt = dt.astimezone(TZ)
        return dt
    except Exception:
        return None


def _in_market_window(dt: datetime) -> bool:
    """Seg–sex 10:00–17:59 America/Sao_Paulo."""
    if dt.weekday() >= 5:
        return False
    hm = dt.hour * 100 + dt.minute
    return 1000 <= hm <= 1759


def _file_meta(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.isfile(path):
        return None
    try:
        st = os.stat(path)
        mtime = datetime.fromtimestamp(st.st_mtime, tz=TZ) if TZ else datetime.fromtimestamp(st.st_mtime).astimezone()
        age = int((_now() - mtime).total_seconds())
        return {
            "path": path,
            "exists": True,
            "bytes": st.st_size,
            "mtime": mtime.isoformat(timespec="seconds"),
            "age_s": age,
        }
    except OSError:
        return None


def _load_heartbeat() -> Optional[Dict[str, Any]]:
    if not os.path.isfile(STATUS_PATH):
        return None
    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _heartbeat_ref(hb: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[str]]:
    status = str(hb.get("last_status") or "")
    end = _parse_iso(hb.get("last_end"))
    start = _parse_iso(hb.get("last_start"))
    skip = _parse_iso(hb.get("last_skip"))
    if end is not None:
        return end, "end"
    if status == "running" and start is not None:
        return start, "start"
    if skip is not None:
        return skip, "skip"
    if start is not None:
        return start, "start"
    return None, None


def _floor_10min(dt: datetime) -> str:
    m = (dt.minute // 10) * 10
    return dt.strftime("%Y-%m-%d %H:") + f"{m:02d}"


def _sqlite_evidence() -> Dict[str, Any]:
    """Lê fill_state.last_filled_at e classifica padrão temporal."""
    import data_layer

    out: Dict[str, Any] = {
        "available": False,
        "db_path": getattr(data_layer, "_DB_PATH", None),
        "error": None,
    }
    try:
        db_path = getattr(data_layer, "_DB_PATH", None) or os.environ.get("SCANNER_DB") or os.path.join(HERE, "scanner.db")
        out["db_path"] = db_path

        df = data_layer.read_fill_state()
        if df is None or df.empty:
            out.update({
                "available": True,
                "fill_state_count": 0,
                "parsed_timestamps": 0,
                "last_filled_min": None,
                "last_filled_max": None,
                "fill_age_s": None,
                "db_verdict": "empty",
                "db_fresh": False,
                "pattern": "empty",
                "pattern_detail": "fill_state vazio.",
                "burst_ratio": None,
                "distinct_10min_slots": 0,
                "top_10min_slot": None,
                "top_10min_fills": 0,
                "top_slots": [],
                "top_hours": [],
                "by_interval": [],
                "note": (
                    "last_filled_at = wall-clock do prewarm (_set_fill_state), "
                    "NÃO o timestamp da candle (bars.ts)."
                ),
            })
            return out

        times: List[datetime] = []
        for raw in df["last_filled_at"].tolist():
            dt = _parse_iso(str(raw) if raw is not None else None)
            if dt is not None:
                times.append(dt)

        count = len(df)
        parsed = len(times)
        min_dt = min(times) if times else None
        max_dt = max(times) if times else None
        now = _now()
        fill_age_s = int((now - max_dt).total_seconds()) if max_dt else None

        slot_c: Counter = Counter()
        hour_c: Counter = Counter()
        for dt in times:
            slot_c[_floor_10min(dt)] += 1
            hour_c[dt.strftime("%Y-%m-%d %H:00")] += 1

        top_slot, top_slot_n = (None, 0)
        if slot_c:
            top_slot, top_slot_n = slot_c.most_common(1)[0]
        burst_ratio = round(top_slot_n / count, 3) if count and top_slot_n else None
        slot_count = len(slot_c)

        if count == 0:
            pattern, pattern_detail = "empty", "fill_state vazio."
        elif burst_ratio is not None and burst_ratio >= 0.5:
            pattern = "bulk_burst"
            pattern_detail = (
                f"{burst_ratio * 100:.0f}% dos fills no mesmo slot de 10 min "
                f"({top_slot}, n={top_slot_n}). Parece UMA corrida longa de prewarm, "
                f"não ticks a cada 10 min espalhados."
            )
        elif slot_count >= 4:
            pattern = "spread_multi_slot"
            pattern_detail = (
                f"{slot_count} slots de 10 min com fills — consistente com várias "
                f"execuções (cron ou manuais)."
            )
        else:
            pattern = "few_slots"
            pattern_detail = (
                f"Só {slot_count} slot(s) de 10 min com atividade — poucas corridas, "
                f"não um dia inteiro de cron a cada 10 min."
            )

        # max_age is decided by caller; compute both windows for consumers
        in_market = _in_market_window(now)
        max_age = 20 * 60 if in_market else 75 * 60
        db_fresh = fill_age_s is not None and fill_age_s <= max_age
        if count == 0:
            db_verdict = "empty"
        elif db_fresh:
            db_verdict = "fresh"
        else:
            db_verdict = "stale"

        by_iv = []
        for iv, g in df.groupby("interval"):
            iv_times = [_parse_iso(str(x)) for x in g["last_filled_at"].tolist()]
            iv_times = [t for t in iv_times if t is not None]
            by_iv.append({
                "interval": iv,
                "n": int(len(g)),
                "mn": min(iv_times).isoformat(timespec="seconds") if iv_times else None,
                "mx": max(iv_times).isoformat(timespec="seconds") if iv_times else None,
            })
        by_iv.sort(key=lambda r: str(r["interval"]))

        out.update({
            "available": True,
            "fill_state_count": count,
            "parsed_timestamps": parsed,
            "last_filled_min": min_dt.isoformat(timespec="seconds") if min_dt else None,
            "last_filled_max": max_dt.isoformat(timespec="seconds") if max_dt else None,
            "fill_age_s": fill_age_s,
            "db_verdict": db_verdict,
            "db_fresh": db_fresh,
            "pattern": pattern,
            "pattern_detail": pattern_detail,
            "burst_ratio": burst_ratio,
            "distinct_10min_slots": slot_count,
            "top_10min_slot": top_slot,
            "top_10min_fills": top_slot_n,
            "top_slots": [{"slot": k, "fills": v} for k, v in slot_c.most_common(8)],
            "top_hours": [{"hour": k, "fills": v} for k, v in hour_c.most_common(8)],
            "by_interval": by_iv,
            "note": (
                "last_filled_at = wall-clock do prewarm (_set_fill_state), "
                "NÃO o timestamp da candle (bars.ts)."
            ),
        })
        return out
    except Exception as e:
        out["error"] = repr(e)
        return out


def build_report() -> Tuple[Dict[str, Any], int]:
    """Monta o JSON de status e o HTTP code sugerido (200/503)."""
    now = _now()
    in_market = _in_market_window(now)
    max_age_s = 20 * 60 if in_market else 75 * 60

    heartbeat = _load_heartbeat()
    last_ref = None
    last_ref_kind = None
    age_s = None

    verdict = "never"
    verdict_detail = (
        "Nenhum heartbeat (tmp/warm_cron_status.json). "
        "Deploye warm_cron.py novo e rode o cron ao menos 1x."
    )

    if heartbeat:
        last_ref, last_ref_kind = _heartbeat_ref(heartbeat)
        if last_ref is not None:
            age_s = int((now - last_ref).total_seconds())
        st = str(heartbeat.get("last_status") or "")
        if st == "running" and age_s is not None and age_s < 2 * 3600:
            verdict = "running"
            verdict_detail = f"warm_cron em execução (idade {age_s}s)."
        elif st == "error":
            verdict = "error"
            verdict_detail = (
                "Última execução em erro: " + str(heartbeat.get("last_error") or "?")
            )
        elif age_s is None:
            verdict = "unknown"
            verdict_detail = "Heartbeat sem timestamp utilizável."
        elif age_s <= max_age_s:
            verdict = "ok"
            window = "pregão a cada 10 min" if in_market else "fora do pregão (horário)"
            verdict_detail = (
                f"Última atividade há {age_s}s (limite {max_age_s}s; janela {window})."
            )
        else:
            verdict = "late"
            verdict_detail = (
                f"ATRASADO: última atividade há {age_s}s (limite {max_age_s}s)."
            )

    sqlite = _sqlite_evidence()

    # Combined: processo (heartbeat) + escrita no DB (fill_state)
    if verdict in ("ok", "running"):
        combined = verdict
        combined_detail = "Heartbeat do warm_cron.py em dia."
        if sqlite.get("db_verdict") == "stale":
            combined_detail += (
                " (DB fill_state mais antigo que o heartbeat — possível run sem "
                "fills novos, normal se já filled.)"
            )
    elif sqlite.get("db_verdict") == "fresh":
        combined = "db_active_no_heartbeat"
        combined_detail = (
            "fill_state fresco no SQLite, mas sem heartbeat JSON. "
            "Algo escreveu o banco (prewarm/manual/versão antiga), mas não o "
            "warm_cron.py com status."
        )
        if sqlite.get("pattern") == "bulk_burst":
            combined_detail += " Padrão = bulk_burst (uma corrida), não cron contínuo."
    elif verdict == "never" and sqlite.get("db_verdict") == "stale":
        combined = "idle_or_dead"
        combined_detail = (
            "Sem heartbeat e fill_state velho — cron provavelmente não está rodando. "
            + str(sqlite.get("pattern_detail") or "")
        )
    elif verdict == "late":
        combined = "late"
        combined_detail = verdict_detail
    elif verdict == "error":
        combined = "error"
        combined_detail = verdict_detail
    else:
        combined = verdict
        combined_detail = verdict_detail

    payload: Dict[str, Any] = {
        "ok": verdict in ("ok", "running"),
        "verdict": verdict,
        "detail": verdict_detail,
        "combined": combined,
        "combined_detail": combined_detail,
        "now": now.isoformat(timespec="seconds"),
        "timezone": "America/Sao_Paulo",
        "in_market_window": in_market,
        "max_age_s": max_age_s,
        "last_ref": last_ref.isoformat(timespec="seconds") if last_ref else None,
        "last_ref_kind": last_ref_kind,
        "age_s": age_s,
        "expected_schedule": EXPECTED_SCHEDULE,
        "heartbeat": heartbeat,
        "sqlite": sqlite,
        "files": {
            "status": _file_meta(STATUS_PATH),
            "log": _file_meta(LOG_PATH),
            "lock": _file_meta(LOCK_PATH),
            "tmp_dir": TMP_DIR if os.path.isdir(TMP_DIR) else None,
        },
        "note": (
            "Prova de processo=heartbeat JSON. Prova de escrita="
            "fill_state.last_filled_at no SQLite. bars.ts é o horário da candle, "
            "não do job."
        ),
    }

    # HTTP: 503 se processo ausente/atrasado/erro; 200 se ok/running ou DB fresco sem heartbeat
    http = 200
    if verdict in ("late", "never", "error") and combined != "db_active_no_heartbeat":
        http = 503
    if combined == "db_active_no_heartbeat":
        http = 200

    return payload, http
