from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.keyboards.common import make_main_menu
from app.services import roles
from app.states.forms import EmployeeTaskStates

router = Router()


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


async def _get_repo(message: Message):
    return message.bot["repo"]


async def _ensure_employee(message: Message) -> bool:
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    if not user:
        return False
    return user["role"] == roles.ROLE_EMPLOYEE


@router.message(F.text == "Мои задачи")
async def my_tasks(message: Message, state: FSMContext):
    if not await _ensure_employee(message):
        raise SkipHandler
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    today = _date_str(datetime.now())
    tasks = await repo.list_tasks_for_user_on_date(int(user["id"]), today)
    if not tasks:
        await message.answer("Задач на сегодня нет.")
        return
    lines = ["Ваши задачи на сегодня:"]
    for t in tasks:
        lines.append(f"#{t['id']} {t['title']} (статус: {t['status']})")
    await message.answer("\n".join(lines))
    for t in tasks:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Выполнено", callback_data=f"task_done:{t['id']}"),
                    InlineKeyboardButton(text="Не выполнено", callback_data=f"task_notdone:{t['id']}"),
                ]
            ]
        )
        await message.answer(f"Задача #{t['id']}: {t['title']}", reply_markup=kb)


@router.callback_query(F.data.startswith("task_done:"))
async def task_done(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_employee(callback.message):
        raise SkipHandler
    repo = await _get_repo(callback.message)
    task_id = int(callback.data.split(":")[1])
    task = await repo.get_task(task_id)
    user = await repo.get_user_by_tg(callback.from_user.id)
    if not task or int(task["assignee_id"]) != int(user["id"]):
        await callback.answer("Нет доступа.")
        return
    await repo.update_task_status(task_id, "Выполнено")
    await _notify_directors(callback.message, f"Задача #{task_id} выполнена.")
    await callback.answer("Отмечено как выполнено.")


@router.callback_query(F.data.startswith("task_notdone:"))
async def task_not_done(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_employee(callback.message):
        raise SkipHandler
    repo = await _get_repo(callback.message)
    task_id = int(callback.data.split(":")[1])
    task = await repo.get_task(task_id)
    user = await repo.get_user_by_tg(callback.from_user.id)
    if not task or int(task["assignee_id"]) != int(user["id"]):
        await callback.answer("Нет доступа.")
        return
    await state.set_state(EmployeeTaskStates.not_done_reason)
    await state.update_data(task_id=task_id)
    await callback.message.answer("Причина / комментарий:")
    await callback.answer()


@router.message(EmployeeTaskStates.not_done_reason)
async def task_not_done_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = int(data.get("task_id"))
    repo = await _get_repo(message)
    await repo.update_task_status(task_id, "Не выполнено", reason=message.text)
    await _notify_directors(message, f"Задача #{task_id} НЕ выполнена. Причина: {message.text}")
    await state.clear()
    await message.answer("Причина сохранена.")


async def _notify_directors(message: Message, text: str) -> None:
    repo = await _get_repo(message)
    users = await repo.db.fetchall("SELECT * FROM users WHERE role = 'director'")
    for u in users:
        try:
            await message.bot.send_message(int(u["tg_id"]), text)
        except Exception:
            continue


@router.message(F.text == "Мои заказы")
async def my_orders(message: Message, state: FSMContext):
    if not await _ensure_employee(message):
        raise SkipHandler
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    orders = await repo.list_orders_for_user(int(user["id"]), user["role"])
    if not orders:
        await message.answer("Заказов нет.")
        return
    lines = ["Ваши заказы:"]
    for o in orders:
        lines.append(f"#{o['id']} {o['name']} | статус: {o['status']} | дедлайн: {o['deadline_date'] or '-'}")
    await message.answer("\n".join(lines))


@router.message()
async def fallback(message: Message, state: FSMContext):
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    if not user:
        return
    await message.answer("Главное меню:", reply_markup=make_main_menu(user["role"]))
