"""Test natijasini 2-botga (Ish topish boti) yuborish — retry mexanizmi bilan.

Oqim:
  1) Natija avval 1-bot DB'siga saqlanadi (sync_status='pending').
  2) Darhol yuborishga urinamiz. Muvaffaqiyatsiz bo'lsa yo'qolmaydi.
  3) Fon tsikli (run_sync_loop) 'pending' natijalarni qayta yuboradi.

Retry oralig'i: 1 daqiqa -> 5 -> 15 -> 60 daqiqa. Undan keyin 'failed'.

Idempotency: har bir yuborishda `result_key = "assignment_<id>"` yuboriladi.
Bir xil result_key ikki marta kelsa, 2-bot duplicate yaratmasligi kerak.
"""
import asyncio
import logging
from datetime import datetime, timedelta

import httpx

import config
import db

log = logging.getLogger("result_sync")

# Retry jadvali (daqiqalarda). Ro'yxat tugagach -> 'failed'.
RETRY_MINUTES = [1, 5, 15, 60]
MAX_ATTEMPTS = len(RETRY_MINUTES)

_LOOP_INTERVAL = 30  # sekund — pending natijalarni tekshirish oralig'i
_HTTP_TIMEOUT = 15


def _now() -> datetime:
    return datetime.now()


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _iso_utc(value) -> str:
    """DB dagi 'YYYY-MM-DD HH:MM:SS' ni ISO 8601 (UTC) ga aylantiradi."""
    if not value:
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return str(value)


def _build_payload(r) -> dict:
    percent = float(r["percent"])
    return {
        "result_key": f"assignment_{r['assignment_id']}",
        "assignment_id": r["assignment_id"],
        "candidate_id": r["candidate_id"],
        "telegram_id": r["telegram_id"],
        "vacancy_id": r["vacancy_id"],
        "test_id": r["test_id"],
        "external_application_id": r["external_application_id"],
        "total_questions": r["total"],
        "correct_answers": r["correct"],
        "wrong_answers": r["wrong"],
        # Canonical contract (2-bot bilan kelishilgan):
        #   score      — butun son (yaxlitlangan foiz),
        #   percentage — float, 1 kasr (masalan 66.7) — 2-bot float qabul qiladi.
        "score": int(round(percent)),
        "percentage": round(percent, 1),
        "status": "passed" if r["passed"] else "failed",
        "started_at": _iso_utc(r["started_at"]) if r["started_at"] else None,
        "completed_at": _iso_utc(r["completed_at"] or r["created_at"]),
    }


async def _post_result(payload: dict) -> bool:
    """2-bot API'ga POST qiladi. True = qabul qilindi (2xx)."""
    if not config.RECRUITMENT_API_URL:
        log.warning("RECRUITMENT_API_URL sozlanmagan — natija yuborilmaydi (pending qoladi).")
        return False

    url = f"{config.RECRUITMENT_API_URL}/api/v1/test-results"
    headers = {"Content-Type": "application/json"}
    if config.RECRUITMENT_API_SECRET:
        headers["Authorization"] = f"Bearer {config.RECRUITMENT_API_SECRET}"
        headers["X-API-Key"] = config.RECRUITMENT_API_SECRET

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except Exception as e:
        # Secret loglamaymiz — faqat xato turi.
        log.warning("2-botga ulanib bo'lmadi (assignment=%s): %s",
                    payload.get("assignment_id"), type(e).__name__)
        return False

    if 200 <= resp.status_code < 300:
        return True
    log.warning("2-bot natijani rad etdi (assignment=%s): HTTP %s",
                payload.get("assignment_id"), resp.status_code)
    return False


async def _handle_result(r) -> None:
    """Bitta natijani yuborishga urinadi va DB holatini yangilaydi."""
    result_id = r["id"]
    payload = _build_payload(r)
    ok = await _post_result(payload)
    if ok:
        await db.mark_result_synced(result_id)
        log.info("Natija 2-botga yuborildi: assignment=%s", r["assignment_id"])
        return

    attempts = (r["sync_attempts"] or 0) + 1
    if attempts >= MAX_ATTEMPTS:
        await db.schedule_result_retry(result_id, attempts, None, failed=True)
        log.error("Natija yuborilmadi (max urinish): assignment=%s", r["assignment_id"])
        return

    delay_min = RETRY_MINUTES[min(attempts, len(RETRY_MINUTES) - 1)]
    next_at = _fmt(_now() + timedelta(minutes=delay_min))
    await db.schedule_result_retry(result_id, attempts, next_at)
    log.info("Natija qayta yuboriladi %s daqiqadan keyin: assignment=%s",
             delay_min, r["assignment_id"])


async def send_result_now(result_id: int) -> None:
    """Test tugagach darhol chaqiriladi (fire-and-forget). Xatolar yutiladi —
    fon tsikli baribir qayta urinadi."""
    try:
        r = await db.get_result(result_id)
        if r and r["sync_status"] == "pending":
            await _handle_result(r)
    except Exception:
        log.exception("send_result_now xatosi (result_id=%s)", result_id)


async def run_sync_loop() -> None:
    """Fon tsikli: 'pending' va vaqti kelgan natijalarni qayta yuboradi."""
    log.info("Result-sync fon tsikli ishga tushdi (interval=%ss).", _LOOP_INTERVAL)
    while True:
        try:
            pending = await db.get_pending_sync_results()
            for r in pending:
                await _handle_result(r)
        except Exception:
            log.exception("Result-sync tsikl xatosi")
        await asyncio.sleep(_LOOP_INTERVAL)
