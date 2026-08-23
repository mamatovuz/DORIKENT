"""
Noto'g'ri javob variantlarini yaratish xizmati.

Tartib:
  1) Gemini (agar API key bo'lsa)
  2) OpenAI / ChatGPT (agar API key bo'lsa)
  3) AI-siz offline generator (har doim ishlaydi)

AI_ORDER orqali qaysi biri birinchi sinalishini boshqarish mumkin.
Biri ishlamasa avtomatik ikkinchisiga, u ham bo'lmasa offline generatorga o'tadi.
"""
import asyncio
import json
import logging
import random
import re

import config
import db

log = logging.getLogger("ai_service")


async def get_keys() -> tuple[str, str]:
    """(gemini_key, openai_key) — avval admin panel sozlamasi, keyin .env."""
    gem = await db.get_setting("gemini_api_key") or config.GEMINI_API_KEY
    oai = await db.get_setting("openai_api_key") or config.OPENAI_API_KEY
    return (gem or "").strip(), (oai or "").strip()

_PROMPT = (
    "Sen test tuzuvchi yordamchisan. Berilgan savol va uning TO'G'RI javobiga asoslanib, "
    "aynan 3 ta ISHONARLI, lekin NOTO'G'RI javob varianti yarat. "
    "Variantlar o'zbek tilida, qisqa va to'g'ri javob bilan bir uslubda bo'lsin. "
    "To'g'ri javobni takrorlama. Faqat JSON massiv qaytar, boshqa matn yozma. "
    'Masalan: ["variant1", "variant2", "variant3"]\n\n'
    "Savol: {question}\n"
    "To'g'ri javob: {correct}"
)


def _parse_list(raw: str) -> list[str]:
    """AI matnidan 3 ta variantni ajratib oladi."""
    raw = raw.strip()
    # kod bloklarini tozalash
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        pass
    # JSON bo'lmasa qatorlarga bo'lib olamiz
    lines = []
    for ln in raw.splitlines():
        ln = re.sub(r'^\s*[\d\.\)\-\*"]+\s*', "", ln).strip().strip('"')
        if ln:
            lines.append(ln)
    return lines


# ---------------- GEMINI ----------------
async def _gemini(question: str, correct: str) -> list[str]:
    import google.generativeai as genai

    gem, _ = await get_keys()
    genai.configure(api_key=gem)
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    prompt = _PROMPT.format(question=question, correct=correct)

    def _call():
        resp = model.generate_content(prompt)
        return resp.text or ""

    text = await asyncio.to_thread(_call)
    return _parse_list(text)


# ---------------- OPENAI ----------------
async def _openai(question: str, correct: str) -> list[str]:
    from openai import AsyncOpenAI

    _, oai = await get_keys()
    client = AsyncOpenAI(api_key=oai)
    prompt = _PROMPT.format(question=question, correct=correct)
    resp = await client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    text = resp.choices[0].message.content or ""
    return _parse_list(text)


# ---------------- OFFLINE ----------------
_GENERIC = [
    "Bu javob noto'g'ri",
    "Hech qanday chora ko'rmaslik",
    "Muammoni e'tiborsiz qoldirish",
    "Boshqa xodimga yuklab qo'yish",
    "Qoidaga rioya qilmaslik",
    "Faqat qisqa va rasmiy javob berish",
    "Kechiktirib, keyinroq hal qilish",
    "O'z bilganicha ish tutish",
]


def _offline(question: str, correct: str, pool: list[str] | None = None) -> list[str]:
    """AI-siz distraktorlar. Boshqa savollarning to'g'ri javoblaridan (pool) foydalanadi."""
    result: list[str] = []
    if pool:
        candidates = [p for p in pool if p and p.strip().lower() != correct.strip().lower()]
        random.shuffle(candidates)
        for c in candidates:
            if c not in result:
                result.append(c)
            if len(result) >= 3:
                break
    i = 0
    generic = _GENERIC[:]
    random.shuffle(generic)
    while len(result) < 3 and i < len(generic):
        if generic[i].lower() != correct.strip().lower() and generic[i] not in result:
            result.append(generic[i])
        i += 1
    return result[:3]


async def generate_wrong_answers(question: str, correct: str,
                                 pool: list[str] | None = None) -> tuple[list[str], str]:
    """
    3 ta noto'g'ri variant qaytaradi.
    Qaytadi: (variantlar, ishlatilgan_manba)  manba: gemini|openai|offline
    """
    gem, oai = await get_keys()
    providers = {
        "gemini": (_gemini, bool(gem)),
        "openai": (_openai, bool(oai)),
    }
    for name in config.AI_ORDER:
        func, enabled = providers.get(name, (None, False))
        if not func or not enabled:
            continue
        try:
            wrongs = await asyncio.wait_for(func(question, correct), timeout=30)
            wrongs = [w for w in wrongs if w.strip().lower() != correct.strip().lower()]
            if len(wrongs) >= 3:
                return wrongs[:3], name
            if wrongs:  # qisman — to'ldiramiz
                extra = _offline(question, correct, pool)
                merged = wrongs + [e for e in extra if e not in wrongs]
                return merged[:3], name
        except Exception as e:  # noqa
            log.warning("AI (%s) xato berdi: %s — keyingisiga o'tilyapti", name, e)
            continue
    return _offline(question, correct, pool), "offline"


async def ai_status() -> str:
    gem, oai = await get_keys()
    parts = []
    parts.append(f"Gemini: {'✅ ulangan' if gem else '❌ yo`q'}")
    parts.append(f"OpenAI (ChatGPT): {'✅ ulangan' if oai else '❌ yo`q'}")
    if not gem and not oai:
        parts.append("Rejim: 🔧 AI-siz (offline) generator")
    return "\n".join(parts)
