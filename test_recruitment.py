"""DoriKent tomonidagi recruitment integratsiyasi testi (REAL, mocksiz).

 - Real FastAPI ilova (ASGITransport orqali, real routing + auth + validation)
 - Real DoriKent SQLite bazasi (vaqtinchalik fayl)
 - Real result_sync payload va retry mantiqi

Ishga tushirish:
    python test_recruitment.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile

_TMP = os.path.join(tempfile.gettempdir(), "dk_recruit_test.db")
if os.path.exists(_TMP):
    os.remove(_TMP)
os.environ["DB_PATH"] = _TMP
os.environ["TEST_API_SECRET"] = "assign_secret"
os.environ["BOT_USERNAME"] = "DoriKentTestBot"
os.environ["RECRUITMENT_API_URL"] = ""       # 2-bot yo'q -> pending qolishi shart
os.environ["RECRUITMENT_API_SECRET"] = "result_secret"
os.environ["BOT_TOKEN"] = "1:AAA"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
import config
import db
from api.app import create_app
from handlers import recruitment
import services.result_sync as result_sync

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

_checks: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    _checks.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))


async def run() -> None:
    await db.init_db()

    # Seed: aktiv test + savollar
    tid = await db.create_test("Farmatsevt testi", qpt=15, pass_percent=70, tpq=30,
                               allow_retake=0, show_result=1)
    for i in range(15):
        await db.add_question(tid, f"Savol {i}?", "To'g'ri", ["X", "Y", "Z"])
    await db.update_test_field(tid, "is_active", 1)

    # Inactive test — /tests da ko'rinmasligi kerak
    tid_inactive = await db.create_test("Yashirin test", qpt=5, pass_percent=70, tpq=30,
                                        allow_retake=0, show_result=1)
    await db.add_question(tid_inactive, "Q?", "A", ["B"])

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/v1/health")
        check("health -> 200 success", r.status_code == 200 and r.json()["success"])

        r = await c.get("/api/v1/tests")
        check("tests be'auth -> 401", r.status_code == 401)

        r = await c.get("/api/v1/tests", headers={"Authorization": "Bearer assign_secret"})
        ids = [t["id"] for t in r.json()["tests"]]
        check("tests -> aktiv test bor", tid in ids)
        check("tests -> inactive test YO'Q", tid_inactive not in ids)

        # X-API-Key ham qabul qilinadi
        r = await c.get("/api/v1/tests", headers={"X-API-Key": "assign_secret"})
        check("tests X-API-Key -> 200", r.status_code == 200)

        # assign: interest_id -> external_application_id
        body = {"candidate_id": 482, "telegram_id": 123456789, "vacancy_id": 25,
                "test_id": tid, "external_application_id": 901}
        r = await c.post("/api/v1/test/assign", json=body,
                         headers={"X-API-Key": "assign_secret"})
        j = r.json()
        aid = j.get("assignment_id")
        check("assign -> 200 + assignment_id", r.status_code == 200 and isinstance(aid, int))
        check("assign -> test_title qaytdi", j.get("test_title") == "Farmatsevt testi")
        check("assign -> question_count=15", j.get("question_count") == 15)
        check("assign -> deep_link to'g'ri",
              j.get("deep_link") == f"https://t.me/DoriKentTestBot?start=test_{aid}")

        r = await c.post("/api/v1/test/assign", json={"candidate_id": 1, "telegram_id": 1},
                         headers={"X-API-Key": "assign_secret"})
        check("assign no test_id -> 422", r.status_code == 422)

        r = await c.post("/api/v1/test/assign", json={**body, "test_id": 99999},
                         headers={"X-API-Key": "assign_secret"})
        check("assign bad test -> 404", r.status_code == 404)

    # Assignment DB da
    a = await db.get_test_assignment(aid)
    check("assignment saqlandi (interest 901)", a and a["external_application_id"] == 901)

    # Ownership: boshqa telegram_id rad etiladi
    ok, err, _ = await recruitment._validate(a, 999)
    check("ownership: boshqa tg -> rad", (not ok) and "tegishli emas" in err)
    ok, err, test = await recruitment._validate(a, 123456789)
    check("ownership: to'g'ri tg -> ok", ok)

    # Test yakunini simulyatsiya: 11/15 = 73.3% (butun bo'lmagan foiz — kritik holat)
    await db.set_assignment_started(aid)
    correct, total = 11, 15
    percent = round(correct / total * 100, 1)  # 73.3
    passed = 1 if percent >= test["pass_percent"] else 0
    rid = await db.save_recruitment_result(
        telegram_id=123456789, test_id=tid, total=total, correct=correct,
        wrong=total - correct, percent=percent, passed=passed, candidate_id=482,
        vacancy_id=25, assignment_id=aid, external_application_id=901,
        started_at="2026-09-30 10:00:00", completed_at="2026-09-30 10:20:00")
    await db.set_assignment_completed(aid, rid)

    res = await db.get_result(rid)
    check("result percent lokalda REAL saqlandi (73.3)", res["percent"] == 73.3)
    check("result sync_status pending", res["sync_status"] == "pending")

    # Wire payload: percentage float (73.3), score butun (73). 2-bot ikkalasini ham float qabul qiladi.
    payload = result_sync._build_payload(res)
    check("payload percentage=73.3 (float)", payload["percentage"] == 73.3)
    check("payload score=73 (int)", payload["score"] == 73 and isinstance(payload["score"], int))
    check("payload result_key", payload["result_key"] == f"assignment_{aid}")
    check("payload started_at bor", payload["started_at"] == "2026-09-30T10:00:00Z")
    check("payload completed_at ISO", payload["completed_at"] == "2026-09-30T10:20:00Z")
    check("payload status passed", payload["status"] == "passed")
    check("payload correct/total", payload["correct_answers"] == 11 and payload["total_questions"] == 15)

    # Retry: 2-bot yo'q -> pending, attempts oshadi
    await result_sync._handle_result(res)
    res2 = await db.get_result(rid)
    check("send fail -> pending, attempts=1", res2["sync_status"] == "pending" and res2["sync_attempts"] == 1)

    # Backward-compat: oddiy employee natijasi sync_status NULL
    old_rid = await db.save_result(555, tid, 15, 10, 5, 66.7, 0)
    old = await db.get_result(old_rid)
    check("employee natijasi sync_status NULL", old["sync_status"] is None)

    total_c = len(_checks)
    passed_c = sum(1 for _, ok, _ in _checks if ok)
    print("\n" + "=" * 50)
    print(f"Natija: {passed_c}/{total_c}")
    if passed_c != total_c:
        for n, ok, d in _checks:
            if not ok:
                print(f"  FAIL: {n} ({d})")
        sys.exit(1)
    print("Barcha DoriKent recruitment testlari o'tdi.")


if __name__ == "__main__":
    asyncio.run(run())
