from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Dict

from aiogram.types import Message

from app.db.repository import Repository

_PIN_TTL_MINUTES = 30
_pin_cache: Dict[int, datetime] = {}


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def is_private_chat(message: Message) -> bool:
    return message.chat.type == "private"


def is_pin_valid_in_memory(user_id: int) -> bool:
    now = datetime.utcnow()
    exp = _pin_cache.get(user_id)
    return exp is not None and exp > now


def set_pin_valid(user_id: int) -> None:
    _pin_cache[user_id] = datetime.utcnow() + timedelta(minutes=_PIN_TTL_MINUTES)


def clear_pin(user_id: int) -> None:
    _pin_cache.pop(user_id, None)


async def ensure_user(repo: Repository, tg_id: int, full_name: str, username: str | None, role_default: str) -> int:
    user = await repo.get_user_by_tg(tg_id)
    if user:
        return int(user["id"])
    return await repo.create_user(tg_id, full_name, username, role_default)
