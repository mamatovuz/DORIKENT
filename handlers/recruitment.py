"""Recruitment (2-bot) nomzodlari uchun handlerlar.

Nomzod 2-botdan kelgan deep link orqali kiradi:
    https://t.me/<bot>?start=test_<assignment_id>

Bu oqim xodimlar (employee) oqimidan MUSTAQIL:
  * nomzod employee sifatida ro'yxatga OLINMAYDI (bazalar aralashmaydi);
  * faqat assignment mavjud bo'lganda ishlaydi (backward-compatible).
"""
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import db
import test_session

log = logging.getLogger("recruitment")
router = Router()


def _start_kb(assignment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Boshlash", callback_data=f"rbegin:{assignment_id}")]
    ])


def parse_assignment_id(payload: str) -> int | None:
    """'test_1001' -> 1001. Aks holda None."""
    if not payload or not payload.startswith("test_"):
        return None
    rest = payload[len("test_"):]
    return int(rest) if rest.isdigit() else None


async def _validate(assignment, telegram_id: int) -> tuple[bool, str, object]:
    """Assignment/test tekshiruvlari. (ok, xato_matni, test) qaytaradi."""
    if assignment is None:
        return False, "❌ Bu test topilmadi yoki muddati o'tgan.", None
    if assignment["telegram_id"] != telegram_id:
        return False, "⛔️ Bu test sizga tegishli emas.", None
    if assignment["status"] in ("cancelled", "expired"):
        return False, "❌ Bu test bekor qilingan yoki muddati o'tgan.", None

    test = await db.get_test(assignment["test_id"])
    if not test or not test["is_active"]:
        return False, "❌ Bu test hozircha faol emas.", None
    if await db.count_questions(test["id"]) == 0:
        return False, "❌ Bu testda hali savollar yo'q.", None

    # Allaqachon topshirilganmi? (qayta topshirish testga bog'liq)
    if assignment["status"] == "completed" and str(test["allow_retake"]) != "1":
        return False, "ℹ️ Siz bu testni allaqachon topshirgansiz.", None

    return True, "", test


async def start_from_deeplink(message: Message, state: FSMContext, payload: str) -> bool:
    """Deep link'ni qayta ishlaydi. True = bu recruitment deep link edi (ishlov berildi)."""
    assignment_id = parse_assignment_id(payload)
    if assignment_id is None:
        return False  # recruitment deep link emas — oddiy /start davom etsin

    await state.clear()
    assignment = await db.get_test_assignment(assignment_id)
    ok, err, test = await _validate(assignment, message.from_user.id)
    if not ok:
        await message.answer(err)
        return True

    n = min(test["questions_per_test"], await db.count_questions(test["id"]))
    await message.answer(
        "📝 <b>Sizga test tayinlandi.</b>\n\n"
        f"📋 Test: <b>{test['title']}</b>\n"
        f"Savollar soni: {n} ta\n"
        f"⏱ Har bir savol: {test['time_per_question']} soniya\n"
        f"🎯 O'tish bali: {test['pass_percent']}%\n\n"
        "Tayyor bo'lsangiz «🚀 Boshlash» tugmasini bosing.",
        reply_markup=_start_kb(assignment_id),
    )
    return True


@router.callback_query(F.data.startswith("rbegin:"))
async def recruitment_begin(call: CallbackQuery):
    assignment_id = int(call.data.split(":")[1])
    assignment = await db.get_test_assignment(assignment_id)
    ok, err, test = await _validate(assignment, call.from_user.id)
    if not ok:
        await call.answer(err, show_alert=True)
        return

    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    started, msg = await test_session.start_session(
        call.bot, call.message.chat.id, call.from_user.id, test, assignment=assignment
    )
    if not started:
        await call.message.answer(f"⚠️ {msg}")
