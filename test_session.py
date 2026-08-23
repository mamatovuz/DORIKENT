"""
Test topshirish sessiyasi (xotirada). Har bir savol uchun taymer,
javob variantlari random, savollar random.
"""
import asyncio
import random
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import db

log = logging.getLogger("test_session")

# user_id -> Session
_sessions: dict[int, "Session"] = {}


def get_session(user_id: int):
    return _sessions.get(user_id)


class Session:
    def __init__(self, bot: Bot, chat_id: int, user_id: int, test, questions):
        self.bot = bot
        self.chat_id = chat_id
        self.user_id = user_id
        self.test = test
        self.questions = questions          # tayyorlangan savollar
        self.index = 0
        self.correct = 0
        self.wrong = 0
        self.msg_id: int | None = None
        self.timer: asyncio.Task | None = None
        self.lock = asyncio.Lock()
        self.finished = False

    # ---------- savolni ko'rsatish ----------
    def _kb(self):
        q = self.questions[self.index]
        rows = [[InlineKeyboardButton(text=opt["text"], callback_data=f"ans:{i}")]
                for i, opt in enumerate(q["options"])]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _text(self):
        q = self.questions[self.index]
        total = len(self.questions)
        return (f"<b>{self.index + 1}/{total}</b>  ⏱ {self.test['time_per_question']} soniya\n\n"
                f"{q['text']}")

    async def send_current(self):
        m = await self.bot.send_message(self.chat_id, self._text(), reply_markup=self._kb())
        self.msg_id = m.message_id
        self._start_timer()

    def _start_timer(self):
        if self.timer:
            self.timer.cancel()
        self.timer = asyncio.create_task(self._timeout_watcher(self.index))

    async def _timeout_watcher(self, q_index: int):
        try:
            await asyncio.sleep(self.test["time_per_question"])
        except asyncio.CancelledError:
            return
        async with self.lock:
            if self.finished or self.index != q_index:
                return
            # vaqt tugadi -> noto'g'ri
            self.wrong += 1
            await self._reveal(chosen=None)
            await self._advance()

    # ---------- javob berish ----------
    async def answer(self, chosen_idx: int):
        async with self.lock:
            if self.finished:
                return
            if self.timer:
                self.timer.cancel()
            q = self.questions[self.index]
            if 0 <= chosen_idx < len(q["options"]) and q["options"][chosen_idx]["is_correct"]:
                self.correct += 1
            else:
                self.wrong += 1
            await self._reveal(chosen=chosen_idx)
            await self._advance()

    async def _reveal(self, chosen):
        """Javob berilgan savolni belgilar bilan ko'rsatib, tugmalarni olib tashlaydi."""
        q = self.questions[self.index]
        lines = [self._text(), ""]
        for i, opt in enumerate(q["options"]):
            if opt["is_correct"]:
                mark = "✅"
            elif chosen is not None and i == chosen:
                mark = "❌"
            else:
                mark = "▫️"
            lines.append(f"{mark} {opt['text']}")
        if chosen is None:
            lines.append("\n⏱ Vaqt tugadi!")
        try:
            await self.bot.edit_message_text(
                "\n".join(lines), chat_id=self.chat_id, message_id=self.msg_id
            )
        except Exception:
            pass

    async def _advance(self):
        self.index += 1
        if self.index >= len(self.questions):
            await self._finish()
        else:
            await asyncio.sleep(0.4)
            await self.send_current()

    async def _finish(self):
        self.finished = True
        total = len(self.questions)
        percent = round((self.correct / total) * 100, 1) if total else 0.0
        passed = 1 if percent >= self.test["pass_percent"] else 0

        await db.save_result(self.user_id, self.test["id"], total,
                             self.correct, self.wrong, percent, passed)
        await db.mark_assignment_done(self.test["id"], self.user_id)

        user = await db.get_user(self.user_id)
        name = user["full_name"] if user else str(self.user_id)

        show = str(self.test["show_result"]) == "1"
        if show:
            head = "🟢 Siz testdan o'tdingiz!" if passed else "🔴 Siz testdan o'ta olmadingiz."
            text = (
                "🎉 <b>Test yakunlandi!</b>\n\n"
                f"👤 Xodim: {name}\n"
                f"📝 Savollar: {total}\n"
                f"✅ To'g'ri: {self.correct}\n"
                f"❌ Noto'g'ri: {self.wrong}\n"
                f"📊 Natija: {percent}%\n\n"
                f"{head}"
            )
            if not passed and str(self.test["allow_retake"]) == "1":
                text += "\n\n🔁 Qayta topshirish imkoniyati mavjud."
        else:
            text = ("🎉 <b>Test yakunlandi!</b>\n\n"
                    "Natijangiz administratorga yuborildi. Rahmat!")

        await self.bot.send_message(self.chat_id, text)
        _sessions.pop(self.user_id, None)


def _prepare_questions(all_questions_with_opts, count: int):
    """Random savollar + random variantlar tayyorlaydi."""
    chosen = random.sample(all_questions_with_opts, min(count, len(all_questions_with_opts)))
    prepared = []
    for q in chosen:
        opts = list(q["options"])
        random.shuffle(opts)
        prepared.append({"text": q["text"], "options": opts})
    return prepared


async def start_session(bot: Bot, chat_id: int, user_id: int, test) -> tuple[bool, str]:
    """Sessiyani boshlaydi. Qaytadi (muvaffaqiyat, xabar)."""
    if user_id in _sessions:
        return False, "Sizda tugallanmagan test bor."

    questions = await db.get_questions(test["id"])
    if not questions:
        return False, "Bu testda savollar yo'q."

    with_opts = []
    for q in questions:
        opts = await db.get_options(q["id"])
        opt_list = [{"text": o["text"], "is_correct": bool(o["is_correct"])} for o in opts]
        if len(opt_list) < 2:
            continue
        with_opts.append({"text": q["text"], "options": opt_list})

    if not with_opts:
        return False, "Savollar variantlari to'liq emas."

    prepared = _prepare_questions(with_opts, test["questions_per_test"])
    sess = Session(bot, chat_id, user_id, test, prepared)
    _sessions[user_id] = sess
    await sess.send_current()
    return True, ""
