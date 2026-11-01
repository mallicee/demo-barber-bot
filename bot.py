"""Точка входа: запуск бота «Demo Barber».

Запуск:  python bot.py
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, ErrorEvent
from aiogram.utils.token import TokenValidationError

from app.config import config  # при ошибке в .env программа остановится здесь с подсказкой
from app.database import init_db
from app.handlers import admin, booking, common, fallback, my_bookings

log = logging.getLogger("bot")


async def on_error(event: ErrorEvent) -> bool:
    """Любая непредвиденная ошибка в обработчике записывается в лог,
    а бот продолжает работать."""
    log.exception("Ошибка при обработке обновления: %s", event.exception,
                  exc_info=event.exception)
    return True


async def set_commands(bot: Bot) -> None:
    """Команды в меню Telegram (кнопка «Меню» слева от поля ввода)."""
    user_commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="id", description="Узнать мой Telegram ID"),
    ]
    await bot.set_my_commands(user_commands)
    if config.admin_id:
        try:
            await bot.set_my_commands(
                user_commands + [BotCommand(command="admin", description="Панель владельца")],
                scope=BotCommandScopeChat(chat_id=config.admin_id),
            )
        except TelegramAPIError:
            log.warning("Не удалось установить команды админа. "
                        "Напишите боту /start со своего аккаунта и перезапустите.")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    await init_db()

    try:
        bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    except TokenValidationError:
        log.error("BOT_TOKEN в .env имеет неверный формат. Скопируйте токен "
                  "от @BotFather целиком, без пробелов и кавычек.")
        return

    dp = Dispatcher(storage=MemoryStorage())
    # Порядок важен: admin раньше common, fallback — всегда последним
    dp.include_routers(admin.router, common.router, booking.router,
                       my_bookings.router, fallback.router)
    dp.errors.register(on_error)

    try:
        me = await bot.get_me()
    except TelegramUnauthorizedError:
        log.error("Telegram не принял BOT_TOKEN. Проверьте токен в .env "
                  "(при необходимости выпустите новый в @BotFather: /token).")
        await bot.session.close()
        return

    await set_commands(bot)
    if not config.admin_id:
        log.warning("ADMIN_ID не указан: уведомления и /admin отключены. "
                    "Отправьте боту /id, впишите число в .env и перезапустите бота.")

    log.info("Бот @%s запущен. Остановить: Ctrl+C", me.username)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
