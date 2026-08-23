"""Admin panel handlerlari."""
import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile

import config
import db
import keyboards as kb
import ai_service
import excel_service as xls
import guide_service
from states import UploadTest, EditTest, SendTest, SettingsFSM, AddAdmin
from .employee import calc_age

log = logging.getLogger("admin")
router = Router()


class IsAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        uid = event.from_user.id if event.from_user else None
        if uid is None:
            return False
        # .env dagi super-adminlar yoki panel orqali qo'shilgan adminlar
        return config.is_admin(uid) or await db.is_admin_user(uid)


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

FIELD_LABELS = {
    "title": "Nomi",
    "questions_per_test": "Beriladigan savollar soni",
    "pass_percent": "O'tish bali (%)",
    "time_per_question": "Bir savolga vaqt (soniya)",
    "allow_retake": "Qayta topshirish (1=ha, 0=yo'q)",
    "show_result": "Natijani ko'rsatish (1=ha, 0=yo'q)",
    "gemini_api_key": "Gemini API kaliti",
    "openai_api_key": "ChatGPT (OpenAI) API kaliti",
}

# Matn (son emas) qabul qiladigan sozlamalar
TEXT_SETTINGS = {"gemini_api_key", "openai_api_key"}


# ==================== SHABLON ====================
@router.message(F.text == "📄 Shablon olish")
async def send_template(message: Message):
    buf = xls.build_template()
    await message.answer_document(
        BufferedInputFile(buf.read(), filename="savollar_shablon.xlsx"),
        caption=("📄 <b>Excel shablon</b>\n\n"
                 "Ustunlar: Savol | To'g'ri javob | Noto'g'ri 1 | 2 | 3\n"
                 "Noto'g'ri variantlarni bo'sh qoldirsangiz — AI (yoki AI-siz generator) "
                 "avtomatik yaratadi."),
    )


# ==================== EXCEL YUKLASH ====================
@router.message(F.text == "📥 Excel yuklash")
async def upload_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(UploadTest.waiting_title)
    await message.answer("🆕 Yangi test yaratamiz.\n\nTest nomini kiriting:")


@router.message(UploadTest.waiting_title, F.text)
async def upload_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(UploadTest.waiting_qpt)
    d = await db.get_setting("questions_per_test")
    await message.answer(f"Xodimga nechta savol berilsin? (default: {d})\n"
                         f"Standart qiymat uchun <code>-</code> yuboring.")


async def _num_or_default(message: Message, key: str) -> int:
    if message.text.strip() == "-":
        return int(await db.get_setting(key))
    if not message.text.strip().isdigit():
        return -1
    return int(message.text.strip())


@router.message(UploadTest.waiting_qpt, F.text)
async def upload_qpt(message: Message, state: FSMContext):
    val = await _num_or_default(message, "questions_per_test")
    if val <= 0:
        await message.answer("Iltimos, musbat son kiriting yoki <code>-</code>.")
        return
    await state.update_data(qpt=val)
    await state.set_state(UploadTest.waiting_pass)
    d = await db.get_setting("pass_percent")
    await message.answer(f"O'tish bali (%)? (default: {d})\n<code>-</code> = standart.")


@router.message(UploadTest.waiting_pass, F.text)
async def upload_pass(message: Message, state: FSMContext):
    val = await _num_or_default(message, "pass_percent")
    if not (0 <= val <= 100):
        await message.answer("0–100 oralig'ida son kiriting yoki <code>-</code>.")
        return
    await state.update_data(pass_percent=val)
    await state.set_state(UploadTest.waiting_time)
    d = await db.get_setting("time_per_question")
    await message.answer(f"Har bir savolga vaqt (soniya)? (default: {d})\n<code>-</code> = standart.")


@router.message(UploadTest.waiting_time, F.text)
async def upload_time(message: Message, state: FSMContext):
    val = await _num_or_default(message, "time_per_question")
    if val <= 0:
        await message.answer("Musbat son kiriting yoki <code>-</code>.")
        return
    await state.update_data(tpq=val)
    await state.set_state(UploadTest.waiting_file)
    await message.answer(
        "📥 Endi Excel faylni (.xlsx) yuboring.\n"
        "Shablon kerak bo'lsa /start → 📄 Shablon olish."
    )


@router.message(UploadTest.waiting_file, F.document)
async def upload_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith((".xlsx", ".xls")):
        await message.answer("❌ Iltimos, .xlsx formatidagi Excel fayl yuboring.")
        return

    await message.answer("📄 Fayl qabul qilindi. O'qilmoqda…")
    file = await bot.get_file(doc.file_id)
    buf = await bot.download_file(file.file_path)
    data = buf.read()

    try:
        parsed, warnings = xls.parse_excel(data)
    except Exception as e:
        log.exception("Excel o'qishda xato")
        await message.answer(f"❌ Faylni o'qib bo'lmadi: {e}")
        return

    if not parsed:
        await message.answer("❌ Faylda savollar topilmadi. Shablonga qarang.")
        return

    need_ai = sum(1 for p in parsed if p.needs_ai)
    ai_first_line = (await ai_service.ai_status()).splitlines()[0]
    await message.answer(
        f"📊 Savollar: {len(parsed)} ta\n"
        f"✅ To'g'ri javoblar: {len(parsed)} ta\n"
        + (f"⚙️ {need_ai} ta savol uchun noto'g'ri variantlar yaratilmoqda…\n"
           f"({ai_first_line})" if need_ai else "")
    )

    # AI/offline generatsiya
    pool = [p.correct for p in parsed]
    prepared = []
    sources = {"gemini": 0, "openai": 0, "offline": 0, "excel": 0}

    sem = asyncio.Semaphore(2)  # AI free-tier rate-limitiga ehtiyotkorlik

    async def _make(p: xls.ParsedQuestion):
        if not p.needs_ai:
            sources["excel"] += 1
            return {"text": p.text, "correct": p.correct, "wrongs": p.wrongs[:3]}
        async with sem:
            wrongs, src = await ai_service.generate_wrong_answers(p.text, p.correct, pool)
        sources[src] = sources.get(src, 0) + 1
        # excel dagi qisman variantlarni ham qo'shamiz
        combined = (p.wrongs + [w for w in wrongs if w not in p.wrongs])[:3]
        while len(combined) < 3:
            combined.append("Noto'g'ri variant")
        return {"text": p.text, "correct": p.correct, "wrongs": combined}

    prepared = await asyncio.gather(*[_make(p) for p in parsed])

    total_variants = sum(1 + len(q["wrongs"]) for q in prepared)
    await state.update_data(prepared=prepared)

    src_line = ", ".join(f"{k}:{v}" for k, v in sources.items() if v)
    warn_line = ("\n\n⚠️ " + "\n⚠️ ".join(warnings)) if warnings else ""
    await message.answer(
        f"🤖 <b>Test tayyor!</b>\n\n"
        f"Savollar: {len(prepared)}\n"
        f"Variantlar: {total_variants}\n"
        f"Manba: {src_line}"
        f"{warn_line}",
        reply_markup=kb.confirm_upload_kb(),
    )


@router.callback_query(F.data == "up_view")
async def upload_view(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prepared = data.get("prepared", [])
    if not prepared:
        await call.answer("Ma'lumot topilmadi.", show_alert=True)
        return
    lines = ["👁 <b>Ko'rib chiqish (dastlabki 5 ta):</b>\n"]
    for i, q in enumerate(prepared[:5], start=1):
        lines.append(f"<b>{i}. {q['text']}</b>")
        lines.append(f"   ✅ {q['correct']}")
        for w in q["wrongs"]:
            lines.append(f"   ▫️ {w}")
        lines.append("")
    await call.answer()
    await call.message.answer("\n".join(lines))


@router.callback_query(F.data == "up_cancel")
async def upload_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("Bekor qilindi.")
    await call.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data == "up_confirm")
async def upload_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prepared = data.get("prepared", [])
    if not prepared:
        await call.answer("Ma'lumot topilmadi.", show_alert=True)
        return
    await call.answer("Saqlanmoqda…")

    test_id = await db.create_test(
        title=data["title"],
        qpt=data["qpt"],
        pass_percent=data["pass_percent"],
        tpq=data["tpq"],
        allow_retake=int(await db.get_setting("allow_retake")),
        show_result=int(await db.get_setting("show_result")),
    )
    for q in prepared:
        await db.add_question(test_id, q["text"], q["correct"], q["wrongs"])

    await state.clear()
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        f"✅ <b>«{data['title']}»</b> testi yaratildi!\n"
        f"Savollar: {len(prepared)}\n\n"
        "▶️ Testni faollashtirish va xodimlarga yuborish uchun "
        "«📝 Testlar» bo'limiga o'ting.",
        reply_markup=kb.admin_menu(),
    )


# ==================== TESTLAR ====================
@router.message(F.text == "📝 Testlar")
async def tests_list(message: Message):
    tests = await db.list_tests()
    if not tests:
        await message.answer("Hozircha testlar yo'q. «📥 Excel yuklash» orqali qo'shing.")
        return
    await message.answer("📝 <b>Testlar</b>\n🟢 = faol, ⚪️ = to'xtatilgan",
                         reply_markup=kb.tests_list_kb(tests))


@router.callback_query(F.data == "tests_back")
async def tests_back(call: CallbackQuery):
    tests = await db.list_tests()
    await call.answer()
    await call.message.edit_text("📝 <b>Testlar</b>\n🟢 = faol, ⚪️ = to'xtatilgan",
                                 reply_markup=kb.tests_list_kb(tests))


async def _test_card(test) -> str:
    q_count = await db.count_questions(test["id"])
    return (
        f"📋 <b>{test['title']}</b>\n\n"
        f"Bazadagi savollar: {q_count} ta\n"
        f"Beriladigan savollar: {test['questions_per_test']} ta\n"
        f"O'tish bali: {test['pass_percent']}%\n"
        f"Vaqt/savol: {test['time_per_question']} soniya\n"
        f"Qayta topshirish: {'ha' if str(test['allow_retake'])=='1' else 'yo`q'}\n"
        f"Natijani ko'rsatish: {'ha' if str(test['show_result'])=='1' else 'yo`q'}\n"
        f"Holat: {'🟢 faol' if test['is_active'] else '⚪️ to`xtatilgan'}"
    )


@router.callback_query(F.data.startswith("test:"))
async def test_open(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    test = await db.get_test(tid)
    if not test:
        await call.answer("Test topilmadi.", show_alert=True)
        return
    await call.answer()
    await call.message.edit_text(await _test_card(test), reply_markup=kb.test_manage_kb(test))


@router.callback_query(F.data.startswith("toggle:"))
async def test_toggle(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    test = await db.get_test(tid)
    new_val = 0 if test["is_active"] else 1
    if new_val == 1 and await db.count_questions(tid) == 0:
        await call.answer("Savol yo'q testni faollashtirib bo'lmaydi.", show_alert=True)
        return
    await db.update_test_field(tid, "is_active", new_val)
    test = await db.get_test(tid)
    await call.answer("Holat yangilandi.")
    await call.message.edit_text(await _test_card(test), reply_markup=kb.test_manage_kb(test))


@router.callback_query(F.data.startswith("del:"))
async def test_delete(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    await db.delete_test(tid)
    tests = await db.list_tests()
    await call.answer("O'chirildi.")
    await call.message.edit_text("🗑 Test o'chirildi.\n\n📝 <b>Testlar</b>",
                                 reply_markup=kb.tests_list_kb(tests))


@router.callback_query(F.data.startswith("view:"))
async def test_view(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    questions = await db.get_questions(tid)
    await call.answer()
    if not questions:
        await call.message.answer("Bu testda savollar yo'q.")
        return
    lines = [f"👁 <b>Savollar ({len(questions)} ta), dastlabki 10:</b>\n"]
    for i, q in enumerate(questions[:10], start=1):
        lines.append(f"<b>{i}. {q['text']}</b>")
        opts = await db.get_options(q["id"])
        for o in opts:
            mark = "✅" if o["is_correct"] else "▫️"
            lines.append(f"   {mark} {o['text']}")
        lines.append("")
    await call.message.answer("\n".join(lines))


# ---------- Test tahrirlash ----------
@router.callback_query(F.data.startswith("edit:"))
async def test_edit(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    await call.answer()
    await call.message.edit_text("✏️ Qaysi maydonni tahrirlaymiz?",
                                 reply_markup=kb.edit_fields_kb(tid))


@router.callback_query(F.data.startswith("ef:"))
async def edit_field(call: CallbackQuery, state: FSMContext):
    _, tid, field = call.data.split(":")
    await state.set_state(EditTest.waiting_value)
    await state.update_data(test_id=int(tid), field=field)
    await call.answer()
    await call.message.answer(f"Yangi qiymat kiriting — <b>{FIELD_LABELS.get(field, field)}</b>:")


@router.message(EditTest.waiting_value, F.text)
async def edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    tid, field = data["test_id"], data["field"]
    val = message.text.strip()
    if field != "title":
        if not val.lstrip("-").isdigit():
            await message.answer("Son kiriting.")
            return
        val = int(val)
    await db.update_test_field(tid, field, val)
    await state.clear()
    test = await db.get_test(tid)
    await message.answer("✅ Yangilandi.")
    await message.answer(await _test_card(test), reply_markup=kb.test_manage_kb(test))


# ==================== XODIMLAR ====================
@router.message(F.text == "👥 Xodimlar")
async def employees(message: Message):
    users = await db.list_users("employee")
    if not users:
        await message.answer("Hali xodimlar botni ishga tushirmagan.\n"
                             "Ular /start bosgach shu yerda paydo bo'ladi.")
        return
    await message.answer("👥 <b>Xodimlar</b>", reply_markup=kb.users_list_kb(users))


@router.callback_query(F.data.startswith("emp:"))
async def employee_card(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    user = await db.get_user(uid)
    stats = await db.user_stats(uid)
    results = await db.user_results(uid)
    await call.answer()
    name = user["full_name"] if user else str(uid)
    avg = round(stats["avg_percent"], 1) if stats["avg_percent"] is not None else 0
    age = calc_age(user["birth_date"]) if user else None
    age_str = f"{age} yosh" if age is not None else "—"
    exp = user["experience_years"] if user and user["experience_years"] is not None else "—"
    lines = [
        f"👤 <b>{name}</b>",
        f"@{user['username']}" if user and user["username"] else "",
        "",
        "<b>👔 Profil</b>",
        f"Ism: {user['first_name'] or '—'}" if user else "",
        f"Familiya: {user['last_name'] or '—'}" if user else "",
        f"Jinsi: {user['gender'] or '—'}" if user else "",
        f"Tug'ilgan kun: {user['birth_date'] or '—'}" if user else "",
        f"Yoshi: {age_str}",
        f"Ish staji: {exp} yil",
        "",
        "<b>📊 Statistika</b>",
        f"Topshirilgan testlar: {stats['attempts'] or 0}",
        f"O'rtacha natija: {avg}%",
        f"O'tgan testlar: {stats['passed_count'] or 0}",
        "",
        "<b>Oxirgi natijalar:</b>",
    ]
    for r in results[:5]:
        icon = "🟢" if r["passed"] else "🔴"
        lines.append(f"{icon} {r['title']} — {r['percent']}%")
    text = "\n".join(l for l in lines if l != "")
    if user and user["photo_file_id"]:
        if len(text) <= 1024:
            await call.message.answer_photo(user["photo_file_id"], caption=text)
        else:
            await call.message.answer_photo(user["photo_file_id"])
            await call.message.answer(text)
    else:
        await call.message.answer(text)


# ==================== NATIJALAR ====================
@router.message(F.text == "📊 Natijalar")
async def results_menu(message: Message):
    rows = await db.all_results()
    if not rows:
        await message.answer("Hali natijalar yo'q.")
        return
    lines = ["📊 <b>Natijalar (oxirgi 15):</b>\n"]
    for r in rows[:15]:
        icon = "🟢" if r["passed"] else "🔴"
        lines.append(f"{icon} {r['full_name']} — {r['title']} — {r['percent']}%")
    lines.append("\n📥 To'liq ro'yxatni Excel qilib yuklab olyapman…")
    await message.answer("\n".join(lines))
    buf = xls.build_results_excel(rows)
    await message.answer_document(
        BufferedInputFile(buf.read(), filename="natijalar.xlsx"),
        caption="📥 Barcha natijalar",
    )


# ==================== SOZLAMALAR ====================
@router.message(F.text == "⚙️ Sozlamalar")
async def settings_menu(message: Message):
    s = await db.all_settings()
    await message.answer(
        "⚙️ <b>Sozlamalar</b> (yangi testlar uchun standart qiymatlar)\n"
        "O'zgartirish uchun tugmani bosing:",
        reply_markup=kb.settings_kb(s),
    )


@router.callback_query(F.data.startswith("set:"))
async def settings_change(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":")[1]
    # boolean sozlamalar bir bosishda almashadi
    if key in ("allow_retake", "show_result"):
        cur = await db.get_setting(key)
        await db.set_setting(key, "0" if cur == "1" else "1")
        s = await db.all_settings()
        await call.answer("O'zgartirildi.")
        await call.message.edit_reply_markup(reply_markup=kb.settings_kb(s))
        return
    await state.set_state(SettingsFSM.waiting_value)
    await state.update_data(key=key)
    await call.answer()
    if key in TEXT_SETTINGS:
        await call.message.answer(
            f"🔑 <b>{FIELD_LABELS.get(key, key)}</b>ni kiriting.\n\n"
            "Kalitni to'liq nusxalab yuboring.\n"
            "Kalitni o'chirish uchun <code>-</code> yuboring."
        )
    else:
        await call.message.answer(f"Yangi qiymat kiriting — <b>{FIELD_LABELS.get(key, key)}</b>:")


@router.message(SettingsFSM.waiting_value, F.text)
async def settings_value(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data["key"]
    val = message.text.strip()

    if key in TEXT_SETTINGS:
        # "-" => kalitni tozalash
        new_val = "" if val == "-" else val
        await db.set_setting(key, new_val)
        await state.clear()
        s = await db.all_settings()
        status = "o'chirildi" if new_val == "" else "saqlandi"
        await message.answer(f"✅ {FIELD_LABELS.get(key, key)} {status}.",
                             reply_markup=kb.admin_menu())
        await message.answer("⚙️ <b>Sozlamalar</b>", reply_markup=kb.settings_kb(s))
        return

    if not val.isdigit():
        await message.answer("Son kiriting.")
        return
    if key == "pass_percent" and not (0 <= int(val) <= 100):
        await message.answer("0–100 oralig'ida.")
        return
    await db.set_setting(key, int(val))
    await state.clear()
    s = await db.all_settings()
    await message.answer("✅ Saqlandi.", reply_markup=kb.admin_menu())
    await message.answer("⚙️ <b>Sozlamalar</b>", reply_markup=kb.settings_kb(s))


# ==================== AI HOLATI ====================
@router.message(F.text == "🤖 AI holati")
async def ai_status(message: Message):
    status = await ai_service.ai_status()
    await message.answer(
        "🤖 <b>AI holati</b>\n\n" + status +
        f"\n\nTartib: {', '.join(config.AI_ORDER)}\n\n"
        "AI kalitlarini «⚙️ Sozlamalar» bo'limidan qo'lda kiritishingiz mumkin. "
        "Ikkalasi ham bo'sh bo'lsa, bot AI-siz generator bilan ishlaydi."
    )


# ==================== TEST YUBORISH ====================
@router.message(F.text == "📤 Test yuborish")
async def send_test_start(message: Message, state: FSMContext):
    tests = await db.list_tests()
    if not tests:
        await message.answer("Avval test yarating.")
        return
    await state.set_state(SendTest.choosing_test)
    await message.answer("📤 Qaysi testni yuboramiz?", reply_markup=kb.tests_list_kb(tests))


@router.callback_query(SendTest.choosing_test, F.data.startswith("test:"))
async def send_choose_test(call: CallbackQuery, state: FSMContext):
    tid = int(call.data.split(":")[1])
    await _open_user_picker(call, state, tid)


@router.callback_query(F.data.startswith("assign:"))
async def assign_from_manage(call: CallbackQuery, state: FSMContext):
    tid = int(call.data.split(":")[1])
    await _open_user_picker(call, state, tid)


async def _open_user_picker(call: CallbackQuery, state: FSMContext, tid: int):
    users = await db.list_users("employee")
    if not users:
        await call.answer("Xodimlar yo'q. Ular /start bosishi kerak.", show_alert=True)
        return
    await state.set_state(SendTest.choosing_users)
    await state.update_data(test_id=tid, selected=[])
    await call.answer()
    await call.message.edit_text(
        "👥 Kimga yuboramiz? Tanlab, «🚀 Yuborish» ni bosing.",
        reply_markup=kb.users_pick_kb(users, set(), tid),
    )


@router.callback_query(SendTest.choosing_users, F.data.startswith("pick:"))
async def pick_user(call: CallbackQuery, state: FSMContext):
    uid = int(call.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("selected", []))
    if uid in selected:
        selected.discard(uid)
    else:
        selected.add(uid)
    await state.update_data(selected=list(selected))
    users = await db.list_users("employee")
    await call.answer()
    await call.message.edit_reply_markup(
        reply_markup=kb.users_pick_kb(users, selected, data["test_id"]))


@router.callback_query(SendTest.choosing_users, F.data == "pick_all")
async def pick_all(call: CallbackQuery, state: FSMContext):
    users = await db.list_users("employee")
    data = await state.get_data()
    selected = {u["telegram_id"] for u in users}
    await state.update_data(selected=list(selected))
    await call.answer("Hammasi tanlandi.")
    await call.message.edit_reply_markup(
        reply_markup=kb.users_pick_kb(users, selected, data["test_id"]))


@router.callback_query(SendTest.choosing_users, F.data == "pick_cancel")
async def pick_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("Bekor qilindi.")
    await call.message.edit_text("❌ Bekor qilindi.")


@router.callback_query(SendTest.choosing_users, F.data == "pick_send")
async def pick_send(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    tid = data["test_id"]
    selected = data.get("selected", [])
    if not selected:
        await call.answer("Hech kim tanlanmagan.", show_alert=True)
        return
    test = await db.get_test(tid)
    if await db.count_questions(tid) == 0:
        await call.answer("Testda savol yo'q.", show_alert=True)
        return

    # test yuborilsa avtomatik faollashtiramiz
    if not test["is_active"]:
        await db.update_test_field(tid, "is_active", 1)

    sent, failed = 0, 0
    for uid in selected:
        await db.assign_test(tid, uid)
        try:
            await bot.send_message(
                uid,
                f"📝 <b>Sizga yangi test tayinlandi.</b>\n\n"
                f"Test: {test['title']}\n"
                f"Savollar: {test['questions_per_test']} ta\n"
                f"O'tish bali: {test['pass_percent']}%",
                reply_markup=kb.start_test_kb(tid),
            )
            sent += 1
        except Exception as e:
            log.warning("Xodimga yuborilmadi %s: %s", uid, e)
            failed += 1

    await state.clear()
    await call.answer()
    await call.message.edit_text(
        f"✅ Yuborildi: {sent} ta xodim" + (f"\n⚠️ Yuborilmadi: {failed}" if failed else "")
    )


# ==================== QO'LLANMA (PDF) ====================
@router.message(F.text == "📖 Qo'llanma")
async def send_guide(message: Message):
    await message.answer("📖 Qo'llanma tayyorlanmoqda…")
    buf = guide_service.build_guide_pdf()
    await message.answer_document(
        BufferedInputFile(buf.read(), filename="DoriKent_qollanma.pdf"),
        caption="📖 <b>To'liq qo'llanma</b>\n\nBotni admin va xodim (mijoz) qanday ishlatishi "
                "batafsil yozilgan.",
    )


# ==================== ADMINLAR ====================
@router.message(F.text == "👑 Adminlar")
async def admins_menu(message: Message):
    admins = await db.list_admins()
    lines = ["👑 <b>Adminlar ro'yxati</b>\n"]
    shown = set()
    for a in admins:
        name = a["full_name"] or (f"@{a['username']}" if a["username"] else str(a["telegram_id"]))
        lines.append(f"• {name} (<code>{a['telegram_id']}</code>)")
        shown.add(a["telegram_id"])
    for eid in config.ADMIN_IDS:
        if eid not in shown:
            lines.append(f"• (asosiy) <code>{eid}</code>")
    if len(lines) == 1:
        lines.append("Hozircha panel orqali admin qo'shilmagan.")
    lines.append("\nYangi admin qo'shish uchun usulni tanlang:")
    await message.answer("\n".join(lines), reply_markup=kb.admins_kb())


ADD_ADMIN_PROMPT = {
    "id": "🆔 Yangi adminning Telegram <b>ID</b> raqamini yuboring (faqat son).\n"
          "Foydalanuvchi o'z ID sini @userinfobot orqali bilib olishi mumkin.",
    "username": "🔗 Yangi adminning <b>username</b> ini yuboring (masalan: <code>@username</code>).\n"
                "Foydalanuvchi avval botni /start qilgan bo'lsa aniqroq topiladi.",
    "phone": "📞 Yangi adminning <b>kontaktini</b> yuboring "
             "(📎 → Kontakt → o'sha odamni tanlang).\n"
             "Bot uning Telegram'da borligini tekshiradi.",
}


@router.callback_query(F.data.startswith("addadm:"))
async def add_admin_start(call: CallbackQuery, state: FSMContext):
    method = call.data.split(":")[1]
    if method not in ADD_ADMIN_PROMPT:
        await call.answer("Noma'lum usul.", show_alert=True)
        return
    await state.set_state(AddAdmin.waiting_value)
    await state.update_data(method=method)
    await call.answer()
    await call.message.answer(ADD_ADMIN_PROMPT[method])


async def _grant_admin(message: Message, bot: Bot, target_id: int, name: str, username: str):
    await db.make_admin(target_id, name, username)
    label = name or (f"@{username}" if username else str(target_id))
    await message.answer(
        f"✅ <b>Admin qo'shildi:</b> {label} (<code>{target_id}</code>)",
        reply_markup=kb.admin_menu(),
    )
    try:
        await bot.send_message(
            target_id,
            "👑 <b>Sizga admin huquqi berildi!</b>\n\n/start bosib admin paneldan foydalaning.",
        )
    except Exception:
        await message.answer("ℹ️ Eslatma: foydalanuvchiga xabar yuborib bo'lmadi "
                             "(u avval botni /start qilishi kerak).")


@router.message(AddAdmin.waiting_value, F.contact)
async def add_admin_contact(message: Message, state: FSMContext, bot: Bot):
    c = message.contact
    if c.user_id is None:
        await message.answer(
            "❌ Bu raqam Telegram'da topilmadi yoki foydalanuvchi ma'lumotini yashirgan.\n"
            "Boshqa usulni sinab ko'ring (ID yoki username)."
        )
        await state.clear()
        return
    name = " ".join(x for x in [c.first_name, c.last_name] if x)
    await state.clear()
    await _grant_admin(message, bot, c.user_id, name, "")


@router.message(AddAdmin.waiting_value, F.text)
async def add_admin_value(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    method = data.get("method")
    val = message.text.strip()

    if method == "phone":
        await message.answer("Iltimos, telefon uchun <b>kontakt</b> yuboring (📎 → Kontakt).")
        return

    if method == "id":
        if not val.lstrip("-").isdigit():
            await message.answer("Faqat raqamli ID kiriting.")
            return
        target_id = int(val)
        name, username = "", ""
        try:
            chat = await bot.get_chat(target_id)
            name = chat.full_name or ""
            username = chat.username or ""
        except Exception:
            pass  # ID berilgan — baribir admin qilamiz, u /start bosganda faollashadi
        await state.clear()
        await _grant_admin(message, bot, target_id, name, username)
        return

    if method == "username":
        uname = val.lstrip("@")
        if not uname:
            await message.answer("Username kiriting (masalan: @username).")
            return
        try:
            chat = await bot.get_chat(f"@{uname}")
        except Exception:
            await message.answer(
                "❌ Bu username topilmadi.\n"
                "Foydalanuvchi avval botni /start qilishi kerak, yoki ID/kontakt orqali qo'shing."
            )
            return
        await state.clear()
        await _grant_admin(message, bot, chat.id, chat.full_name or "", chat.username or uname)
        return

    await message.answer("Noma'lum usul. «👑 Adminlar» dan qaytadan boshlang.")
    await state.clear()
