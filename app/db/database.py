from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

import asyncpg

ISO_FORMAT = "%Y-%m-%d %H:%M:%S"
_PLACEHOLDER_RE = re.compile(r"\?")


def utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime(ISO_FORMAT)


def _convert_placeholders(query: str) -> str:
    index = 0

    def repl(_: re.Match[str]) -> str:
        nonlocal index
        index += 1
        return f"${index}"

    return _PLACEHOLDER_RE.sub(repl, query)


class Database:
    def __init__(
        self,
        database_url: str,
        min_pool_size: int = 1,
        max_pool_size: int = 10,
        connect_retries: int = 10,
    ) -> None:
        self._database_url = database_url
        self._min_pool_size = min_pool_size
        self._max_pool_size = max_pool_size
        self._connect_retries = connect_retries
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is not None:
            return

        last_error: Exception | None = None
        for attempt in range(1, self._connect_retries + 1):
            try:
                self._pool = await asyncpg.create_pool(
                    dsn=self._database_url,
                    min_size=self._min_pool_size,
                    max_size=self._max_pool_size,
                    command_timeout=60,
                    server_settings={"application_name": "menedjer_bot"},
                )
                return
            except Exception as exc:  # pragma: no cover - retry path
                last_error = exc
                if attempt == self._connect_retries:
                    break
                await asyncio.sleep(min(attempt, 5))

        raise RuntimeError(f"Failed to connect to PostgreSQL: {last_error}") from last_error

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def execute(self, query: str, params: Iterable[Any] = ()) -> str:
        pool = self._require_pool()
        sql = _convert_placeholders(query)
        async with pool.acquire() as conn:
            return await conn.execute(sql, *tuple(params))

    async def executemany(self, query: str, seq: Iterable[Iterable[Any]]) -> None:
        pool = self._require_pool()
        sql = _convert_placeholders(query)
        rows = [tuple(item) for item in seq]
        if not rows:
            return
        async with pool.acquire() as conn:
            await conn.executemany(sql, rows)

    async def fetchone(self, query: str, params: Iterable[Any] = ()) -> asyncpg.Record | None:
        pool = self._require_pool()
        sql = _convert_placeholders(query)
        async with pool.acquire() as conn:
            return await conn.fetchrow(sql, *tuple(params))

    async def fetchall(self, query: str, params: Iterable[Any] = ()) -> list[asyncpg.Record]:
        pool = self._require_pool()
        sql = _convert_placeholders(query)
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *tuple(params))
            return list(rows)

    async def fetchval(self, query: str, params: Iterable[Any] = ()) -> Any:
        pool = self._require_pool()
        sql = _convert_placeholders(query)
        async with pool.acquire() as conn:
            return await conn.fetchval(sql, *tuple(params))

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database not connected")
        return self._pool


async def init_db(db: Database) -> None:
    await db.connect()

    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            tg_id BIGINT UNIQUE NOT NULL,
            full_name TEXT,
            username TEXT,
            role TEXT NOT NULL DEFAULT 'employee',
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pins (
            user_id BIGINT PRIMARY KEY,
            pin_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sales (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            item TEXT NOT NULL,
            amount_total NUMERIC(12, 2) NOT NULL,
            amount_paid NUMERIC(12, 2) NOT NULL,
            amount_debt NUMERIC(12, 2) NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            item TEXT NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS debts (
            id BIGSERIAL PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_id BIGINT NOT NULL,
            amount_total NUMERIC(12, 2) NOT NULL,
            amount_left NUMERIC(12, 2) NOT NULL,
            created_at TEXT NOT NULL,
            closed_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS debt_payments (
            id BIGSERIAL PRIMARY KEY,
            debt_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(debt_id) REFERENCES debts(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS requests (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            comment TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS clients (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS orders (
            id BIGSERIAL PRIMARY KEY,
            request_id BIGINT,
            client_id BIGINT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            comment TEXT,
            deadline_date TEXT,
            responsible_user_id BIGINT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(request_id) REFERENCES requests(id) ON DELETE SET NULL,
            FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE SET NULL,
            FOREIGN KEY(responsible_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id BIGSERIAL PRIMARY KEY,
            manager_id BIGINT NOT NULL,
            assignee_id BIGINT NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            comment TEXT,
            status TEXT NOT NULL,
            completed_at TEXT,
            not_done_reason TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(manager_id) REFERENCES users(id),
            FOREIGN KEY(assignee_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS materials (
            id BIGSERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            unit TEXT NOT NULL,
            current_qty NUMERIC(12, 2) NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS material_history (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            material_id BIGINT NOT NULL,
            qty NUMERIC(12, 2) NOT NULL,
            action TEXT NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(material_id) REFERENCES materials(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            category TEXT NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS personal_tasks (
            id BIGSERIAL PRIMARY KEY,
            director_id BIGINT NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            comment TEXT,
            status TEXT NOT NULL,
            completed_at TEXT,
            not_done_reason TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(director_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            type TEXT NOT NULL,
            payload TEXT,
            scheduled_at TEXT NOT NULL,
            sent_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS exports (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            section TEXT NOT NULL,
            period TEXT NOT NULL,
            file_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS photos (
            id BIGSERIAL PRIMARY KEY,
            owner_type TEXT NOT NULL,
            owner_id BIGINT NOT NULL,
            file_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_expenses_created_at ON expenses(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_requests_phone ON requests(phone)",
        "CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(phone)",
        "CREATE INDEX IF NOT EXISTS idx_orders_deadline_date ON orders(deadline_date)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)",
        "CREATE INDEX IF NOT EXISTS idx_personal_tasks_due_date ON personal_tasks(due_date)",
        "CREATE INDEX IF NOT EXISTS idx_material_history_created_at ON material_history(created_at)",
    ]

    for statement in statements:
        await db.execute(statement)

    await _seed_materials(db)


async def _seed_materials(db: Database) -> None:
    materials = [
        ("Баннер", "м2", 0),
        ("Самоклейка", "м2", 0),
        ("Сетка", "м2", 0),
        ("Плоттерная пленка", "м2", 0),
        ("Форекс 3 мм", "лист", 0),
        ("Форекс 5 мм", "лист", 0),
    ]
    await db.executemany(
        """
        INSERT INTO materials (name, unit, current_qty)
        VALUES (?, ?, ?)
        ON CONFLICT (name) DO NOTHING
        """,
        materials,
    )


async def init_db_sync(database_url: str) -> None:
    db = Database(database_url)
    await init_db(db)
    await db.close()


if __name__ == "__main__":
    import os

    asyncio.run(init_db_sync(os.getenv("DATABASE_URL", "")))
