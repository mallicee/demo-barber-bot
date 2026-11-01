"""Состояния пошаговой записи (FSM — конечный автомат)."""

from aiogram.fsm.state import State, StatesGroup


class Booking(StatesGroup):
    service = State()   # шаг 1: выбор услуги
    date = State()      # шаг 2: выбор даты
    time = State()      # шаг 3: выбор времени
    name = State()      # шаг 4: ввод имени
    phone = State()     # шаг 5: телефон
    confirm = State()   # итог: подтверждение
