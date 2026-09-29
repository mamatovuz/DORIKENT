"""DoriKent E2E yordamchisi — real cross-service test uchun.

Ikki rejim:

  serve   — real FastAPI API serverini ishga tushiradi (bitta seed test bilan).
            2-bot shu serverga real HTTP orqali ulanadi.

  complete <assignment_id> <correct> <total>
          — nomzod testni tugatganini simulyatsiya qiladi: DoriKent'ning REAL
            kodi bilan (save_recruitment_result + result_sync) natijani hisoblab,
            2-bot result API'ga REAL HTTP POST qiladi.

Muhit o'zgaruvchilari (subprocess env orqali beriladi):
  DB_PATH, TEST_API_SECRET, API_PORT, BOT_USERNAME,
  RECRUITMENT_API_URL, RECRUITMENT_API_SECRET

Bu skript faqat test uchun; production oqimiga aralashmaydi.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

SEED_TITLE = "E2E Farmatsevt testi"


async def _seed_test() -> int:
    import db
    await db.init_db()
    for t in await db.get_active_tests():
        if t["title"] == SEED_TITLE:
            return t["id"]
    tid = await db.create_test(SEED_TITLE, qpt=15, pass_percent=70, tpq=30,
                               allow_retake=0, show_result=1)
    for i in range(15):
        await db.add_question(tid, f"E2E savol {i}?", "To'g'ri", ["X", "Y", "Z"])
    await db.update_test_field(tid, "is_active", 1)
    return tid


async def serve() -> None:
    tid = await _seed_test()
    print(f"SEED_TEST_ID={tid}", flush=True)
    from api import run_api
    await run_api()


async def complete(assignment_id: int, correct: int, total: int) -> None:
    import db
    import services.result_sync as result_sync
    await db.init_db()

    a = await db.get_test_assignment(assignment_id)
    if a is None:
        print(f"ERROR: assignment {assignment_id} topilmadi", flush=True)
        sys.exit(2)
    test = await db.get_test(a["test_id"])
    percent = round(correct / total * 100, 1) if total else 0.0
    passed = 1 if percent >= test["pass_percent"] else 0

    await db.set_assignment_started(assignment_id)
    rid = await db.save_recruitment_result(
        telegram_id=a["telegram_id"], test_id=a["test_id"], total=total,
        correct=correct, wrong=total - correct, percent=percent, passed=passed,
        candidate_id=a["candidate_id"], vacancy_id=a["vacancy_id"],
        assignment_id=assignment_id, external_application_id=a["external_application_id"],
        started_at="2026-09-30 10:00:00", completed_at="2026-09-30 10:20:00")
    await db.set_assignment_completed(assignment_id, rid)

    # REAL HTTP POST 2-botga (result_sync'ning haqiqiy kodi)
    await result_sync.send_result_now(rid)
    r = await db.get_result(rid)
    print(f"RESULT rid={rid} percent={r['percent']} sync_status={r['sync_status']}", flush=True)
    code = 0 if r["sync_status"] == "sent" else 3
    # aiosqlite fon-thread'i jarayonni tirik ushlab qolmasligi uchun majburiy chiqish.
    sys.stdout.flush()
    os._exit(code)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: e2e_side.py serve | complete <assignment_id> <correct> <total>")
        sys.exit(1)
    mode = sys.argv[1]
    if mode == "serve":
        asyncio.run(serve())
    elif mode == "complete":
        asyncio.run(complete(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])))
    else:
        print(f"noma'lum rejim: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
