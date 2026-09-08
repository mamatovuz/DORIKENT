"""SQLite ma'lumotlar bazasi qatlami (aiosqlite bilan)."""
import os
import shutil
import logging
import aiosqlite
from datetime import datetime
from typing import Optional

import config

log = logging.getLogger("db")

_db: Optional[aiosqlite.Connection] = None


def _seed_if_needed() -> None:
    """Railway (yoki boshqa) volume birinchi marta bo'sh bo'lsa, seed.db dan
    ma'lumotlarni ko'chiradi. Agar DB_PATH allaqachon mavjud bo'lsa — tegmaydi,
    ya'ni jonli ma'lumotlar hech qachon ustidan yozilmaydi."""
    target = config.DB_PATH
    seed = os.path.join(os.path.dirname(__file__), "seed.db")
    if os.path.exists(target):
        return  # jonli baza bor — hech narsa qilmaymiz
    if not os.path.exists(seed):
        return  # seed yo'q — bo'sh bazadan boshlanadi
    shutil.copyfile(seed, target)
    log.info("Seed ma'lumotlar ko'chirildi: %s -> %s", seed, target)


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(config.DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA foreign_keys = ON;")
    return _db


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id      INTEGER PRIMARY KEY,
    full_name        TEXT,
    username         TEXT,
    role             TEXT DEFAULT 'employee',   -- employee | admin
    first_name       TEXT,
    last_name        TEXT,
    gender           TEXT,                       -- Erkak | Ayol
    birth_date       TEXT,                       -- kun.oy.yil (dd.mm.yyyy)
    experience_years INTEGER,
    photo_file_id    TEXT,
    is_registered    INTEGER NOT NULL DEFAULT 0,
    last_profile_edit TEXT,
    created_at       TEXT
);

CREATE TABLE IF NOT EXISTS tests (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    title              TEXT NOT NULL,
    questions_per_test INTEGER NOT NULL,
    pass_percent       INTEGER NOT NULL,
    time_per_question  INTEGER NOT NULL,
    allow_retake       INTEGER NOT NULL DEFAULT 1,
    show_result        INTEGER NOT NULL DEFAULT 1,
    is_active          INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT
);

CREATE TABLE IF NOT EXISTS questions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id    INTEGER NOT NULL,
    text       TEXT NOT NULL,
    created_at TEXT,
    FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS options (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    text        TEXT NOT NULL,
    is_correct  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS assignments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    status     TEXT DEFAULT 'assigned',  -- assigned | done
    created_at TEXT,
    UNIQUE (test_id, user_id),
    FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    test_id    INTEGER NOT NULL,
    total      INTEGER NOT NULL,
    correct    INTEGER NOT NULL,
    wrong      INTEGER NOT NULL,
    percent    REAL NOT NULL,
    passed     INTEGER NOT NULL,
    created_at TEXT,
    FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


async def _migrate(db):
    """Eski bot.db uchun yetishmayotgan ustunlarni qo'shadi."""
    async with db.execute("PRAGMA table_info(users)") as cur:
        cols = {r["name"] for r in await cur.fetchall()}
    add = {
        "first_name": "TEXT",
        "last_name": "TEXT",
        "gender": "TEXT",
        "birth_date": "TEXT",
        "experience_years": "INTEGER",
        "photo_file_id": "TEXT",
        "is_registered": "INTEGER NOT NULL DEFAULT 0",
        "last_profile_edit": "TEXT",
    }
    for name, ddl in add.items():
        if name not in cols:
            await db.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
    await db.commit()


async def init_db():
    _seed_if_needed()
    db = await get_db()
    await db.executescript(SCHEMA)
    await db.commit()
    await _migrate(db)
    # Global default sozlamalar
    defaults = {
        "questions_per_test": config.DEFAULT_QUESTIONS_PER_TEST,
        "pass_percent": config.DEFAULT_PASS_PERCENT,
        "time_per_question": config.DEFAULT_TIME_PER_QUESTION,
        "allow_retake": config.DEFAULT_ALLOW_RETAKE,
        "show_result": config.DEFAULT_SHOW_RESULT,
        "gemini_api_key": config.GEMINI_API_KEY,
        "openai_api_key": config.OPENAI_API_KEY,
    }
    for k, v in defaults.items():
        await db.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, str(v))
        )
    await db.commit()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- USERS ----------
async def upsert_user(telegram_id: int, full_name: str, username: str, role: str = "employee"):
    db = await get_db()
    async with db.execute(
        "SELECT role, is_registered FROM users WHERE telegram_id=?", (telegram_id,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        await db.execute(
            "INSERT INTO users(telegram_id, full_name, username, role, created_at) VALUES(?,?,?,?,?)",
            (telegram_id, full_name, username, role, _now()),
        )
    else:
        # rolni admin qilib qo'ygan bo'lsak, uni employee ga tushirmaymiz
        keep_role = row["role"] if row["role"] == "admin" else role
        # ro'yxatdan o'tgan xodimning full_name'ini telegram nomi bilan almashtirmaymiz
        if row["is_registered"]:
            await db.execute(
                "UPDATE users SET username=?, role=? WHERE telegram_id=?",
                (username, keep_role, telegram_id),
            )
        else:
            await db.execute(
                "UPDATE users SET full_name=?, username=?, role=? WHERE telegram_id=?",
                (full_name, username, keep_role, telegram_id),
            )
    await db.commit()


async def is_user_registered(telegram_id: int) -> bool:
    db = await get_db()
    async with db.execute(
        "SELECT is_registered FROM users WHERE telegram_id=?", (telegram_id,)
    ) as cur:
        row = await cur.fetchone()
        return bool(row and row["is_registered"])


async def register_user(telegram_id: int, first_name: str, last_name: str, gender: str,
                        birth_date: str, experience_years: int, photo_file_id: str):
    """Xodim profilini to'ldiradi va ro'yxatdan o'tkazadi."""
    db = await get_db()
    full_name = f"{first_name} {last_name}".strip()
    await db.execute(
        """UPDATE users SET first_name=?, last_name=?, gender=?, birth_date=?,
               experience_years=?, photo_file_id=?, full_name=?, is_registered=1
           WHERE telegram_id=?""",
        (first_name, last_name, gender, birth_date, experience_years,
         photo_file_id, full_name, telegram_id),
    )
    await db.commit()


async def update_user_field(telegram_id: int, field: str, value, touch_edit: bool = True):
    """Profil maydonini yangilaydi va (default) tahrirlash vaqtini belgilaydi."""
    allowed = {"first_name", "last_name", "gender", "birth_date",
               "experience_years", "photo_file_id", "full_name"}
    if field not in allowed:
        raise ValueError("Ruxsat etilmagan maydon")
    db = await get_db()
    if touch_edit:
        await db.execute(
            f"UPDATE users SET {field}=?, last_profile_edit=? WHERE telegram_id=?",
            (value, _now(), telegram_id),
        )
    else:
        await db.execute(
            f"UPDATE users SET {field}=? WHERE telegram_id=?", (value, telegram_id)
        )
    await db.commit()


async def set_user_role(telegram_id: int, role: str):
    db = await get_db()
    await db.execute("UPDATE users SET role=? WHERE telegram_id=?", (role, telegram_id))
    await db.commit()


async def is_admin_user(telegram_id: int) -> bool:
    """DB dagi roli admin bo'lgan foydalanuvchimi (panel orqali qo'shilgan)."""
    db = await get_db()
    async with db.execute("SELECT role FROM users WHERE telegram_id=?", (telegram_id,)) as cur:
        row = await cur.fetchone()
        return bool(row and row["role"] == "admin")


async def make_admin(telegram_id: int, full_name: str = "", username: str = ""):
    """Foydalanuvchini admin qiladi. Bazada bo'lmasa, yozuv yaratadi."""
    db = await get_db()
    async with db.execute("SELECT telegram_id FROM users WHERE telegram_id=?", (telegram_id,)) as cur:
        exists = await cur.fetchone()
    if exists:
        await db.execute("UPDATE users SET role='admin' WHERE telegram_id=?", (telegram_id,))
    else:
        await db.execute(
            "INSERT INTO users(telegram_id, full_name, username, role, created_at) VALUES(?,?,?,'admin',?)",
            (telegram_id, full_name, username, _now()),
        )
    await db.commit()


async def list_admins():
    db = await get_db()
    async with db.execute(
        "SELECT * FROM users WHERE role='admin' ORDER BY full_name"
    ) as cur:
        return await cur.fetchall()


async def get_user(telegram_id: int):
    db = await get_db()
    async with db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)) as cur:
        return await cur.fetchone()


async def list_users(role: str = "employee"):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM users WHERE role=? ORDER BY full_name", (role,)
    ) as cur:
        return await cur.fetchall()


# ---------- TESTS ----------
async def create_test(title: str, qpt: int, pass_percent: int, tpq: int,
                      allow_retake: int, show_result: int) -> int:
    db = await get_db()
    cur = await db.execute(
        """INSERT INTO tests(title, questions_per_test, pass_percent, time_per_question,
           allow_retake, show_result, is_active, created_at)
           VALUES(?,?,?,?,?,?,0,?)""",
        (title, qpt, pass_percent, tpq, allow_retake, show_result, _now()),
    )
    await db.commit()
    return cur.lastrowid


async def get_test(test_id: int):
    db = await get_db()
    async with db.execute("SELECT * FROM tests WHERE id=?", (test_id,)) as cur:
        return await cur.fetchone()


async def list_tests():
    db = await get_db()
    async with db.execute("SELECT * FROM tests ORDER BY id DESC") as cur:
        return await cur.fetchall()


async def get_active_tests():
    """Barcha faol testlar — ro'yxatdan o'tgan har bir xodimga ochiq."""
    db = await get_db()
    async with db.execute(
        "SELECT * FROM tests WHERE is_active=1 ORDER BY id DESC"
    ) as cur:
        return await cur.fetchall()


async def update_test_field(test_id: int, field: str, value):
    allowed = {"title", "questions_per_test", "pass_percent", "time_per_question",
               "allow_retake", "show_result", "is_active"}
    if field not in allowed:
        raise ValueError("Ruxsat etilmagan maydon")
    db = await get_db()
    await db.execute(f"UPDATE tests SET {field}=? WHERE id=?", (value, test_id))
    await db.commit()


async def delete_test(test_id: int):
    db = await get_db()
    await db.execute("DELETE FROM tests WHERE id=?", (test_id,))
    await db.commit()


async def count_questions(test_id: int) -> int:
    db = await get_db()
    async with db.execute("SELECT COUNT(*) c FROM questions WHERE test_id=?", (test_id,)) as cur:
        row = await cur.fetchone()
        return row["c"]


# ---------- QUESTIONS & OPTIONS ----------
async def add_question(test_id: int, text: str, correct: str, wrongs: list[str]) -> int:
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO questions(test_id, text, created_at) VALUES(?,?,?)",
        (test_id, text, _now()),
    )
    qid = cur.lastrowid
    await db.execute(
        "INSERT INTO options(question_id, text, is_correct) VALUES(?,?,1)", (qid, correct)
    )
    for w in wrongs:
        if w and w.strip():
            await db.execute(
                "INSERT INTO options(question_id, text, is_correct) VALUES(?,?,0)", (qid, w.strip())
            )
    await db.commit()
    return qid


async def get_questions(test_id: int):
    db = await get_db()
    async with db.execute("SELECT * FROM questions WHERE test_id=? ORDER BY id", (test_id,)) as cur:
        return await cur.fetchall()


async def get_options(question_id: int):
    db = await get_db()
    async with db.execute("SELECT * FROM options WHERE question_id=?", (question_id,)) as cur:
        return await cur.fetchall()


async def clear_questions(test_id: int):
    db = await get_db()
    await db.execute("DELETE FROM questions WHERE test_id=?", (test_id,))
    await db.commit()


# ---------- ASSIGNMENTS ----------
async def assign_test(test_id: int, user_id: int):
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO assignments(test_id, user_id, status, created_at) VALUES(?,?, 'assigned', ?)",
        (test_id, user_id, _now()),
    )
    await db.commit()


async def get_assignments_for_user(user_id: int):
    """Xodimga tayinlangan VA faol testlar."""
    db = await get_db()
    async with db.execute(
        """SELECT t.* FROM assignments a
           JOIN tests t ON t.id = a.test_id
           WHERE a.user_id=? AND t.is_active=1
           ORDER BY a.created_at DESC""",
        (user_id,),
    ) as cur:
        return await cur.fetchall()


async def mark_assignment_done(test_id: int, user_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE assignments SET status='done' WHERE test_id=? AND user_id=?", (test_id, user_id)
    )
    await db.commit()


# ---------- RESULTS ----------
async def save_result(user_id: int, test_id: int, total: int, correct: int,
                      wrong: int, percent: float, passed: int) -> int:
    db = await get_db()
    cur = await db.execute(
        """INSERT INTO results(user_id, test_id, total, correct, wrong, percent, passed, created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (user_id, test_id, total, correct, wrong, percent, passed, _now()),
    )
    await db.commit()
    return cur.lastrowid


async def user_results(user_id: int):
    db = await get_db()
    async with db.execute(
        """SELECT r.*, t.title FROM results r
           JOIN tests t ON t.id=r.test_id
           WHERE r.user_id=? ORDER BY r.created_at DESC""",
        (user_id,),
    ) as cur:
        return await cur.fetchall()


async def user_test_attempts(user_id: int, test_id: int) -> int:
    db = await get_db()
    async with db.execute(
        "SELECT COUNT(*) c FROM results WHERE user_id=? AND test_id=?", (user_id, test_id)
    ) as cur:
        row = await cur.fetchone()
        return row["c"]


async def all_results():
    db = await get_db()
    async with db.execute(
        """SELECT r.*, t.title, u.full_name, u.username
           FROM results r
           JOIN tests t ON t.id=r.test_id
           JOIN users u ON u.telegram_id=r.user_id
           ORDER BY r.created_at DESC""",
    ) as cur:
        return await cur.fetchall()


async def user_stats(user_id: int):
    db = await get_db()
    async with db.execute(
        """SELECT COUNT(*) attempts,
                  AVG(percent) avg_percent,
                  SUM(passed) passed_count
           FROM results WHERE user_id=?""",
        (user_id,),
    ) as cur:
        return await cur.fetchone()


# ---------- SETTINGS ----------
async def get_setting(key: str, default=None):
    db = await get_db()
    async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
        row = await cur.fetchone()
        return row["value"] if row else default


async def set_setting(key: str, value):
    db = await get_db()
    await db.execute(
        "INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    await db.commit()


async def all_settings() -> dict:
    db = await get_db()
    async with db.execute("SELECT key, value FROM settings") as cur:
        rows = await cur.fetchall()
        return {r["key"]: r["value"] for r in rows}
