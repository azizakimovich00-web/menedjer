from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from app.handlers.common import require_director_pin
from app.keyboards.common import (
    clients_menu as clients_menu_kb,
    confirm_menu,
    manager_menu,
    materials_menu,
    orders_menu as orders_menu_kb,
    tasks_menu,
)
from app.services import roles
from app.services.exporter import export_to_xlsx
from app.states.forms import DeleteStates, MaterialStates, OrderStates, RequestStates, SearchStates, TaskStates

router = Router()


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _period_start(label: str) -> str:
    now = datetime.now()
    if label == "За сегодня":
        return _date_str(now)
    if label == "За неделю":
        return _date_str(now - timedelta(days=7))
    if label == "За месяц":
        return _date_str(now - timedelta(days=30))
    return _date_str(now)


async def _get_repo(message: Message):
    return message.bot["repo"]


async def _ensure_manager(message: Message, state: FSMContext) -> bool:
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    if not user:
        return False
    if user["role"] == roles.ROLE_DIRECTOR:
        ok = await require_director_pin(message, state)
        if not ok:
            return False
        data = await state.get_data()
        return data.get("current_menu") == "manager"
    return user["role"] == roles.ROLE_MANAGER


@router.message(F.text == "Новая заявка")
async def new_request_start(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    await state.update_data(current_menu="requests")
    await state.set_state(RequestStates.name)
    await message.answer("Имя клиента?")


@router.message(RequestStates.name)
async def request_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(RequestStates.phone)
    await message.answer("Номер телефона?")


@router.message(RequestStates.phone)
async def request_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(RequestStates.comment)
    await message.answer("Комментарий (что нужно, размеры, адрес, срочность и т.д.)")


@router.message(RequestStates.comment)
async def request_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await state.set_state(RequestStates.photos)
    await state.update_data(photos=[])
    await message.answer("Фото? Отправьте до 3 фото. Если без фото, напишите 'нет'.")


@router.message(RequestStates.photos, F.text)
async def request_photos_skip(message: Message, state: FSMContext):
    if (message.text or "").strip().lower() not in {"нет", "no"}:
        await message.answer("Если есть фото, отправьте их файлом. Либо напишите 'нет'.")
        return
    data = await state.get_data()
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    request_id = await repo.add_request(
        user_id=int(user["id"]),
        name=data.get("name", ""),
        phone=data.get("phone", ""),
        comment=data.get("comment"),
    )
    for fid in data.get("photos", []):
        await repo.add_photo("request", request_id, fid)
    await state.clear()
    await message.answer(f"Заявка создана (ID {request_id}).", reply_markup=manager_menu())


@router.message(RequestStates.photos, F.photo)
async def request_photos_add(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = list(data.get("photos", []))
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    await state.update_data(photos=photos)
    if len(photos) >= 3:
        repo = await _get_repo(message)
        user = await repo.get_user_by_tg(message.from_user.id)
        request_id = await repo.add_request(
            user_id=int(user["id"]),
            name=data.get("name", ""),
            phone=data.get("phone", ""),
            comment=data.get("comment"),
        )
        for fid in photos:
            await repo.add_photo("request", request_id, fid)
        await state.clear()
        await message.answer(f"Заявка создана (ID {request_id}).", reply_markup=manager_menu())
        return
    await message.answer("Фото сохранено. Отправьте еще фото или напишите 'нет'.")


@router.message(F.text == "Клиенты")
async def open_clients_menu(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    await state.update_data(current_menu="clients")
    await message.answer("Клиенты:", reply_markup=clients_menu_kb())


@router.message(F.text == "Заказы")
async def open_orders_menu(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    await state.update_data(current_menu="orders")
    await message.answer("Заказы:", reply_markup=orders_menu_kb())


@router.message(F.text == "Задачи")
async def tasks_open(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    await state.update_data(current_menu="tasks")
    await message.answer("Задачи:", reply_markup=tasks_menu())


@router.message(F.text.in_({"Сегодня", "Завтра"}))
async def tasks_by_date(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    data = await state.get_data()
    if data.get("current_menu") != "tasks":
        raise SkipHandler
    repo = await _get_repo(message)
    date_str = _date_str(datetime.now() if message.text == "Сегодня" else datetime.now() + timedelta(days=1))
    tasks = await repo.list_tasks_by_date(date_str)
    if not tasks:
        await message.answer("Задач нет.")
        return
    lines = [f"Задачи на {date_str}:"]
    for t in tasks:
        lines.append(f"#{t['id']} {t['title']} | сотрудник ID {t['assignee_id']} | статус: {t['status']}")
    await message.answer("\n".join(lines))


@router.message(F.text == "Выполненные")
async def tasks_done(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    data = await state.get_data()
    if data.get("current_menu") != "tasks":
        raise SkipHandler
    repo = await _get_repo(message)
    rows = await repo.db.fetchall("SELECT * FROM tasks WHERE status = 'Выполнено' ORDER BY id DESC")
    if not rows:
        await message.answer("Выполненных задач нет.")
        return
    lines = ["Выполненные задачи:"]
    for t in rows:
        lines.append(f"#{t['id']} {t['title']} | {t['completed_at'] or ''}")
    await message.answer("\n".join(lines))


@router.message(F.text == "Добавить задачу")
async def task_add_start(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    await state.set_state(TaskStates.assignee)
    await message.answer("Кому? Введите TG ID сотрудника:")


@router.message(TaskStates.assignee)
async def task_add_assignee(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужен TG ID числом.")
        return
    await state.update_data(assignee_tg=int(text))
    await state.set_state(TaskStates.title)
    await message.answer("Что сделать?")


@router.message(TaskStates.title)
async def task_add_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(TaskStates.due_date)
    await message.answer("Когда? (формат YYYY-MM-DD или 'сегодня'/'завтра')")


@router.message(TaskStates.due_date)
async def task_add_date(message: Message, state: FSMContext):
    text = (message.text or "").strip().lower()
    if text == "сегодня":
        date_str = _date_str(datetime.now())
    elif text == "завтра":
        date_str = _date_str(datetime.now() + timedelta(days=1))
    else:
        date_str = text
    await state.update_data(due_date=date_str)
    await state.set_state(TaskStates.comment)
    await message.answer("Комментарий (можно пусто):")


@router.message(TaskStates.comment)
async def task_add_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    repo = await _get_repo(message)
    manager = await repo.get_user_by_tg(message.from_user.id)
    assignee = await repo.get_user_by_tg(int(data.get("assignee_tg")))
    if not assignee:
        await message.answer("Сотрудник не найден. Он должен написать /start.")
        await state.clear()
        return
    await repo.add_task(
        manager_id=int(manager["id"]),
        assignee_id=int(assignee["id"]),
        title=data.get("title", ""),
        due_date=data.get("due_date", ""),
        comment=message.text,
    )
    await state.clear()
    await message.answer("Задача добавлена.", reply_markup=tasks_menu())


@router.message(F.text == "Материалы")
async def materials_open(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    await state.update_data(current_menu="materials")
    await message.answer("Материалы:", reply_markup=materials_menu())


@router.message(F.text == "Остатки")
async def materials_balance(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    repo = await _get_repo(message)
    mats = await repo.list_materials()
    lines = ["Остатки:"]
    for m in mats:
        lines.append(f"{m['name']}: {m['current_qty']} {m['unit']}")
    await message.answer("\n".join(lines))


@router.message(F.text.in_({"Приход", "Списание"}))
async def material_action(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    action = "IN" if message.text == "Приход" else "OUT"
    await state.set_state(MaterialStates.material)
    await state.update_data(action=action)
    await message.answer("Материал (например: Баннер, Самоклейка, Сетка, Плоттерная пленка, Форекс 3 мм, Форекс 5 мм):")


@router.message(MaterialStates.material)
async def material_choose(message: Message, state: FSMContext):
    await state.update_data(material_name=message.text)
    await state.set_state(MaterialStates.qty)
    await message.answer("Сколько?")


@router.message(MaterialStates.qty)
async def material_qty(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", ".").strip()
    try:
        qty = float(text)
    except ValueError:
        await message.answer("Введите число.")
        return
    await state.update_data(qty=qty)
    await state.set_state(MaterialStates.comment)
    await message.answer("Комментарий (можно пусто):")


@router.message(MaterialStates.comment)
async def material_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    mat = await repo.get_material_by_name(data.get("material_name", ""))
    if not mat:
        await message.answer("Материал не найден.")
        await state.clear()
        return
    action = data.get("action")
    qty = float(data.get("qty"))
    if action == "OUT":
        qty = -abs(qty)
    await repo.add_material_movement(
        user_id=int(user["id"]),
        material_id=int(mat["id"]),
        qty=qty,
        action=action,
        comment=message.text,
    )
    await state.clear()
    await message.answer("Движение сохранено.", reply_markup=materials_menu())


@router.message(F.text == "История")
async def manager_history(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    repo = await _get_repo(message)
    data = await state.get_data()
    if data.get("current_menu") == "materials":
        rows = await repo.list_material_history()
        if not rows:
            await message.answer("История пуста.")
            return
        lines = ["История материалов:"]
        for r in rows:
            lines.append(f"#{r['id']} материал {r['material_id']} {r['action']} {r['qty']} | {r['created_at']}")
        await message.answer("\n".join(lines))
        return
    rows = await repo.list_manager_history()
    if not rows:
        await message.answer("История пуста.")
        return
    lines = ["История заявок:"]
    for r in rows:
        lines.append(f"#{r['id']} {r['name']} | статус: {r['status']} | {r['created_at']}")
    await message.answer("\n".join(lines))


@router.message(F.text == "Напоминания")
async def reminders(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    repo = await _get_repo(message)
    today = _date_str(datetime.now())
    tomorrow = _date_str(datetime.now() + timedelta(days=1))
    tasks_today = await repo.list_tasks_by_date(today)
    tasks_tomorrow = await repo.list_tasks_by_date(tomorrow)
    orders_today = await repo.list_orders_by_deadline(today)
    orders_tomorrow = await repo.list_orders_by_deadline(tomorrow)
    await message.answer(
        "Напоминания:\n"
        f"Сегодня: задач {len(tasks_today)}, заказов {len(orders_today)}\n"
        f"Завтра: задач {len(tasks_tomorrow)}, заказов {len(orders_tomorrow)}"
    )


@router.message(F.text == "Отчеты")
async def manager_reports(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    await state.update_data(current_menu="reports")
    await message.answer("Выберите период: За сегодня / За неделю / За месяц")


@router.message(F.text == "Все клиенты")
async def list_clients(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    repo = await _get_repo(message)
    rows = await repo.list_clients()
    if not rows:
        await message.answer("Клиентов нет.")
        return
    lines = ["Клиенты:"]
    for r in rows:
        lines.append(f"#{r['id']} {r['name']} | {r['phone']} | {r['comment'] or ''}")
    await message.answer("\n".join(lines))


@router.message(F.text == "Поиск клиента")
async def search_client_start(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    await state.set_state(SearchStates.query)
    await state.update_data(search_context="clients")
    await message.answer("Введите имя или номер для поиска клиента:")


@router.message(SearchStates.query)
async def search_client_process(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("search_context") != "clients":
        raise SkipHandler
    repo = await _get_repo(message)
    rows = await repo.search_clients(message.text or "")
    await state.clear()
    if not rows:
        await message.answer("Клиентов не найдено.")
        return
    lines = ["Результаты поиска:"]
    for r in rows:
        lines.append(f"#{r['id']} {r['name']} | {r['phone']} | {r['comment'] or ''}")
    await message.answer("\n".join(lines))


@router.message(F.text == "История клиента")
async def client_history_start(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    await state.set_state(SearchStates.query)
    await state.update_data(search_context="client_history")
    await message.answer("Введите номер клиента для истории:")


@router.message(SearchStates.query)
async def client_history_process(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("search_context") != "client_history":
        raise SkipHandler
    repo = await _get_repo(message)
    reqs, orders = await repo.list_client_history(message.text or "")
    await state.clear()
    lines = ["История клиента:"]
    for r in reqs:
        lines.append(f"Заявка #{r['id']} {r['status']} | {r['created_at']}")
    for o in orders:
        lines.append(f"Заказ #{o['id']} {o['status']} | дедлайн {o['deadline_date'] or '-'}")
    await message.answer("\n".join(lines) if lines else "История пуста.")


@router.message(F.text == "Добавить заказ")
async def order_add_start(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    await state.set_state(OrderStates.name)
    await message.answer("Имя клиента?")


@router.message(OrderStates.name)
async def order_add_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(OrderStates.phone)
    await message.answer("Номер клиента?")


@router.message(OrderStates.phone)
async def order_add_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(OrderStates.comment)
    await message.answer("Комментарий по заказу:")


@router.message(OrderStates.comment)
async def order_add_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await state.set_state(OrderStates.deadline)
    await message.answer("Дедлайн (YYYY-MM-DD или 'сегодня'/'завтра'):")


@router.message(OrderStates.deadline)
async def order_add_deadline(message: Message, state: FSMContext):
    text = (message.text or "").strip().lower()
    if text == "сегодня":
        date_str = _date_str(datetime.now())
    elif text == "завтра":
        date_str = _date_str(datetime.now() + timedelta(days=1))
    else:
        date_str = text
    await state.update_data(deadline=date_str)
    await state.set_state(OrderStates.responsible)
    await message.answer("Ответственный TG ID (или 0 если без назначения):")


@router.message(OrderStates.responsible)
async def order_add_responsible(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужен TG ID числом (или 0).")
        return
    await state.update_data(responsible=int(text))
    await state.set_state(OrderStates.photos)
    await state.update_data(photos=[])
    await message.answer("Фото по заказу? До 3 фото. Если нет — напишите 'нет'.")


@router.message(OrderStates.photos, F.text)
async def order_add_photos_skip(message: Message, state: FSMContext):
    if (message.text or "").strip().lower() not in {"нет", "no"}:
        await message.answer("Если есть фото, отправьте их. Либо напишите 'нет'.")
        return
    await _finish_order_create(message, state)


@router.message(OrderStates.photos, F.photo)
async def order_add_photos_add(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = list(data.get("photos", []))
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    if len(photos) >= 3:
        await _finish_order_create(message, state)
        return
    await message.answer("Фото сохранено. Отправьте еще или напишите 'нет'.")


async def _finish_order_create(message: Message, state: FSMContext):
    data = await state.get_data()
    repo = await _get_repo(message)
    responsible_id = None
    if int(data.get("responsible", 0)) != 0:
        user = await repo.get_user_by_tg(int(data.get("responsible")))
        if user:
            responsible_id = int(user["id"])
    order_id = await repo.add_order(
        name=data.get("name", ""),
        phone=data.get("phone", ""),
        comment=data.get("comment"),
        deadline_date=data.get("deadline"),
        responsible_user_id=responsible_id,
    )
    for fid in data.get("photos", []):
        await repo.add_photo("order", order_id, fid)
    await _notify_order_created(message, order_id, data.get("name", ""), data.get("deadline"))
    await state.clear()
    await message.answer(f"Заказ создан (ID {order_id}).", reply_markup=orders_menu_kb())


async def _notify_order_created(message: Message, order_id: int, name: str, deadline: str | None) -> None:
    repo = await _get_repo(message)
    users = await repo.db.fetchall("SELECT * FROM users WHERE role IN ('director','manager')")
    text = f"Новый заказ #{order_id} для {name}. Дедлайн: {deadline or '-'}."
    for u in users:
        try:
            await message.bot.send_message(int(u["tg_id"]), text)
        except Exception:
            continue


@router.message(F.text.in_({"Сегодня", "Завтра", "Все активные", "Завершенные"}))
async def orders_filter(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    data = await state.get_data()
    if data.get("current_menu") != "orders":
        raise SkipHandler
    repo = await _get_repo(message)
    if message.text in {"Сегодня", "Завтра"}:
        date_str = _date_str(datetime.now() if message.text == "Сегодня" else datetime.now() + timedelta(days=1))
        orders = await repo.list_orders_by_deadline(date_str)
        label = f"Заказы на {date_str}:"
    elif message.text == "Все активные":
        orders = await repo.list_orders_by_status(["Новый", "В работе", "Готов"])
        label = "Активные заказы:"
    else:
        orders = await repo.list_orders_by_status(["Закрыт"])
        label = "Завершенные заказы:"
    if not orders:
        await message.answer("Заказов нет.")
        return
    lines = [label]
    for o in orders:
        lines.append(f"#{o['id']} {o['name']} | статус: {o['status']} | дедлайн: {o['deadline_date'] or '-'}")
    await message.answer("\n".join(lines))


@router.message(F.text.in_({"За сегодня", "За неделю", "За месяц"}))
async def manager_period_report(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    data = await state.get_data()
    if data.get("current_menu") != "reports":
        raise SkipHandler
    start = _period_start(message.text)
    repo = await _get_repo(message)
    reqs = await repo.db.fetchone(
        "SELECT COUNT(*) AS c FROM requests WHERE substr(created_at,1,10) >= ?",
        (start,),
    )
    orders = await repo.db.fetchone(
        "SELECT COUNT(*) AS c FROM orders WHERE substr(created_at,1,10) >= ?",
        (start,),
    )
    closed = await repo.db.fetchone(
        "SELECT COUNT(*) AS c FROM orders WHERE status = 'Закрыт' AND substr(created_at,1,10) >= ?",
        (start,),
    )
    done_tasks = await repo.db.fetchone(
        "SELECT COUNT(*) AS c FROM tasks WHERE status = 'Выполнено' AND substr(created_at,1,10) >= ?",
        (start,),
    )
    not_done_tasks = await repo.db.fetchone(
        "SELECT COUNT(*) AS c FROM tasks WHERE status = 'Не выполнено' AND substr(created_at,1,10) >= ?",
        (start,),
    )
    await message.answer(
        f"Отчет {message.text}:\n"
        f"Новые заявки: {reqs['c']}\n"
        f"Заказы: {orders['c']}\n"
        f"Закрытые заказы: {closed['c']}\n"
        f"Выполненные задачи: {done_tasks['c']}\n"
        f"Невыполненные задачи: {not_done_tasks['c']}"
    )


@router.message(F.text == "Экспорт Excel")
async def export_excel(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    data = await state.get_data()
    section = data.get("current_menu")
    repo = await _get_repo(message)
    if section == "materials":
        rows = await repo.list_material_history(10000)
        body = [
            [r["id"], r["material_id"], r["qty"], r["action"], r["comment"], r["created_at"]]
            for r in rows
        ]
        path = export_to_xlsx(
            headers=["ID", "Материал ID", "Кол-во", "Тип", "Комментарий", "Дата"],
            rows=body,
            out_dir=message.bot["exports_dir"],
            prefix="materials",
        )
        await message.answer_document(document=FSInputFile(path), caption="Экспорт материалов")
        return
    if section == "tasks":
        rows = await repo.db.fetchall("SELECT * FROM tasks ORDER BY id DESC")
        body = [
            [r["id"], r["assignee_id"], r["title"], r["due_date"], r["status"], r["comment"], r["created_at"]]
            for r in rows
        ]
        path = export_to_xlsx(
            headers=["ID", "Сотрудник", "Задача", "Дата", "Статус", "Комментарий", "Создано"],
            rows=body,
            out_dir=message.bot["exports_dir"],
            prefix="tasks",
        )
        await message.answer_document(document=FSInputFile(path), caption="Экспорт задач")
        return
    if section == "clients":
        rows = await repo.list_clients()
        body = [[r["id"], r["name"], r["phone"], r["comment"], r["created_at"]] for r in rows]
        path = export_to_xlsx(
            headers=["ID", "Имя", "Телефон", "Комментарий", "Создано"],
            rows=body,
            out_dir=message.bot["exports_dir"],
            prefix="clients",
        )
        await message.answer_document(document=FSInputFile(path), caption="Экспорт клиентов")
        return
    if section == "orders":
        rows = await repo.db.fetchall("SELECT * FROM orders ORDER BY id DESC")
        body = [
            [r["id"], r["name"], r["phone"], r["status"], r["deadline_date"], r["responsible_user_id"], r["created_at"]]
            for r in rows
        ]
        path = export_to_xlsx(
            headers=["ID", "Имя", "Телефон", "Статус", "Дедлайн", "Ответственный", "Создано"],
            rows=body,
            out_dir=message.bot["exports_dir"],
            prefix="orders",
        )
        await message.answer_document(document=FSInputFile(path), caption="Экспорт заказов")
        return
    await message.answer("Экспорт доступен внутри разделов: Материалы, Задачи, Клиенты, Заказы.")


@router.message(F.text == "Очистить")
async def clear_section(message: Message, state: FSMContext):
    if not await _ensure_manager(message, state):
        raise SkipHandler
    data = await state.get_data()
    section = data.get("current_menu")
    if section not in {"materials", "tasks", "clients", "orders"}:
        await message.answer("Очистка доступна внутри разделов.")
        return
    await state.set_state(DeleteStates.section)
    await state.update_data(delete_section=section)
    await message.answer(
        "Точно хотите очистить данные? Рекомендуется сначала сделать экспорт Excel.",
        reply_markup=confirm_menu(),
    )


@router.message(DeleteStates.section, F.text.in_({"Да", "Нет"}))
async def clear_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    section = data.get("delete_section")
    if not section:
        raise SkipHandler
    if message.text == "Нет":
        await state.clear()
        await message.answer("Отменено.")
        return
    repo = await _get_repo(message)
    if section == "materials":
        await repo.delete_all_from("material_history")
        await repo.db.execute("UPDATE materials SET current_qty = 0")
    if section == "tasks":
        await repo.delete_all_from("tasks")
    if section == "clients":
        await repo.delete_all_from("clients")
    if section == "orders":
        await repo.delete_all_from("orders")
    await state.clear()
    if section == "materials":
        await message.answer("Раздел очищен.", reply_markup=materials_menu())
    elif section == "tasks":
        await message.answer("Раздел очищен.", reply_markup=tasks_menu())
    elif section == "clients":
        await message.answer("Раздел очищен.", reply_markup=clients_menu_kb())
    elif section == "orders":
        await message.answer("Раздел очищен.", reply_markup=orders_menu_kb())
