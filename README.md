# 🤖 Xodimlar Test Boti (DoriKent)

Xodimlar uchun Telegram test boti. Admin Excel orqali savollar yuklaydi,
noto'g'ri javob variantlarini **AI (Gemini / ChatGPT)** yoki **AI-siz generator**
avtomatik yaratadi. Xodimlar botda test topshiradi, natijalar saqlanadi.

Python + SQLite + aiogram 3. Real, to'liq ishlaydigan mahsulot (MVP emas).

---

## ✨ Imkoniyatlar

**Xodim uchun:**
- `/start` → xush kelibsiz + tayinlangan testlar
- Random savollar, random variantlar, har savolga vaqt (taymer)
- Test yakunida natija: to'g'ri/noto'g'ri, foiz, o'tdi/o'tmadi
- «📊 Mening natijalarim»

**Admin uchun:**
- 📥 **Excel yuklash** — savollarni fayldan yuklash (savol + to'g'ri javob)
- 📄 **Shablon olish** — tayyor Excel namunasi
- 🤖 **AI** noto'g'ri variantlarni avtomatik yaratadi
- 📝 **Testlar** — ko'rish / tahrirlash / o'chirish / faollashtirish / to'xtatish
- 👥 **Xodimlar** — har birining statistikasi
- 📊 **Natijalar** — ro'yxat + Excel eksport
- 📤 **Test yuborish** — testni tanlab, xodimlarga jo'natish
- ⚙️ **Sozlamalar** — savollar soni, o'tish bali, vaqt, qayta topshirish va h.k.

**AI mantiqi (talab qilinganidek):**
1. Avval **Gemini** sinaladi (kalit bo'lsa)
2. Ishlamasa **OpenAI / ChatGPT** sinaladi (kalit bo'lsa)
3. Ikkalasi ham ishlamasa/ulanmagan bo'lsa → **AI-siz generator** (har doim ishlaydi)

Tartibni `.env` dagi `AI_ORDER` bilan boshqarasiz.

---

## 🚀 O'rnatish va ishga tushirish

### 1. Kutubxonalar
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Sozlash — `.env` fayl
`.env.example` dan nusxa oling va to'ldiring:
```powershell
copy .env.example .env
```
Kerakli qiymatlar:
- `BOT_TOKEN` — @BotFather dan
- `ADMIN_IDS` — admin Telegram ID (@userinfobot dan)
- `GEMINI_API_KEY` va/yoki `OPENAI_API_KEY` — ixtiyoriy (bo'sh bo'lsa AI-siz ishlaydi)

### 3. Ishga tushirish
```powershell
python bot.py
```
Ishga tushganda: `Bot ishga tushdi: @sizning_bot` deb yozadi.

> ⚠️ Bitta bot tokeni faqat **bitta joyda** ishga tushishi kerak.
> `Conflict: terminated by other getUpdates` xatosi — bot boshqa joyda ham
> ishlab turgani (masalan eski oyna) degani. Eskisini to'xtating.

---

## 📄 Excel shablon formati

| Savol | To'g'ri javob | Noto'g'ri 1 | Noto'g'ri 2 | Noto'g'ri 3 |
|-------|---------------|-------------|-------------|-------------|
| Savol matni | To'g'ri javob | (ixtiyoriy) | (ixtiyoriy) | (ixtiyoriy) |

- **1 va 2-ustun majburiy.** 3–5-ustun bo'sh bo'lsa — AI (yoki AI-siz generator)
  noto'g'ri variantlarni o'zi yaratadi.
- Botdan «📄 Shablon olish» tugmasi orqali tayyor namunani yuklab olasiz.

---

## 🗂 Loyiha tuzilishi

```
bot.py             — ishga tushirish
config.py          — .env sozlamalari
db.py              — SQLite (users, tests, questions, options, results, ...)
ai_service.py      — Gemini + OpenAI + AI-siz generator (fallback)
excel_service.py   — shablon yaratish, o'qish, natijalar eksporti
keyboards.py       — barcha tugmalar
states.py          — FSM holatlar
test_session.py    — test topshirish sessiyasi (taymer, random)
handlers/
  employee.py      — xodim: /start, test, natijalar
  test_taking.py   — test boshlash va javob berish
  admin.py         — admin panel (barcha bo'limlar)
```

Ma'lumotlar `bot.db` (SQLite) faylida saqlanadi.

---

## 🔐 Xavfsizlik
- `.env` va `*.db` fayllar `.gitignore` da — commit qilinmaydi.
- API kalitlaringizni hech kimga bermang.

---

## ❓ Tez-tez uchraydigan holatlar
- **AI ishlamayapti / offline chiqyapti** — kalit noto'g'ri, kvota tugagan yoki
  internet yo'q. Bot avtomatik AI-siz generatorga o'tadi, test baribir ishlaydi.
- **OpenAI 429 / quota** — OpenAI hisobingizda balans yo'q. Gemini yoki offline ishlaydi.
- **Gemini 429 (free tier 5/min)** — bepul limit. Ko'p savol yuklasangiz bir qismi
  offline yaratiladi. To'liq tezlik uchun pullik reja kerak.
