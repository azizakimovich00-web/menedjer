from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def make_main_menu(role: str) -> ReplyKeyboardMarkup:
    if role == "director":
        buttons = [
            ["Бухгалтер", "Менеджер"],
            ["Контакты", "Сотрудники"],
            ["Мои дела"],
        ]
    elif role == "accountant":
        buttons = [["Бухгалтер"]]
    elif role == "manager":
        buttons = [
            ["Новая заявка", "Клиенты"],
            ["Заказы", "Задачи"],
            ["Материалы", "Напоминания"],
            ["Отчеты", "История"],
        ]
    else:
        buttons = [["Мои задачи", "Мои заказы"]]

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
    )


def accountant_menu() -> ReplyKeyboardMarkup:
    buttons = [
        ["Продажа", "Расход"],
        ["Баланс", "Долги"],
        ["Отчеты", "История"],
        ["Экспорт Excel", "Очистить"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
    )


def manager_menu() -> ReplyKeyboardMarkup:
    buttons = [
        ["Новая заявка", "Клиенты"],
        ["Заказы", "Задачи"],
        ["Материалы", "Напоминания"],
        ["Отчеты", "История"],
        ["Экспорт Excel", "Очистить"],
        ["Назад"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
    )


def employees_menu() -> ReplyKeyboardMarkup:
    buttons = [["Добавить сотрудника", "Список сотрудников"], ["Назначить роль", "Изменить роль"], ["Удалить доступ"], ["Назад"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
    )


def contacts_menu() -> ReplyKeyboardMarkup:
    buttons = [["Добавить контакт", "Все контакты"], ["Поиск", "Категории"], ["Экспорт Excel", "Очистить"], ["Назад"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
    )


def personal_menu() -> ReplyKeyboardMarkup:
    buttons = [["Добавить дело"], ["Сегодня", "Завтра"], ["Выполнено", "История"], ["Назад"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
    )


def tasks_menu() -> ReplyKeyboardMarkup:
    buttons = [["Добавить задачу"], ["Сегодня", "Завтра"], ["Выполненные"], ["Экспорт Excel", "Очистить"], ["Назад"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
    )


def materials_menu() -> ReplyKeyboardMarkup:
    buttons = [["Остатки"], ["Приход", "Списание"], ["История"], ["Экспорт Excel", "Очистить"], ["Назад"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
    )


def clients_menu() -> ReplyKeyboardMarkup:
    buttons = [["Все клиенты", "Поиск клиента"], ["История клиента"], ["Экспорт Excel", "Очистить"], ["Назад"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
    )


def orders_menu() -> ReplyKeyboardMarkup:
    buttons = [["Сегодня", "Завтра"], ["Все активные", "Завершенные"], ["Добавить заказ"], ["Экспорт Excel", "Очистить"], ["Назад"]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in buttons],
        resize_keyboard=True,
    )


def simple_back_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Назад")]],
        resize_keyboard=True,
    )


def confirm_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
