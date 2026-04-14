from __future__ import annotations

from typing import Optional

from app.db.database import Database, utcnow_str

ALLOWED_DELETE_TABLES = {
    "clients",
    "contacts",
    "debt_payments",
    "debts",
    "expenses",
    "material_history",
    "orders",
    "sales",
    "tasks",
}


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def get_user_by_tg(self, tg_id: int):
        return await self.db.fetchone("SELECT * FROM users WHERE tg_id = ?", (tg_id,))

    async def create_user(self, tg_id: int, full_name: str, username: str | None, role: str) -> int:
        user_id = await self.db.fetchval(
            """
            INSERT INTO users (tg_id, full_name, username, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
            """,
            (tg_id, full_name, username, role, utcnow_str()),
        )
        return int(user_id or 0)

    async def set_role(self, user_id: int, role: str) -> None:
        await self.db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))

    async def set_pin(self, user_id: int, pin_hash: str) -> None:
        await self.db.execute(
            """
            INSERT INTO pins (user_id, pin_hash, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE
            SET pin_hash = EXCLUDED.pin_hash,
                updated_at = EXCLUDED.updated_at
            """,
            (user_id, pin_hash, utcnow_str()),
        )

    async def get_pin_hash(self, user_id: int) -> Optional[str]:
        row = await self.db.fetchone("SELECT pin_hash FROM pins WHERE user_id = ?", (user_id,))
        return str(row["pin_hash"]) if row else None

    async def add_sale(
        self,
        user_id: int,
        item: str,
        total: float,
        paid: float,
        debt: float,
        comment: str | None,
    ) -> int:
        sale_id = await self.db.fetchval(
            """
            INSERT INTO sales (user_id, item, amount_total, amount_paid, amount_debt, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (user_id, item, total, paid, debt, comment, utcnow_str()),
        )
        if debt > 0 and sale_id is not None:
            await self.db.execute(
                """
                INSERT INTO debts (source_type, source_id, amount_total, amount_left, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("sale", int(sale_id), total, debt, utcnow_str()),
            )
        return int(sale_id or 0)

    async def add_expense(self, user_id: int, item: str, amount: float, comment: str | None):
        await self.db.execute(
            "INSERT INTO expenses (user_id, item, amount, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, item, amount, comment, utcnow_str()),
        )

    async def add_request(self, user_id: int, name: str, phone: str, comment: str | None) -> int:
        req_id = await self.db.fetchval(
            """
            INSERT INTO requests (user_id, name, phone, comment, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (user_id, name, phone, comment, "Новая", utcnow_str()),
        )
        await self._upsert_client(name, phone, comment)
        return int(req_id or 0)

    async def add_photo(self, owner_type: str, owner_id: int, file_id: str) -> None:
        await self.db.execute(
            "INSERT INTO photos (owner_type, owner_id, file_id, created_at) VALUES (?, ?, ?, ?)",
            (owner_type, owner_id, file_id, utcnow_str()),
        )

    async def add_task(self, manager_id: int, assignee_id: int, title: str, due_date: str, comment: str | None):
        await self.db.execute(
            """
            INSERT INTO tasks (manager_id, assignee_id, title, due_date, comment, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (manager_id, assignee_id, title, due_date, comment, "Новая", utcnow_str()),
        )

    async def list_tasks_for_user_on_date(self, user_id: int, date_str: str):
        return await self.db.fetchall(
            "SELECT * FROM tasks WHERE assignee_id = ? AND due_date = ? ORDER BY id DESC",
            (user_id, date_str),
        )

    async def list_tasks_by_date(self, date_str: str):
        return await self.db.fetchall(
            "SELECT * FROM tasks WHERE due_date = ? ORDER BY id DESC",
            (date_str,),
        )

    async def get_task(self, task_id: int):
        return await self.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))

    async def add_material_movement(
        self,
        user_id: int,
        material_id: int,
        qty: float,
        action: str,
        comment: str | None,
    ):
        await self.db.execute(
            "UPDATE materials SET current_qty = current_qty + ? WHERE id = ?",
            (qty, material_id),
        )
        await self.db.execute(
            """
            INSERT INTO material_history (user_id, material_id, qty, action, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, material_id, qty, action, comment, utcnow_str()),
        )

    async def list_materials(self):
        return await self.db.fetchall("SELECT * FROM materials ORDER BY name")

    async def get_material_by_name(self, name: str):
        return await self.db.fetchone("SELECT * FROM materials WHERE name = ?", (name,))

    async def add_contact(self, name: str, phone: str, category: str, comment: str | None):
        await self.db.execute(
            "INSERT INTO contacts (name, phone, category, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, phone, category, comment, utcnow_str()),
        )

    async def add_personal_task(self, director_id: int, title: str, due_date: str, comment: str | None):
        await self.db.execute(
            """
            INSERT INTO personal_tasks (director_id, title, due_date, comment, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (director_id, title, due_date, comment, "Новая", utcnow_str()),
        )

    async def list_personal_tasks(self, director_id: int, date_str: str):
        return await self.db.fetchall(
            "SELECT * FROM personal_tasks WHERE director_id = ? AND due_date = ? ORDER BY id DESC",
            (director_id, date_str),
        )

    async def list_users(self):
        return await self.db.fetchall("SELECT * FROM users ORDER BY created_at DESC")

    async def get_user_by_id(self, user_id: int):
        return await self.db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))

    async def list_recent_sales(self, limit: int = 50):
        return await self.db.fetchall(
            "SELECT * FROM sales ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    async def list_recent_expenses(self, limit: int = 50):
        return await self.db.fetchall(
            "SELECT * FROM expenses ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    async def calc_cash_balance(self):
        paid_sum = await self.db.fetchone("SELECT COALESCE(SUM(amount_paid), 0) AS s FROM sales")
        expense_sum = await self.db.fetchone("SELECT COALESCE(SUM(amount), 0) AS s FROM expenses")
        return float(paid_sum["s"]) - float(expense_sum["s"])

    async def calc_debt_total(self):
        row = await self.db.fetchone("SELECT COALESCE(SUM(amount_left), 0) AS s FROM debts")
        return float(row["s"]) if row else 0.0

    async def calc_today_stats(self, date_str: str):
        sales = await self.db.fetchone(
            "SELECT COALESCE(SUM(amount_total), 0) AS s FROM sales WHERE substring(created_at, 1, 10) = ?",
            (date_str,),
        )
        expenses = await self.db.fetchone(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM expenses WHERE substring(created_at, 1, 10) = ?",
            (date_str,),
        )
        return float(sales["s"]), float(expenses["s"])

    async def list_debts(self):
        return await self.db.fetchall("SELECT * FROM debts WHERE amount_left > 0 ORDER BY id DESC")

    async def add_debt_payment(self, debt_id: int, user_id: int, amount: float, comment: str | None):
        await self.db.execute(
            "INSERT INTO debt_payments (debt_id, user_id, amount, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (debt_id, user_id, amount, comment, utcnow_str()),
        )
        await self.db.execute(
            "UPDATE debts SET amount_left = GREATEST(amount_left - ?, 0) WHERE id = ?",
            (amount, debt_id),
        )
        await self.db.execute(
            "UPDATE debts SET closed_at = ? WHERE amount_left <= 0 AND id = ?",
            (utcnow_str(), debt_id),
        )

    async def list_orders_for_user(self, user_id: int, role: str):
        if role in {"director", "manager"}:
            return await self.db.fetchall("SELECT * FROM orders ORDER BY id DESC")
        return await self.db.fetchall(
            "SELECT * FROM orders WHERE responsible_user_id = ? ORDER BY id DESC",
            (user_id,),
        )

    async def list_requests(self):
        return await self.db.fetchall("SELECT * FROM requests ORDER BY id DESC")

    async def list_contacts(self):
        return await self.db.fetchall("SELECT * FROM contacts ORDER BY id DESC")

    async def add_order(
        self,
        name: str,
        phone: str,
        comment: str | None,
        deadline_date: str | None,
        responsible_user_id: int | None,
    ) -> int:
        client_id = await self._upsert_client(name, phone, comment)
        order_id = await self.db.fetchval(
            """
            INSERT INTO orders (client_id, name, phone, comment, deadline_date, responsible_user_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (client_id, name, phone, comment, deadline_date, responsible_user_id, "Новый", utcnow_str()),
        )
        return int(order_id or 0)

    async def update_order_status(self, order_id: int, status: str) -> None:
        await self.db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))

    async def list_orders_by_status(self, statuses: list[str]):
        placeholders = ",".join(["?"] * len(statuses))
        return await self.db.fetchall(
            f"SELECT * FROM orders WHERE status IN ({placeholders}) ORDER BY id DESC",
            statuses,
        )

    async def list_orders_by_deadline(self, date_str: str):
        return await self.db.fetchall(
            "SELECT * FROM orders WHERE deadline_date = ? ORDER BY id DESC",
            (date_str,),
        )

    async def list_clients(self):
        return await self.db.fetchall("SELECT * FROM clients ORDER BY id DESC")

    async def search_clients(self, query: str):
        q = f"%{query}%"
        return await self.db.fetchall(
            "SELECT * FROM clients WHERE name ILIKE ? OR phone ILIKE ? ORDER BY id DESC",
            (q, q),
        )

    async def get_client_by_phone(self, phone: str):
        return await self.db.fetchone("SELECT * FROM clients WHERE phone = ?", (phone,))

    async def list_client_history(self, phone: str):
        reqs = await self.db.fetchall("SELECT * FROM requests WHERE phone = ? ORDER BY id DESC", (phone,))
        orders = await self.db.fetchall("SELECT * FROM orders WHERE phone = ? ORDER BY id DESC", (phone,))
        return reqs, orders

    async def delete_all_from(self, table: str) -> None:
        if table not in ALLOWED_DELETE_TABLES:
            raise ValueError(f"Deleting from table '{table}' is not allowed")
        await self.db.execute(f"DELETE FROM {table}")

    async def delete_all_photos_for(self, owner_type: str):
        await self.db.execute("DELETE FROM photos WHERE owner_type = ?", (owner_type,))

    async def list_photos_for(self, owner_type: str, owner_id: int):
        return await self.db.fetchall(
            "SELECT * FROM photos WHERE owner_type = ? AND owner_id = ? ORDER BY id",
            (owner_type, owner_id),
        )

    async def list_manager_history(self, limit: int = 100):
        return await self.db.fetchall(
            "SELECT * FROM requests ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    async def list_material_history(self, limit: int = 100):
        return await self.db.fetchall(
            "SELECT * FROM material_history ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    async def list_personal_history(self, director_id: int, limit: int = 100):
        return await self.db.fetchall(
            "SELECT * FROM personal_tasks WHERE director_id = ? ORDER BY id DESC LIMIT ?",
            (director_id, limit),
        )

    async def update_personal_task_status(self, task_id: int, status: str, reason: str | None = None) -> None:
        completed_at = utcnow_str() if status == "Выполнено" else None
        await self.db.execute(
            """
            UPDATE personal_tasks
            SET status = ?,
                completed_at = COALESCE(?, completed_at),
                not_done_reason = ?
            WHERE id = ?
            """,
            (status, completed_at, reason, task_id),
        )

    async def reschedule_personal_task(self, task_id: int, new_date: str) -> None:
        await self.db.execute("UPDATE personal_tasks SET due_date = ? WHERE id = ?", (new_date, task_id))

    async def update_task_status(self, task_id: int, status: str, reason: str | None = None) -> None:
        completed_at = utcnow_str() if status == "Выполнено" else None
        await self.db.execute(
            """
            UPDATE tasks
            SET status = ?,
                completed_at = COALESCE(?, completed_at),
                not_done_reason = ?
            WHERE id = ?
            """,
            (status, completed_at, reason, task_id),
        )

    async def _upsert_client(self, name: str, phone: str, comment: str | None) -> int:
        row = await self.get_client_by_phone(phone)
        if row:
            await self.db.execute(
                "UPDATE clients SET name = ?, comment = ? WHERE id = ?",
                (name, comment, int(row["id"])),
            )
            return int(row["id"])

        client_id = await self.db.fetchval(
            """
            INSERT INTO clients (name, phone, comment, created_at)
            VALUES (?, ?, ?, ?)
            RETURNING id
            """,
            (name, phone, comment, utcnow_str()),
        )
        return int(client_id or 0)
