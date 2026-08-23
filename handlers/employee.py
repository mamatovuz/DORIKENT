"""Xodim (employee) handlerlari: /start, ro'yxatdan o'tish, profil, test, natijalar."""
from datetime import date, datetime, timedelta

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import config
import db
import keyboards as kb
from states import Registration, ProfileEdit

router = Router()

EDIT_COOLDOWN_DAYS = 7


# ---------- Yordamchi funksiyalar ----------
def parse_birth_date(text: str):
    """kun.oy.yil (dd.mm.yyyy) formatini tekshiradi. To'g'ri bo'lsa date qaytaradi, aks holda None."""
    text = text.strip()
    try:
        d = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        return None
    if d.year < 1900 or d > date.today():
        return None
    return d


def calc_age(birth_date: str):
    """dd.mm.yyyy dan yoshni hisoblaydi."""
    try:
        d = datetime.strptime(birth_date, "%d.%m.%Y").date()
    except (ValueError, TypeError):
        return None
    today = date.today()
    return today.year - d.year - ((today.month, today.day) < (d.month, d.day))


def split_name(text: str):
    """'Aziz Azizov' -> ('Aziz', 'Azizov'). Yetarli emas bo'lsa None."""
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    first = parts[0]
    last = " ".join(parts[1:])
    return first, last


def edit_cooldown_left(user):
    """Profil tahrirlashga qancha vaqt qolganini timedelta qaytaradi. Ruxsat bo'lsa None."""
    last = user["last_profile_edit"]
    if not last:
        return None
    try:
        dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    nxt = dt + timedelta(days=EDIT_COOLDOWN_DAYS)
    now = datetime.now()
    if now >= nxt:
        return None
    return nxt - now


def cooldown_msg(left: timedelta) -> str:
    days = left.days
    hours = left.seconds // 3600
    if days > 0:
        when = f"{days} kun {hours} soat"
    else:
        minutes = (left.seconds % 3600) // 60
        when = f"{hours} soat {minutes} daqiqa"
    return (f"⏳ Profil ma'lumotlarini haftada faqat 1 marta o'zgartirish mumkin.\n"
            f"Keyingi o'zgartirish: {when} dan keyin.")


async def _register(message: Message) -> str:
    """Foydalanuvchini bazaga yozadi va rolini qaytaradi."""
    u = message.from_user
    role = "admin" if config.is_admin(u.id) else "employee"
    await db.upsert_user(u.id, u.full_name, u.username or "", role)
    user = await db.get_user(u.id)
    return user["role"]


async def _available_tests(user_id: int):
    """Xodim topshira oladigan faol testlar (savoli bor, qayta topshirish qoidasi bilan)."""
    tests = await db.get_active_tests()
    out = []
    for t in tests:
        if await db.count_questions(t["id"]) == 0:
            continue
        attempts = await db.user_test_attempts(user_id, t["id"])
        if attempts > 0 and str(t["allow_retake"]) != "1":
            continue
        out.append(t)
    return out


def _profile_text(user) -> str:
    age = calc_age(user["birth_date"])
    age_str = f"{age} yosh" if age is not None else "—"
    exp = user["experience_years"] if user["experience_years"] is not None else "—"
    return (
        "👤 <b>Mening profilim</b>\n\n"
        f"Ism: <b>{user['first_name'] or '—'}</b>\n"
        f"Familiya: <b>{user['last_name'] or '—'}</b>\n"
        f"Jinsi: {user['gender'] or '—'}\n"
        f"Tug'ilgan kun: {user['birth_date'] or '—'}\n"
        f"Yoshi: {age_str}\n"
        f"Ish staji: {exp} yil"
    )


async def _send_profile(message: Message, user):
    """Profilni rasm + matn + tahrirlash tugmasi bilan yuboradi."""
    if user["photo_file_id"]:
        await message.answer_photo(user["photo_file_id"], caption=_profile_text(user),
                                   reply_markup=kb.profile_kb())
    else:
        await message.answer(_profile_text(user), reply_markup=kb.profile_kb())


# ==================== /start ====================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    role = await _register(message)

    if role == "admin":
        await message.answer(
            "👨‍💼 <b>Admin panel</b>\n\nKerakli bo'limni tanlang:",
            reply_markup=kb.admin_menu(),
        )
        return

    # Xodim — ro'yxatdan o'tganmi?
    if not await db.is_user_registered(message.from_user.id):
        await state.set_state(Registration.waiting_name)
        await message.answer(
            "👋 <b>Assalomu alaykum!</b>\n"
            "Xodimlar test botiga xush kelibsiz.\n\n"
            "Avval qisqa ro'yxatdan o'tamiz.\n\n"
            "1️⃣ <b>Ism va familiyangizni</b> kiriting.\n"
            "Masalan: <code>Aziz Azizov</code>"
        )
        return

    await _show_employee_home(message)


async def _show_employee_home(message: Message):
    tests = await _available_tests(message.from_user.id)
    text = (
        "👋 <b>Xush kelibsiz!</b>\n"
        "📝 Bu bot orqali sizga tayinlangan testlarni topshirishingiz mumkin.\n"
    )
    if tests:
        text += "\n✅ Siz uchun test mavjud. «📝 Testni boshlash» tugmasini bosing."
    else:
        text += "\nℹ️ Hozircha siz uchun mavjud test yo'q."
    await message.answer(text, reply_markup=kb.employee_menu(bool(tests)))


# ==================== RO'YXATDAN O'TISH ====================
@router.message(Registration.waiting_name, F.text)
async def reg_name(message: Message, state: FSMContext):
    res = split_name(message.text)
    if res is None:
        await message.answer("Iltimos, ism va familiyangizni birga kiriting.\n"
                             "Masalan: <code>Aziz Azizov</code>")
        return
    first, last = res
    await state.update_data(first_name=first, last_name=last)
    await state.set_state(Registration.waiting_gender)
    await message.answer("2️⃣ <b>Jinsingizni</b> tanlang:", reply_markup=kb.gender_kb())


@router.callback_query(Registration.waiting_gender, F.data.startswith("gender:"))
async def reg_gender(call: CallbackQuery, state: FSMContext):
    gender = call.data.split(":")[1]
    await state.update_data(gender=gender)
    await state.set_state(Registration.waiting_birth_date)
    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer(
        f"Jinsi: <b>{gender}</b> ✅\n\n"
        "3️⃣ <b>Tug'ilgan kuningizni</b> kiriting.\n"
        "Format: <code>kun.oy.yil</code>\n"
        "Masalan: <code>05.09.1998</code>"
    )


@router.message(Registration.waiting_gender)
async def reg_gender_wrong(message: Message):
    await message.answer("Iltimos, quyidagi tugmalardan jinsingizni tanlang:",
                         reply_markup=kb.gender_kb())


@router.message(Registration.waiting_birth_date, F.text)
async def reg_birth_date(message: Message, state: FSMContext):
    d = parse_birth_date(message.text)
    if d is None:
        await message.answer(
            "❌ Noto'g'ri format.\n"
            "Iltimos, <code>kun.oy.yil</code> ko'rinishida kiriting.\n"
            "Masalan: <code>05.09.1998</code>"
        )
        return
    await state.update_data(birth_date=d.strftime("%d.%m.%Y"))
    await state.set_state(Registration.waiting_experience)
    await message.answer(
        "4️⃣ <b>Ish stajingizni</b> kiriting.\n"
        "Necha yildan beri shu sohada ishlaysiz? (faqat son)\n"
        "Masalan: <code>5</code>"
    )


@router.message(Registration.waiting_experience, F.text)
async def reg_experience(message: Message, state: FSMContext):
    val = message.text.strip()
    if not val.isdigit() or int(val) > 80:
        await message.answer("Iltimos, ish stajingizni yil hisobida son bilan kiriting (masalan: 5):")
        return
    await state.update_data(experience_years=int(val))
    await state.set_state(Registration.waiting_photo)
    await message.answer(
        "5️⃣ <b>Profil rasmingizni</b> yuboring.\n\n"
        "📸 Iltimos, oxirgi 15 kun ichida tushgan rasmingizni yuboring.\n"
        "Rasmni surat (foto) sifatida yuboring."
    )


@router.message(Registration.waiting_photo, F.photo)
async def reg_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id  # eng katta o'lcham
    data = await state.get_data()
    await db.register_user(
        telegram_id=message.from_user.id,
        first_name=data["first_name"],
        last_name=data["last_name"],
        gender=data["gender"],
        birth_date=data["birth_date"],
        experience_years=data["experience_years"],
        photo_file_id=file_id,
    )
    await state.clear()
    await message.answer("✅ <b>Ro'yxatdan o'tdingiz!</b> Rahmat.")
    user = await db.get_user(message.from_user.id)
    await _send_profile(message, user)
    await _show_employee_home(message)


@router.message(Registration.waiting_photo)
async def reg_photo_wrong(message: Message):
    await message.answer("Iltimos, rasmni surat (foto) ko'rinishida yuboring 📸")


# ==================== PROFIL ====================
@router.message(F.text == "👤 Mening profilim")
async def my_profile(message: Message):
    await _register(message)
    user = await db.get_user(message.from_user.id)
    if not user or not user["is_registered"]:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start ni bosing.")
        return
    await _send_profile(message, user)


@router.callback_query(F.data == "pedit")
async def profile_edit_open(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    if not user or not user["is_registered"]:
        await call.answer("Avval ro'yxatdan o'ting.", show_alert=True)
        return
    left = edit_cooldown_left(user)
    if left is not None:
        await call.answer(cooldown_msg(left), show_alert=True)
        return
    await call.answer()
    await call.message.edit_reply_markup(reply_markup=kb.profile_edit_kb())


@router.callback_query(F.data == "pf_back")
async def profile_edit_back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=kb.profile_kb())
    except Exception:
        pass


PF_PROMPTS = {
    "name": ("👤 Ism va familiyangizni kiriting:\nMasalan: <code>Aziz Azizov</code>",
             ProfileEdit.waiting_value),
    "birth_date": ("🎂 Tug'ilgan kuningizni kiriting.\nFormat: <code>kun.oy.yil</code>\n"
                   "Masalan: <code>05.09.1998</code>", ProfileEdit.waiting_value),
    "experience_years": ("💼 Ish stajingizni kiriting (yil, faqat son):",
                         ProfileEdit.waiting_value),
    "photo": ("🖼 Yangi profil rasmingizni yuboring (foto sifatida):",
              ProfileEdit.waiting_value),
}


@router.callback_query(F.data.startswith("pf:"))
async def profile_field_pick(call: CallbackQuery, state: FSMContext):
    field = call.data.split(":")[1]
    user = await db.get_user(call.from_user.id)
    left = edit_cooldown_left(user) if user else None
    if left is not None:
        await call.answer(cooldown_msg(left), show_alert=True)
        return

    if field == "gender":
        await call.answer()
        await call.message.answer("⚧ Jinsingizni tanlang:", reply_markup=kb.pedit_gender_kb())
        return

    prompt, st = PF_PROMPTS.get(field, (None, None))
    if not prompt:
        await call.answer("Noma'lum maydon.", show_alert=True)
        return
    await state.set_state(st)
    await state.update_data(field=field)
    await call.answer()
    await call.message.answer(prompt)


async def _finish_edit(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer("✅ Ma'lumot yangilandi.")
    await _send_profile(message, user)


@router.callback_query(F.data.startswith("pgender:"))
async def profile_gender_set(call: CallbackQuery, state: FSMContext):
    user = await db.get_user(call.from_user.id)
    left = edit_cooldown_left(user) if user else None
    if left is not None:
        await call.answer(cooldown_msg(left), show_alert=True)
        return
    gender = call.data.split(":")[1]
    await db.update_user_field(call.from_user.id, "gender", gender)
    await state.clear()
    await call.answer("Yangilandi.")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    user = await db.get_user(call.from_user.id)
    await _send_profile(call.message, user)


@router.message(ProfileEdit.waiting_value, F.photo)
async def profile_edit_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("field") != "photo":
        return
    user = await db.get_user(message.from_user.id)
    left = edit_cooldown_left(user) if user else None
    if left is not None:
        await state.clear()
        await message.answer(cooldown_msg(left))
        return
    file_id = message.photo[-1].file_id
    await db.update_user_field(message.from_user.id, "photo_file_id", file_id)
    await _finish_edit(message, state)


@router.message(ProfileEdit.waiting_value, F.text)
async def profile_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("field")
    val = message.text.strip()

    user = await db.get_user(message.from_user.id)
    left = edit_cooldown_left(user) if user else None
    if left is not None:
        await state.clear()
        await message.answer(cooldown_msg(left))
        return

    if field == "photo":
        await message.answer("Iltimos, rasmni surat (foto) ko'rinishida yuboring 📸")
        return

    if field == "name":
        res = split_name(val)
        if res is None:
            await message.answer("Ism va familiyani birga kiriting.\n"
                                 "Masalan: <code>Aziz Azizov</code>")
            return
        first, last = res
        # ikkala maydonni ham yangilaymiz, cooldownni bir marta belgilaymiz
        await db.update_user_field(message.from_user.id, "first_name", first, touch_edit=False)
        await db.update_user_field(message.from_user.id, "last_name", last, touch_edit=False)
        await db.update_user_field(message.from_user.id, "full_name",
                                   f"{first} {last}", touch_edit=True)

    elif field == "birth_date":
        d = parse_birth_date(val)
        if d is None:
            await message.answer("❌ Noto'g'ri format. <code>kun.oy.yil</code> ko'rinishida kiriting.\n"
                                 "Masalan: <code>05.09.1998</code>")
            return
        await db.update_user_field(message.from_user.id, "birth_date", d.strftime("%d.%m.%Y"))

    elif field == "experience_years":
        if not val.isdigit() or int(val) > 80:
            await message.answer("Ish stajini yil hisobida son bilan kiriting (masalan: 5):")
            return
        await db.update_user_field(message.from_user.id, "experience_years", int(val))

    else:
        await message.answer("Noma'lum maydon.")
        await state.clear()
        return

    await _finish_edit(message, state)


# ==================== TEST ====================
@router.message(F.text == "📝 Testni boshlash")
async def start_test_list(message: Message):
    await _register(message)
    tests = await _available_tests(message.from_user.id)
    if not tests:
        await message.answer("ℹ️ Hozircha siz uchun mavjud test yo'q.",
                             reply_markup=kb.employee_menu(False))
        return

    for t in tests:
        q_count = await db.count_questions(t["id"])
        n = min(t["questions_per_test"], q_count)
        info = (
            f"📋 <b>{t['title']}</b>\n\n"
            f"Savollar soni: {n} ta\n"
            f"⏱ Har bir savol: {t['time_per_question']} soniya\n"
            f"🎯 O'tish bali: {t['pass_percent']}%\n\n"
            "Testni boshlashga tayyormisiz?"
        )
        await message.answer(info, reply_markup=kb.start_test_kb(t["id"]))


@router.message(F.text == "📊 Mening natijalarim")
async def my_results(message: Message):
    await _register(message)
    rows = await db.user_results(message.from_user.id)
    if not rows:
        await message.answer("Sizda hali natijalar yo'q.")
        return
    lines = ["📊 <b>Mening natijalarim</b>\n"]
    for r in rows[:20]:
        icon = "🟢" if r["passed"] else "🔴"
        lines.append(f"{icon} {r['title']} — {r['percent']}% ({r['created_at']})")
    await message.answer("\n".join(lines))
