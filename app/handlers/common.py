from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards.common import make_main_menu
from app.services import roles
from app.services.auth import ensure_user, hash_pin, is_pin_valid_in_memory, set_pin_valid
from app.states.forms import PinStates

router = Router()


async def _get_repo(message: Message):
    return message.bot.repo


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if message.chat.type != "private":
        return
    repo = await _get_repo(message)
    settings = message.bot.settings

    default_role = roles.ROLE_EMPLOYEE
    if message.from_user and message.from_user.id in settings.director_ids:
        default_role = roles.ROLE_DIRECTOR

    user_id = await ensure_user(
        repo,
        message.from_user.id,
        message.from_user.full_name,
        message.from_user.username,
        default_role,
    )
    user = await repo.get_user_by_id(user_id)
    role = user["role"]

    if role == roles.ROLE_DIRECTOR and settings.pin_required_on_start:
        pin_hash = await repo.get_pin_hash(user_id)
        if pin_hash:
            await state.set_state(PinStates.waiting_pin)
            await state.update_data(pin_action="verify", user_id=user_id)
            await message.answer("Введите PIN-код директора:")
            return
        await state.set_state(PinStates.waiting_pin)
        await state.update_data(pin_action="set", user_id=user_id)
        await message.answer("Установите PIN-код директора (4-8 цифр):")
        return

    await message.answer(
        f"Здравствуйте! Ваша роль: {role}.",
        reply_markup=make_main_menu(role),
    )
    await state.update_data(current_menu=None)


@router.message(PinStates.waiting_pin)
async def pin_flow(message: Message, state: FSMContext):
    repo = await _get_repo(message)
    data = await state.get_data()
    user_id = int(data.get("user_id"))
    action = data.get("pin_action")
    pin = (message.text or "").strip()
    if not pin.isdigit() or not (4 <= len(pin) <= 8):
        await message.answer("PIN должен быть 4-8 цифр. Попробуйте снова:")
        return

    if action == "set":
        await repo.set_pin(user_id, hash_pin(pin))
        set_pin_valid(user_id)
        await state.clear()
        user = await repo.get_user_by_id(user_id)
        await message.answer(
            "PIN-код установлен.",
            reply_markup=make_main_menu(user["role"]),
        )
        return

    stored = await repo.get_pin_hash(user_id)
    if stored and stored == hash_pin(pin):
        set_pin_valid(user_id)
        await state.clear()
        user = await repo.get_user_by_id(user_id)
        await message.answer(
            "Доступ подтвержден.",
            reply_markup=make_main_menu(user["role"]),
        )
        return

    await message.answer("Неверный PIN. Попробуйте снова:")


async def require_director_pin(message: Message, state: FSMContext) -> bool:
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    if not user or user["role"] != roles.ROLE_DIRECTOR:
        return False
    if is_pin_valid_in_memory(int(user["id"])):
        return True

    await state.set_state(PinStates.waiting_pin)
    await state.update_data(pin_action="verify", user_id=int(user["id"]))
    await message.answer("Введите PIN-код директора:")
    return False


@router.message(F.text == "Назад")
async def back_to_main(message: Message, state: FSMContext):
    repo = await _get_repo(message)
    user = await repo.get_user_by_tg(message.from_user.id)
    if not user:
        return
    await state.update_data(current_menu=None)
    await message.answer("Главное меню:", reply_markup=make_main_menu(user["role"]))
