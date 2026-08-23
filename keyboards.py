"""Barcha tugmalar (klaviaturalar)."""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)


# ---------- REPLY (asosiy menyular) ----------
def employee_menu(has_test: bool = True) -> ReplyKeyboardMarkup:
    # «Testni boshlash» doim ko'rinadi — admin test faollashtirsa darhol foydalanish uchun.
    rows = [
        [KeyboardButton(text="📝 Testni boshlash")],
        [KeyboardButton(text="👤 Mening profilim"),
         KeyboardButton(text="📊 Mening natijalarim")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def gender_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👨 Erkak", callback_data="gender:Erkak"),
        InlineKeyboardButton(text="👩 Ayol", callback_data="gender:Ayol"),
    ]])


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="pedit")]
    ])


def profile_edit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Ism-familiya", callback_data="pf:name")],
        [InlineKeyboardButton(text="⚧ Jinsi", callback_data="pf:gender")],
        [InlineKeyboardButton(text="🎂 Tug'ilgan kun", callback_data="pf:birth_date")],
        [InlineKeyboardButton(text="💼 Ish staji", callback_data="pf:experience_years")],
        [InlineKeyboardButton(text="🖼 Rasm", callback_data="pf:photo")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="pf_back")],
    ])


def pedit_gender_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👨 Erkak", callback_data="pgender:Erkak"),
        InlineKeyboardButton(text="👩 Ayol", callback_data="pgender:Ayol"),
    ]])


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Excel yuklash"), KeyboardButton(text="📄 Shablon olish")],
            [KeyboardButton(text="📝 Testlar"), KeyboardButton(text="👥 Xodimlar")],
            [KeyboardButton(text="📊 Natijalar"), KeyboardButton(text="📤 Test yuborish")],
            [KeyboardButton(text="⚙️ Sozlamalar"), KeyboardButton(text="🤖 AI holati")],
            [KeyboardButton(text="👑 Adminlar"), KeyboardButton(text="📖 Qo'llanma")],
        ],
        resize_keyboard=True,
    )


def admins_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ID orqali", callback_data="addadm:id")],
        [InlineKeyboardButton(text="➕ Username orqali", callback_data="addadm:username")],
        [InlineKeyboardButton(text="➕ Telefon (kontakt) orqali", callback_data="addadm:phone")],
    ])


# ---------- INLINE ----------
def start_test_kb(test_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Boshlash", callback_data=f"begin:{test_id}")]
    ])


def tests_list_kb(tests) -> InlineKeyboardMarkup:
    rows = []
    for t in tests:
        status = "🟢" if t["is_active"] else "⚪️"
        rows.append([InlineKeyboardButton(
            text=f"{status} {t['title']}", callback_data=f"test:{t['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(
        text="—", callback_data="noop")]])


def test_manage_kb(test) -> InlineKeyboardMarkup:
    tid = test["id"]
    toggle = ("⏸ To'xtatish", f"toggle:{tid}") if test["is_active"] else ("▶️ Faollashtirish", f"toggle:{tid}")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit:{tid}"),
         InlineKeyboardButton(text="👁 Ko'rish", callback_data=f"view:{tid}")],
        [InlineKeyboardButton(text=toggle[0], callback_data=toggle[1]),
         InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del:{tid}")],
        [InlineKeyboardButton(text="📤 Xodimlarga yuborish", callback_data=f"assign:{tid}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="tests_back")],
    ])


def edit_fields_kb(tid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Nomi", callback_data=f"ef:{tid}:title")],
        [InlineKeyboardButton(text="Savollar soni", callback_data=f"ef:{tid}:questions_per_test")],
        [InlineKeyboardButton(text="O'tish bali (%)", callback_data=f"ef:{tid}:pass_percent")],
        [InlineKeyboardButton(text="Savolga vaqt (soniya)", callback_data=f"ef:{tid}:time_per_question")],
        [InlineKeyboardButton(text="Qayta topshirish", callback_data=f"ef:{tid}:allow_retake")],
        [InlineKeyboardButton(text="Natijani ko'rsatish", callback_data=f"ef:{tid}:show_result")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"test:{tid}")],
    ])


def confirm_upload_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 Ko'rish", callback_data="up_view"),
         InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="up_confirm")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="up_cancel")],
    ])


def question_kb(options, prefix: str = "ans") -> InlineKeyboardMarkup:
    """Test savoli variantlari. options: [(idx, text)]"""
    rows = [[InlineKeyboardButton(text=text, callback_data=f"{prefix}:{idx}")]
            for idx, text in options]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def users_pick_kb(users, selected: set, test_id: int) -> InlineKeyboardMarkup:
    rows = []
    rows.append([InlineKeyboardButton(text="✅ Hammasini tanlash", callback_data="pick_all")])
    for u in users:
        mark = "☑️" if u["telegram_id"] in selected else "⬜️"
        name = u["full_name"] or str(u["telegram_id"])
        rows.append([InlineKeyboardButton(
            text=f"{mark} {name}", callback_data=f"pick:{u['telegram_id']}"
        )])
    rows.append([InlineKeyboardButton(text="🚀 Yuborish", callback_data="pick_send"),
                 InlineKeyboardButton(text="❌ Bekor", callback_data="pick_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_kb(s: dict) -> InlineKeyboardMarkup:
    retake = "✅ Ruxsat" if s.get("allow_retake") == "1" else "❌ Yo'q"
    show = "✅ Ha" if s.get("show_result") == "1" else "❌ Yo'q"
    gem = "✅ kiritilgan" if (s.get("gemini_api_key") or "").strip() else "❌ yo'q"
    oai = "✅ kiritilgan" if (s.get("openai_api_key") or "").strip() else "❌ yo'q"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Savollar soni: {s.get('questions_per_test')}",
                              callback_data="set:questions_per_test")],
        [InlineKeyboardButton(text=f"O'tish bali: {s.get('pass_percent')}%",
                              callback_data="set:pass_percent")],
        [InlineKeyboardButton(text=f"Savolga vaqt: {s.get('time_per_question')} soniya",
                              callback_data="set:time_per_question")],
        [InlineKeyboardButton(text=f"Qayta topshirish: {retake}",
                              callback_data="set:allow_retake")],
        [InlineKeyboardButton(text=f"Natijani ko'rsatish: {show}",
                              callback_data="set:show_result")],
        [InlineKeyboardButton(text=f"🤖 Gemini API kaliti: {gem}",
                              callback_data="set:gemini_api_key")],
        [InlineKeyboardButton(text=f"🤖 ChatGPT (OpenAI) API kaliti: {oai}",
                              callback_data="set:openai_api_key")],
    ])


def users_list_kb(users) -> InlineKeyboardMarkup:
    rows = []
    for u in users:
        name = u["full_name"] or str(u["telegram_id"])
        rows.append([InlineKeyboardButton(text=f"👤 {name}",
                                          callback_data=f"emp:{u['telegram_id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(
        text="Xodimlar yo'q", callback_data="noop")]])
