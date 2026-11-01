"""Работа с базой данных SQLite (через aiosqlite).

Даты храним строкой 'ГГГГ-ММ-ДД', время 'ЧЧ:ММ' — такие строки
правильно сравниваются и сортируются как обычный текст.
"""

import sqlite3
from datetime import datetime

import aiosqlite

from app.config import config

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    username     TEXT,
    client_name  TEXT    NOT NULL,
    phone        TEXT    NOT NULL,
    service_id   INTEGER NOT NULL,
    service_name TEXT    NOT NULL,
    price        INTEGER NOT NULL,
    date         TEXT    NOT NULL,
    time         TEXT    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'active',  -- active / cancelled
    created_at   TEXT    NOT NULL
);

-- Защита от двойной записи: на одно время может быть только одна активная запись
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_slot
    ON bookings(date, time) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
"""


def _connect() -> aiosqlite.Connection:
    return aiosqlite.connect(config.db_path)


async def init_db() -> None:
    """Создаёт таблицы при первом запуске."""
    async with _connect() as db:
        await db.executescript(CREATE_SQL)
        await db.commit()


async def get_busy_times(date: str) -> set[str]:
    """Занятые времена на дату, например {'10:00', '15:00'}."""
    async with _connect() as db:
        cursor = await db.execute(
            "SELECT time FROM bookings WHERE date = ? AND status = 'active'", (date,)
        )
        return {row[0] for row in await cursor.fetchall()}


async def add_booking(
    *,
    user_id: int,
    username: str | None,
    client_name: str,
    phone: str,
    service_id: int,
    service_name: str,
    price: int,
    date: str,
    time: str,
) -> int | None:
    """Создаёт запись. Возвращает её номер или None, если время уже заняли."""
    async with _connect() as db:
        try:
            cursor = await db.execute(
                """INSERT INTO bookings
                   (user_id, username, client_name, phone, service_id,
                    service_name, price, date, time, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, username, client_name, phone, service_id,
                 service_name, price, date, time,
                 datetime.now().isoformat(timespec="seconds")),
            )
            await db.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Сработал уникальный индекс: кто-то успел занять это время
            return None


async def get_booking(booking_id: int) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_upcoming(today: str, now_time: str, user_id: int | None = None,
                       limit: int = 50) -> list[dict]:
    """Будущие активные записи (всех клиентов или одного user_id)."""
    sql = """SELECT * FROM bookings
             WHERE status = 'active'
               AND (date > ? OR (date = ? AND time > ?))"""
    params: list = [today, today, now_time]
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY date, time LIMIT ?"
    params.append(limit)
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(sql, params)
        return [dict(row) for row in await cursor.fetchall()]


async def get_bookings_between(date_from: str, date_to: str) -> list[dict]:
    """Активные записи в диапазоне дат (включительно) — для админа."""
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM bookings
               WHERE status = 'active' AND date BETWEEN ? AND ?
               ORDER BY date, time""",
            (date_from, date_to),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def cancel_booking(booking_id: int, user_id: int | None = None) -> bool:
    """Отменяет запись. True — если отменили сейчас, False — если она уже
    отменена или чужая. Так повторное нажатие кнопки ничего не ломает."""
    sql = "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND status = 'active'"
    params: list = [booking_id]
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    async with _connect() as db:
        cursor = await db.execute(sql, params)
        await db.commit()
        return cursor.rowcount == 1
