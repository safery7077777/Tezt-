import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from config import settings
from handlers import get_handlers_router

# Настройка логирования в стандартный вывод (STDOUT) для отслеживания на Railway
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def main():
    if not settings.BOT_TOKEN:
        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Токен бота BOT_TOKEN отсутствует в конфигурации!")
        return

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(get_handlers_router())

    logger.info("Запуск бота Kratz | mines...")
    try:
        # Сброс старых вебхуков и запуск Long Polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception(f"Критическая ошибка при работе бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот успешно остановлен.")
