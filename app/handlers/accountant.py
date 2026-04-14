from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from app.handlers.common import require_director_pin
from app.keyboards.common import accountant_menu, confirm_menu, make_main_menu
from app.services import roles
from app.services.exporter import export_to_xlsx
from app.states.forms import DebtPaymentStates, DeleteStates, ExpenseStates, SaleStates

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
    return message.bot.repo


async def _ensure_accountant(message: Message, state: FSMContext) -> bool:
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    if not user:
        return False
    if user["role"] == roles.ROLE_DIRECTOR:
        ok = await require_director_pin(message, state)
        if not ok:
            return False
        data = await state.get_data()
        return data.get("current_menu") == "accountant"
    return user["role"] == roles.ROLE_ACCOUNTANT


@router.message(F.text == "Бухгалтер")
async def open_accountant(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    await message.answer("Бухгалтерия:", reply_markup=accountant_menu())


@router.message(F.text == "Продажа")
async def sale_start(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    await state.set_state(SaleStates.item)
    await message.answer("Что продали?")


@router.message(SaleStates.item)
async def sale_item(message: Message, state: FSMContext):
    await state.update_data(item=message.text)
    await state.set_state(SaleStates.total)
    await message.answer("Сумма продажи?")


@router.message(SaleStates.total)
async def sale_total(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", ".").strip()
    try:
        total = float(text)
    except ValueError:
        await message.answer("Введите сумму числом.")
        return
    await state.update_data(total=total)
    await state.set_state(SaleStates.paid)
    await message.answer("Оплатили сейчас?")


@router.message(SaleStates.paid)
async def sale_paid(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", ".").strip()
    try:
        paid = float(text)
    except ValueError:
        await message.answer("Введите сумму числом.")
        return
    await state.update_data(paid=paid)
    await state.set_state(SaleStates.debt)
    await message.answer("Долг?")


@router.message(SaleStates.debt)
async def sale_debt(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", ".").strip()
    try:
        debt = float(text)
    except ValueError:
        await message.answer("Введите сумму числом.")
        return
    await state.update_data(debt=debt)
    await state.set_state(SaleStates.comment)
    await message.answer("Комментарий (можно пусто):")


@router.message(SaleStates.comment)
async def sale_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    await repo.add_sale(
        user_id=int(user["id"]),
        item=str(data.get("item")),
        total=float(data.get("total")),
        paid=float(data.get("paid")),
        debt=float(data.get("debt")),
        comment=message.text,
    )
    await state.clear()
    await message.answer("Продажа сохранена.", reply_markup=accountant_menu())


@router.message(F.text == "Расход")
async def expense_start(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    await state.set_state(ExpenseStates.item)
    await message.answer("На что расход?")


@router.message(ExpenseStates.item)
async def expense_item(message: Message, state: FSMContext):
    await state.update_data(item=message.text)
    await state.set_state(ExpenseStates.amount)
    await message.answer("Сумма?")


@router.message(ExpenseStates.amount)
async def expense_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(text)
    except ValueError:
        await message.answer("Введите сумму числом.")
        return
    await state.update_data(amount=amount)
    await state.set_state(ExpenseStates.comment)
    await message.answer("Комментарий (можно пусто):")


@router.message(ExpenseStates.comment)
async def expense_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    await repo.add_expense(
        user_id=int(user["id"]),
        item=str(data.get("item")),
        amount=float(data.get("amount")),
        comment=message.text,
    )
    await state.clear()
    await message.answer("Расход сохранен.", reply_markup=accountant_menu())


@router.message(F.text == "Баланс")
async def balance(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    repo = await _get_repo(message)
    cash = await repo.calc_cash_balance()
    debt = await repo.calc_debt_total()
    today = _date_str(datetime.now())
    sales, expenses = await repo.calc_today_stats(today)
    await message.answer(
        f"В кассе: {cash}\nНам должны: {debt}\nПродажи сегодня: {sales}\nРасходы сегодня: {expenses}"
    )


@router.message(F.text.in_({"За сегодня", "За неделю", "За месяц"}))
async def reports(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    start = _period_start(message.text)
    repo = await _get_repo(message)
    sales = await repo.db.fetchone(
        "SELECT COALESCE(SUM(amount_total),0) AS s FROM sales WHERE substr(created_at,1,10) >= ?",
        (start,),
    )
    cash = await repo.db.fetchone(
        "SELECT COALESCE(SUM(amount_paid),0) AS s FROM sales WHERE substr(created_at,1,10) >= ?",
        (start,),
    )
    debts = await repo.db.fetchone(
        "SELECT COALESCE(SUM(amount_debt),0) AS s FROM sales WHERE substr(created_at,1,10) >= ?",
        (start,),
    )
    expenses = await repo.db.fetchone(
        "SELECT COALESCE(SUM(amount),0) AS s FROM expenses WHERE substr(created_at,1,10) >= ?",
        (start,),
    )
    balance = float(cash["s"]) - float(expenses["s"])
    await message.answer(
        f"Отчет {message.text}:\n"
        f"Продажи: {sales['s']}\n"
        f"Получено в кассу: {cash['s']}\n"
        f"Долги: {debts['s']}\n"
        f"Расходы: {expenses['s']}\n"
        f"Остаток: {balance}"
    )


@router.message(F.text == "Долги")
async def debts(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    repo = await _get_repo(message)
    rows = await repo.list_debts()
    if not rows:
        await message.answer("Долгов нет.")
        return
    lines = ["Долги:"]
    for d in rows:
        lines.append(f"#{d['id']} остаток: {d['amount_left']} из {d['amount_total']}")
    lines.append("Чтобы оплатить долг, напишите: Оплата долга")
    await message.answer("\n".join(lines))


@router.message(F.text == "Отчеты")
async def reports_menu(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    await message.answer("Выберите период: За сегодня / За неделю / За месяц")


@router.message(F.text == "Оплата долга")
async def debt_payment_start(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    await state.set_state(DebtPaymentStates.debt_id)
    await message.answer("Введите ID долга:")


@router.message(DebtPaymentStates.debt_id)
async def debt_payment_id(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужен ID числом.")
        return
    await state.update_data(debt_id=int(text))
    await state.set_state(DebtPaymentStates.amount)
    await message.answer("Сколько оплатили?")


@router.message(DebtPaymentStates.amount)
async def debt_payment_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(text)
    except ValueError:
        await message.answer("Введите сумму числом.")
        return
    await state.update_data(amount=amount)
    await state.set_state(DebtPaymentStates.comment)
    await message.answer("Комментарий (можно пусто):")


@router.message(DebtPaymentStates.comment)
async def debt_payment_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    await repo.add_debt_payment(
        debt_id=int(data.get("debt_id")),
        user_id=int(user["id"]),
        amount=float(data.get("amount")),
        comment=message.text,
    )
    await state.clear()
    await message.answer("Оплата долга сохранена.", reply_markup=accountant_menu())


@router.message(F.text == "История")
async def history(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    repo = await _get_repo(message)
    sales = await repo.list_recent_sales()
    expenses = await repo.list_recent_expenses()
    lines = ["История операций:"]
    for s in sales:
        lines.append(f"Продажа #{s['id']} {s['item']} сумма {s['amount_total']} ({s['created_at']})")
    for e in expenses:
        lines.append(f"Расход #{e['id']} {e['item']} сумма {e['amount']} ({e['created_at']})")
    await message.answer("\n".join(lines) if lines else "История пуста.")


@router.message(F.text == "Экспорт Excel")
async def export_excel(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    repo = await _get_repo(message)
    sales = await repo.list_recent_sales(1000)
    rows = [
        [s["id"], s["item"], s["amount_total"], s["amount_paid"], s["amount_debt"], s["comment"], s["created_at"]]
        for s in sales
    ]
    path = export_to_xlsx(
        headers=["ID", "Что", "Сумма", "Оплачено", "Долг", "Комментарий", "Дата"],
        rows=rows,
        out_dir=message.bot.exports_dir,
        prefix="sales",
    )
    await message.answer_document(document=FSInputFile(path), caption="Экспорт продаж")


@router.message(F.text == "Очистить")
async def clear_start(message: Message, state: FSMContext):
    if not await _ensure_accountant(message, state):
        raise SkipHandler
    await state.set_state(DeleteStates.section)
    await message.answer(
        "Точно хотите очистить данные? Рекомендуется сначала сделать экспорт Excel.",
        reply_markup=confirm_menu(),
    )


@router.message(DeleteStates.section, F.text.in_({"Да", "Нет"}))
async def clear_confirm(message: Message, state: FSMContext):
    if message.text == "Нет":
        await state.clear()
        await message.answer("Отменено.", reply_markup=accountant_menu())
        return
    repo = await _get_repo(message)
    await repo.delete_all_from("sales")
    await repo.delete_all_from("expenses")
    await repo.delete_all_from("debts")
    await repo.delete_all_from("debt_payments")
    await state.clear()
    await message.answer("Бухгалтерия очищена.", reply_markup=accountant_menu())
