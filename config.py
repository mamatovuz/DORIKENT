"""Loyihaning markaziy konfiguratsiyasi. .env fayldan o'qiladi."""
import os
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().isdigit()
}

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
AI_ORDER = [x.strip().lower() for x in os.getenv("AI_ORDER", "gemini,openai").split(",") if x.strip()]

# AI modellari (kerak bo'lsa .env dan o'zgartiriladi)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

# Default test sozlamalari (admin har bir test uchun o'zgartira oladi)
DEFAULT_QUESTIONS_PER_TEST = _int("DEFAULT_QUESTIONS_PER_TEST", 20)
DEFAULT_PASS_PERCENT = _int("DEFAULT_PASS_PERCENT", 70)
DEFAULT_TIME_PER_QUESTION = _int("DEFAULT_TIME_PER_QUESTION", 30)
DEFAULT_ALLOW_RETAKE = _int("DEFAULT_ALLOW_RETAKE", 1)
DEFAULT_SHOW_RESULT = _int("DEFAULT_SHOW_RESULT", 1)

DB_PATH = os.getenv("DB_PATH", "bot.db")

# Agar DB_PATH papka ichida bo'lsa (masalan Railway volume: /data/bot.db),
# o'sha papkani avtomatik yaratamiz.
_db_dir = os.path.dirname(DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
