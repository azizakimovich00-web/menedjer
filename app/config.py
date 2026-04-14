from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _parse_ids(value: str | None) -> List[int]:
    if not value:
        return []
    ids: List[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


@dataclass(frozen=True)
class Settings:
    bot_token: str
    director_ids: List[int]
    pin_required_on_start: bool
    db_path: str



def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    return Settings(
        bot_token=token,
        director_ids=_parse_ids(os.getenv("DIRECTOR_IDS")),
        pin_required_on_start=_parse_bool(os.getenv("PIN_REQUIRED_ON_START"), True),
        db_path=os.getenv("DB_PATH", "D:\\boty oflayn\\menedjer\\data\\bot.db"),
    )
