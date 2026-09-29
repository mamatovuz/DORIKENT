"""API biznes-mantiqi — db qatlami bilan bog'lovchi (route'lar yupqa qoladi)."""
import logging

import config
import db

log = logging.getLogger("api.service")


def build_deep_link(assignment_id: int) -> str | None:
    """https://t.me/<username>?start=test_<assignment_id> — username bo'lsa."""
    if not config.BOT_USERNAME:
        return None
    return f"https://t.me/{config.BOT_USERNAME}?start=test_{assignment_id}"


async def list_active_tests() -> list[dict]:
    """Faqat aktiv, savoli bor testlar ro'yxati (API contract shaklida)."""
    tests = await db.get_active_tests()
    out = []
    for t in tests:
        available = await db.count_questions(t["id"])
        if available == 0:
            continue
        # Xodimga real beriladigan savollar soni.
        question_count = min(t["questions_per_test"], available)
        out.append({
            "id": t["id"],
            "title": t["title"],
            "description": (t["description"] if "description" in t.keys() else None) or None,
            "question_count": question_count,
            "passing_score": t["pass_percent"],
            "time_per_question": t["time_per_question"],
            "active": bool(t["is_active"]),
        })
    return out


async def assign_test(*, candidate_id: int, telegram_id: int, vacancy_id,
                      test_id: int, external_application_id) -> dict:
    """Testni nomzodga tayinlaydi. (ok, payload | error) qaytaradi."""
    test = await db.get_test(test_id)
    if not test:
        return {"ok": False, "error": "test_not_found"}
    if not test["is_active"]:
        return {"ok": False, "error": "test_inactive"}
    if await db.count_questions(test_id) == 0:
        return {"ok": False, "error": "test_has_no_questions"}

    assignment_id = await db.create_test_assignment(
        candidate_id=candidate_id,
        telegram_id=telegram_id,
        vacancy_id=vacancy_id,
        test_id=test_id,
        external_application_id=external_application_id,
    )
    log.info("Test tayinlandi: assignment=%s candidate=%s test=%s",
             assignment_id, candidate_id, test_id)
    question_count = min(test["questions_per_test"], await db.count_questions(test_id))
    return {
        "ok": True,
        "assignment_id": assignment_id,
        "test_id": test_id,
        "status": "assigned",
        "test_title": test["title"],
        "question_count": question_count,
        "deep_link": build_deep_link(assignment_id),
    }
