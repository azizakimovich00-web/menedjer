from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Iterable, List, Optional, Tuple

import aiosqlite

ISO_FORMAT = "%Y-%m-%d %H:%M:%S"


def utcnow_str() -> str:
    return datetime.utcnow().strftime(ISO_FORMAT)


class Database:
    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self._path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA foreign_keys = ON;")
            await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        if self._conn is None:
            raise RuntimeError("Database not connected")
        await self._conn.execute(query, tuple(params))
        await self._conn.commit()

    async def executemany(self, query: str, seq: Iterable[Iterable[Any]]) -> None:
        if self._conn is None:
            raise RuntimeError("Database not connected")
        await self._conn.executemany(query, [tuple(x) for x in seq])
        await self._conn.commit()

    async def fetchone(self, query: str, params: Iterable[Any] = ()) -> Optional[aiosqlite.Row]:
        if self._conn is None:
            raise RuntimeError("Database not connected")
        async with self._conn.execute(query, tuple(params)) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: Iterable[Any] = ()) -> List[aiosqlite.Row]:
        if self._conn is None:
            raise RuntimeError("Database not connected")
        async with self._conn.execute(query, tuple(params)) as cursor:
            return await cursor.fetchall()


async def init_db(db: Database) -> None:
    await db.connect()

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE NOT NULL,
            full_name TEXT,
            username TEXT,
            role TEXT NOT NULL DEFAULT 'employee',
            created_at TEXT NOT NULL
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS pins (
            user_id INTEGER UNIQUE NOT NULL,
            pin_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            amount_total REAL NOT NULL,
            amount_paid REAL NOT NULL,
            amount_debt REAL NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            amount REAL NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            amount_total REAL NOT NULL,
            amount_left REAL NOT NULL,
            created_at TEXT NOT NULL,
            closed_at TEXT
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS debt_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debt_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(debt_id) REFERENCES debts(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            comment TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            client_id INTEGER,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            comment TEXT,
            deadline_date TEXT,
            responsible_user_id INTEGER,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(request_id) REFERENCES requests(id),
            FOREIGN KEY(client_id) REFERENCES clients(id),
            FOREIGN KEY(responsible_user_id) REFERENCES users(id)
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_id INTEGER NOT NULL,
            assignee_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            comment TEXT,
            status TEXT NOT NULL,
            completed_at TEXT,
            not_done_reason TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(manager_id) REFERENCES users(id),
            FOREIGN KEY(assignee_id) REFERENCES users(id)
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            unit TEXT NOT NULL,
            current_qty REAL NOT NULL DEFAULT 0
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS material_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            qty REAL NOT NULL,
            action TEXT NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(material_id) REFERENCES materials(id)
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            category TEXT NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS personal_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            director_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            comment TEXT,
            status TEXT NOT NULL,
            completed_at TEXT,
            not_done_reason TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(director_id) REFERENCES users(id)
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            payload TEXT,
            scheduled_at TEXT NOT NULL,
            sent_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            section TEXT NOT NULL,
            period TEXT NOT NULL,
            file_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_type TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    await _seed_materials(db)


async def _seed_materials(db: Database) -> None:
    materials = [
        ("Баннер", "м2"),
        ("Самоклейка", "м2"),
        ("Сетка", "м2"),
        ("Плоттерная пленка", "м2"),
        ("Форекс 3 мм", "лист"),
        ("Форекс 5 мм", "лист"),
    ]
    rows = await db.fetchall("SELECT name FROM materials")
    existing = {row["name"] for row in rows}
    to_insert = [(name, unit, 0) for name, unit in materials if name not in existing]
    if to_insert:
        await db.executemany(
            "INSERT INTO materials (name, unit, current_qty) VALUES (?, ?, ?)",
            to_insert,
        )


async def init_db_sync(path: str) -> None:
    db = Database(path)
    await init_db(db)
    await db.close()


if __name__ == "__main__":
    asyncio.run(init_db_sync("D:\\boty oflayn\\menedjer\\data\\bot.db"))
