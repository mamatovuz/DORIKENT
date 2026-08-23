"""Xodimlar test boti — asosiy ishga tushirish fayli."""
import asyncio
import logging
import sys

# Windows konsolida emoji/kirill harflar xatosiz chiqishi uchun
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
from handlers import employee_router, test_taking_router, admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("bot")


async def main():
    if not config.BOT_TOKEN:
        print("❌ BOT_TOKEN topilmadi. .env faylini to'ldiring (.env.example dan nusxa oling).")
        sys.exit(1)
    if not config.ADMIN_IDS:
        log.warning("⚠️ ADMIN_IDS bo'sh. Admin panelga kirish uchun .env da ID qo'shing.")

    await db.init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Tartib: admin (filtrli) -> employee -> test topshirish
    dp.include_router(admin_router)
    dp.include_router(employee_router)
    dp.include_router(test_taking_router)

    me = await bot.get_me()
    log.info("Bot ishga tushdi: @%s", me.username)
    import ai_service
    log.info("AI: %s", " | ".join((await ai_service.ai_status()).splitlines()))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot to'xtatildi.")
