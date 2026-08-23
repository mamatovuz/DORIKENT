"""Test topshirish callbacklari: boshlash va javob berish."""
from aiogram import Router, F
from aiogram.types import CallbackQuery

import db
import test_session

router = Router()


@router.callback_query(F.data.startswith("begin:"))
async def begin_test(call: CallbackQuery):
    test_id = int(call.data.split(":")[1])
    test = await db.get_test(test_id)
    if not test or not test["is_active"]:
        await call.answer("Bu test hozircha faol emas.", show_alert=True)
        return

    # qayta topshirish tekshiruvi
    attempts = await db.user_test_attempts(call.from_user.id, test_id)
    if attempts > 0 and str(test["allow_retake"]) != "1":
        await call.answer("Bu testni qayta topshira olmaysiz.", show_alert=True)
        return

    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    ok, err = await test_session.start_session(
        call.bot, call.message.chat.id, call.from_user.id, test
    )
    if not ok:
        await call.message.answer(f"⚠️ {err}")


@router.callback_query(F.data.startswith("ans:"))
async def answer_question(call: CallbackQuery):
    sess = test_session.get_session(call.from_user.id)
    if not sess:
        await call.answer("Bu test allaqachon yakunlangan.", show_alert=True)
        return
    idx = int(call.data.split(":")[1])
    await call.answer()
    await sess.answer(idx)
