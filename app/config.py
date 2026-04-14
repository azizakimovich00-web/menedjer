from __future__ import annotations

import os
import tempfile
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


def _get_temp_exports_dir() -> str:
    return os.path.join(tempfile.gettempdir(), "menedjer_exports")


@dataclass(frozen=True)
class Settings:
    bot_token: str
    director_ids: List[int]
    pin_required_on_start: bool
    database_url: str
    exports_dir: str
    db_pool_min_size: int
    db_pool_max_size: int
    db_connect_retries: int


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    exports_dir = os.getenv("EXPORTS_DIR", "").strip() or _get_temp_exports_dir()

    return Settings(
        bot_token=token,
        director_ids=_parse_ids(os.getenv("DIRECTOR_IDS")),
        pin_required_on_start=_parse_bool(os.getenv("PIN_REQUIRED_ON_START"), True),
        database_url=database_url,
        exports_dir=exports_dir,
        db_pool_min_size=int(os.getenv("DB_POOL_MIN_SIZE", "1")),
        db_pool_max_size=int(os.getenv("DB_POOL_MAX_SIZE", "10")),
        db_connect_retries=int(os.getenv("DB_CONNECT_RETRIES", "10")),
    )
