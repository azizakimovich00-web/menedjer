from aiogram.fsm.state import State, StatesGroup


class PinStates(StatesGroup):
    waiting_pin = State()


class SaleStates(StatesGroup):
    item = State()
    total = State()
    paid = State()
    debt = State()
    comment = State()


class ExpenseStates(StatesGroup):
    item = State()
    amount = State()
    comment = State()


class RequestStates(StatesGroup):
    name = State()
    phone = State()
    comment = State()
    photos = State()


class OrderStates(StatesGroup):
    name = State()
    phone = State()
    comment = State()
    deadline = State()
    responsible = State()
    photos = State()


class TaskStates(StatesGroup):
    assignee = State()
    title = State()
    due_date = State()
    comment = State()


class MaterialStates(StatesGroup):
    action = State()
    material = State()
    qty = State()
    comment = State()


class ContactStates(StatesGroup):
    name = State()
    phone = State()
    category = State()
    comment = State()


class PersonalTaskStates(StatesGroup):
    title = State()
    due_date = State()
    comment = State()


class RoleAssignStates(StatesGroup):
    user = State()
    role = State()


class DebtPaymentStates(StatesGroup):
    debt_id = State()
    amount = State()
    comment = State()


class DeleteStates(StatesGroup):
    section = State()
    confirm = State()


class EmployeeTaskStates(StatesGroup):
    not_done_reason = State()


class PersonalTaskActionStates(StatesGroup):
    not_done_reason = State()
    new_date = State()


class SearchStates(StatesGroup):
    query = State()
