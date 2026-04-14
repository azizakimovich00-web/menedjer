from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.repository import Repository


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _in_reminder_window(now: datetime) -> bool:
    return 7 <= now.hour <= 20


def create_scheduler(bot, repo: Repository) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Almaty")

    async def notify_tasks_hourly():
        now = datetime.now()
        if not _in_reminder_window(now):
            return
        today = _date_str(now)
        users = await repo.db.fetchall("SELECT * FROM users")
        for user in users:
            tasks = await repo.list_tasks_for_user_on_date(int(user["id"]), today)
            if not tasks:
                continue
            lines = ["Ваши задачи на сегодня:"]
            for t in tasks:
                lines.append(f"#{t['id']}: {t['title']} (статус: {t['status']})")
            try:
                await bot.send_message(int(user["tg_id"]), "\n".join(lines))
            except Exception:
                continue

    async def notify_tasks_tomorrow_at_7():
        now = datetime.now()
        if now.hour != 7:
            return
        tomorrow = _date_str(now + timedelta(days=1))
        users = await repo.db.fetchall("SELECT * FROM users")
        for user in users:
            tasks = await repo.list_tasks_for_user_on_date(int(user["id"]), tomorrow)
            if not tasks:
                continue
            lines = ["Задачи на завтра:"]
            for t in tasks:
                lines.append(f"#{t['id']}: {t['title']} (статус: {t['status']})")
            try:
                await bot.send_message(int(user["tg_id"]), "\n".join(lines))
            except Exception:
                continue

    async def notify_personal_tasks():
        now = datetime.now()
        if not _in_reminder_window(now):
            return
        today = _date_str(now)
        directors = await repo.db.fetchall("SELECT * FROM users WHERE role = 'director'")
        for user in directors:
            tasks = await repo.list_personal_tasks(int(user["id"]), today)
            if not tasks:
                continue
            lines = ["Ваши дела на сегодня:"]
            for t in tasks:
                lines.append(f"#{t['id']}: {t['title']} (статус: {t['status']})")
            try:
                await bot.send_message(int(user["tg_id"]), "\n".join(lines))
            except Exception:
                continue

    scheduler.add_job(notify_tasks_hourly, "interval", hours=1, next_run_time=datetime.now())
    scheduler.add_job(notify_tasks_tomorrow_at_7, "interval", hours=1, next_run_time=datetime.now())
    scheduler.add_job(notify_personal_tasks, "interval", hours=2, next_run_time=datetime.now())

    return scheduler
