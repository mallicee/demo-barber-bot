"""Данные, которые «зашиты» в inline-кнопки (callback_data).

Каждый класс — тип кнопки. aiogram сам упаковывает их в строку
вида 'srv:3' и распаковывает обратно при нажатии.
"""

from aiogram.filters.callback_data import CallbackData


class MenuCb(CallbackData, prefix="menu"):
    action: str  # main / services / book / my / contacts / about


class ServiceCb(CallbackData, prefix="srv"):
    service_id: int


class DateCb(CallbackData, prefix="date"):
    day: str  # ГГГГ-ММ-ДД


class TimeCb(CallbackData, prefix="time"):
    hour: int  # час без минут (двоеточие в callback_data использовать нельзя)


class BackCb(CallbackData, prefix="back"):
    to: str  # service / date / time / phone


class ConfirmCb(CallbackData, prefix="confirm"):
    ok: bool


class MyCancelCb(CallbackData, prefix="mycancel"):
    booking_id: int
    sure: bool  # False — спросить «точно?», True — отменить


class AdminCb(CallbackData, prefix="adm"):
    action: str  # menu / today / week / cancel


class AdminCancelCb(CallbackData, prefix="admcancel"):
    booking_id: int
    sure: bool
