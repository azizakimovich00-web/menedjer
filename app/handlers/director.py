from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.handlers.common import require_director_pin
from app.keyboards.common import (
    accountant_menu,
    confirm_menu,
    contacts_menu,
    employees_menu,
    make_main_menu,
    personal_menu,
)
from app.services import roles
from app.services.exporter import export_to_xlsx
from app.states.forms import ContactStates, DeleteStates, PersonalTaskActionStates, PersonalTaskStates, RoleAssignStates

router = Router()


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


async def _get_repo(message: Message):
    return message.bot["repo"]


async def _ensure_director(message: Message, state: FSMContext) -> bool:
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    if not user or user["role"] != roles.ROLE_DIRECTOR:
        return False
    return await require_director_pin(message, state)


async def _ensure_personal_menu(state: FSMContext) -> bool:
    data = await state.get_data()
    return data.get("current_menu") == "personal"


@router.message(F.text == "Бухгалтер")
async def open_accountant(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    await state.update_data(current_menu="accountant")
    await message.answer("Раздел бухгалтерии:", reply_markup=accountant_menu())


@router.message(F.text == "Менеджер")
async def open_manager(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    from app.keyboards.common import manager_menu

    await state.update_data(current_menu="manager")
    await message.answer("Раздел менеджера:", reply_markup=manager_menu())


@router.message(F.text == "Контакты")
async def open_contacts(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    await state.update_data(current_menu="contacts")
    await message.answer("Раздел контакты:", reply_markup=contacts_menu())


@router.message(F.text == "Сотрудники")
async def open_employees(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    await state.update_data(current_menu="employees")
    await message.answer("Раздел сотрудники:", reply_markup=employees_menu())


@router.message(F.text == "Мои дела")
async def open_personal(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    await state.update_data(current_menu="personal")
    await message.answer("Раздел мои дела:", reply_markup=personal_menu())


@router.message(F.text == "Список сотрудников")
async def list_employees(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    repo = await _get_repo(message)
    users = await repo.list_users()
    if not users:
        await message.answer("Список пуст.")
        return
    lines = ["Сотрудники:"]
    for u in users:
        lines.append(f"ID {u['id']} | TG {u['tg_id']} | {u['full_name']} | роль: {u['role']}")
    await message.answer("\n".join(lines))


@router.message(F.text.in_({"Назначить роль", "Изменить роль"}))
async def start_assign_role(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    await state.set_state(RoleAssignStates.user)
    await message.answer("Введите TG ID сотрудника:")


@router.message(RoleAssignStates.user)
async def assign_role_user(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    data = await state.get_data()
    if data.get("remove_access"):
        return
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужен TG ID числом. Попробуйте снова:")
        return
    await state.update_data(tg_id=int(text))
    await state.set_state(RoleAssignStates.role)
    await message.answer("Введите роль: director / accountant / manager / employee")


@router.message(RoleAssignStates.role)
async def assign_role_role(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    role = (message.text or "").strip().lower()
    if role not in roles.ALL_ROLES:
        await message.answer("Неверная роль. Введите: director / accountant / manager / employee")
        return
    data = await state.get_data()
    tg_id = int(data["tg_id"])
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(tg_id)
    if not user:
        await message.answer("Пользователь не найден. Он должен написать /start.")
        await state.clear()
        return
    await repo.set_role(int(user["id"]), role)
    await state.clear()
    await message.answer(f"Роль обновлена: {user['full_name']} -> {role}")


@router.message(F.text == "Удалить доступ")
async def remove_access(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    await state.set_state(RoleAssignStates.user)
    await state.update_data(remove_access=True)
    await message.answer("Введите TG ID сотрудника для удаления доступа:")


@router.message(RoleAssignStates.user, F.text.regexp(r"^\d+$"))
async def remove_access_process(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("remove_access"):
        return
    if not await _ensure_director(message, state):
        raise SkipHandler
    repo = await _get_repo(message)
    tg_id = int(message.text)
    user = await repo.get_user_by_tg(tg_id)
    if not user:
        await message.answer("Пользователь не найден.")
        await state.clear()
        return
    await repo.set_role(int(user["id"]), roles.ROLE_EMPLOYEE)
    await state.clear()
    await message.answer("Доступ ограничен до роли сотрудник.")


@router.message(F.text == "Добавить контакт")
async def add_contact_start(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    await state.set_state(ContactStates.name)
    await message.answer("Название контакта:")


@router.message(ContactStates.name)
async def add_contact_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ContactStates.phone)
    await message.answer("Номер:")


@router.message(ContactStates.phone)
async def add_contact_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(ContactStates.category)
    await message.answer("Категория (например: Баннеры, Форекс, Печать, Поставщики, Доставка, Реклама, Мастера, Другое):")


@router.message(ContactStates.category)
async def add_contact_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state(ContactStates.comment)
    await message.answer("Комментарий (можно пусто):")


@router.message(ContactStates.comment)
async def add_contact_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    repo = await _get_repo(message)
    await repo.add_contact(
        name=data.get("name", ""),
        phone=data.get("phone", ""),
        category=data.get("category", ""),
        comment=message.text,
    )
    await state.clear()
    await message.answer("Контакт добавлен.", reply_markup=contacts_menu())


@router.message(F.text == "Все контакты")
async def list_contacts(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    if not await _ensure_contacts_menu(state):
        raise SkipHandler
    repo = await _get_repo(message)
    rows = await repo.list_contacts()
    if not rows:
        await message.answer("Контактов нет.")
        return
    lines = ["Контакты:"]
    for r in rows:
        lines.append(f"#{r['id']} {r['name']} | {r['phone']} | {r['category']} | {r['comment'] or ''}")
    await message.answer("\n".join(lines))


@router.message(F.text == "Добавить дело")
async def add_personal_start(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    if not await _ensure_personal_menu(state):
        raise SkipHandler
    await state.set_state(PersonalTaskStates.title)
    await message.answer("Что сделать?")


@router.message(PersonalTaskStates.title)
async def add_personal_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(PersonalTaskStates.due_date)
    await message.answer("Когда? (формат YYYY-MM-DD или 'сегодня'/'завтра')")


@router.message(PersonalTaskStates.due_date)
async def add_personal_date(message: Message, state: FSMContext):
    text = (message.text or "").strip().lower()
    if text in {"сегодня", "today"}:
        date_str = _date_str(datetime.now())
    elif text in {"завтра", "tomorrow"}:
        date_str = _date_str(datetime.now() + timedelta(days=1))
    else:
        date_str = text
    await state.update_data(due_date=date_str)
    await state.set_state(PersonalTaskStates.comment)
    await message.answer("Комментарий (можно пусто):")


@router.message(PersonalTaskStates.comment)
async def add_personal_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    await repo.add_personal_task(
        director_id=int(user["id"]),
        title=data.get("title", ""),
        due_date=data.get("due_date", ""),
        comment=message.text,
    )
    await state.clear()
    await message.answer("Дело добавлено.", reply_markup=personal_menu())


@router.message(F.text.in_({"Сегодня", "Завтра"}))
async def list_personal_by_date(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    if not await _ensure_personal_menu(state):
        raise SkipHandler
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    base = datetime.now()
    date_str = _date_str(base if message.text == "Сегодня" else base + timedelta(days=1))
    tasks = await repo.list_personal_tasks(int(user["id"]), date_str)
    if not tasks:
        await message.answer("Дел нет.")
        return
    lines = [f"Дела на {date_str}:"]
    for t in tasks:
        lines.append(f"#{t['id']} {t['title']} (статус: {t['status']})")
    await message.answer("\n".join(lines))
    for t in tasks:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Выполнено", callback_data=f"pt_done:{t['id']}"),
                    InlineKeyboardButton(text="Не выполнено", callback_data=f"pt_notdone:{t['id']}"),
                    InlineKeyboardButton(text="Перенести", callback_data=f"pt_move:{t['id']}"),
                ]
            ]
        )
        await message.answer(f"Дело #{t['id']}: {t['title']}", reply_markup=kb)


@router.message(F.text == "История")
async def list_personal_history(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    if not await _ensure_personal_menu(state):
        raise SkipHandler
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    tasks = await repo.list_personal_history(int(user["id"]))
    if not tasks:
        await message.answer("История пуста.")
        return
    lines = ["История дел:"]
    for t in tasks:
        lines.append(f"#{t['id']} {t['title']} ({t['due_date']}) статус: {t['status']}")
    await message.answer("\n".join(lines))


@router.callback_query(F.data.startswith("pt_done:"))
async def personal_done(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_director(callback.message, state):
        raise SkipHandler
    task_id = int(callback.data.split(":")[1])
    repo = await _get_repo(callback.message)
    await repo.update_personal_task_status(task_id, "Выполнено")
    await callback.answer("Отмечено как выполнено.")


@router.callback_query(F.data.startswith("pt_notdone:"))
async def personal_not_done(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_director(callback.message, state):
        raise SkipHandler
    task_id = int(callback.data.split(":")[1])
    await state.set_state(PersonalTaskActionStates.not_done_reason)
    await state.update_data(pt_task_id=task_id)
    await callback.message.answer("Причина / комментарий:")
    await callback.answer()


@router.message(PersonalTaskActionStates.not_done_reason)
async def personal_not_done_reason(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    data = await state.get_data()
    task_id = int(data.get("pt_task_id"))
    repo = await _get_repo(message)
    await repo.update_personal_task_status(task_id, "Не выполнено", reason=message.text)
    await state.clear()
    await message.answer("Причина сохранена.")


@router.callback_query(F.data.startswith("pt_move:"))
async def personal_move(callback: CallbackQuery, state: FSMContext):
    if not await _ensure_director(callback.message, state):
        raise SkipHandler
    task_id = int(callback.data.split(":")[1])
    await state.set_state(PersonalTaskActionStates.new_date)
    await state.update_data(pt_task_id=task_id)
    await callback.message.answer("Новая дата (YYYY-MM-DD):")
    await callback.answer()


@router.message(PersonalTaskActionStates.new_date)
async def personal_move_date(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    data = await state.get_data()
    task_id = int(data.get("pt_task_id"))
    repo = await _get_repo(message)
    await repo.reschedule_personal_task(task_id, message.text or "")
    await state.clear()
    await message.answer("Дата обновлена.")


async def _ensure_contacts_menu(state: FSMContext) -> bool:
    data = await state.get_data()
    return data.get("current_menu") == "contacts"


@router.message(F.text == "Экспорт Excel")
async def contacts_export(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    if not await _ensure_contacts_menu(state):
        raise SkipHandler
    repo = await _get_repo(message)
    rows = await repo.list_contacts()
    body = [[r["id"], r["name"], r["phone"], r["category"], r["comment"], r["created_at"]] for r in rows]
    path = export_to_xlsx(
        headers=["ID", "Название", "Телефон", "Категория", "Комментарий", "Создано"],
        rows=body,
        out_dir=message.bot["exports_dir"],
        prefix="contacts",
    )
    await message.answer_document(document=FSInputFile(path), caption="Экспорт контактов")


@router.message(F.text == "Очистить")
async def contacts_clear(message: Message, state: FSMContext):
    if not await _ensure_director(message, state):
        raise SkipHandler
    if not await _ensure_contacts_menu(state):
        raise SkipHandler
    await state.set_state(DeleteStates.section)
    await state.update_data(delete_section="contacts")
    await message.answer(
        "Точно хотите очистить данные? Рекомендуется сначала сделать экспорт Excel.",
        reply_markup=confirm_menu(),
    )


@router.message(DeleteStates.section, F.text.in_({"Да", "Нет"}))
async def contacts_clear_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("delete_section") != "contacts":
        raise SkipHandler
    if message.text == "Нет":
        await state.clear()
        await message.answer("Отменено.", reply_markup=contacts_menu())
        return
    repo = await _get_repo(message)
    await repo.delete_all_from("contacts")
    await state.clear()
    await message.answer("Контакты очищены.", reply_markup=contacts_menu())
