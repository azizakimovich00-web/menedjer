import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import load_settings
from app.db.database import Database, init_db
from app.db.repository import Repository
from app.handlers import accountant, common, director, employee, manager
from app.services.scheduler import create_scheduler


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings = load_settings()
    os.makedirs(settings.exports_dir, exist_ok=True)

    db = Database(
        settings.database_url,
        min_pool_size=settings.db_pool_min_size,
        max_pool_size=settings.db_pool_max_size,
        connect_retries=settings.db_connect_retries,
    )
    await init_db(db)
    repo = Repository(db)

    bot = Bot(token=settings.bot_token)
    bot.repo = repo
    bot.settings = settings
    bot.exports_dir = settings.exports_dir

    dp = Dispatcher(storage=MemoryStorage())
    from aiogram import F

    dp.message.filter(F.chat.type == "private")
    dp.include_router(common.router)
    dp.include_router(director.router)
    dp.include_router(accountant.router)
    dp.include_router(manager.router)
    dp.include_router(employee.router)

    scheduler = create_scheduler(bot, repo)
    scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
