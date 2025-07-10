import asyncio
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import uvicorn
from uvicorn.config import Config
from uvicorn.server import Server
from log_system import get_2fa_logger, LogSection, LogSubsection
from config import settings
from telegram_bot import router as telegram_router, bot

# Инициализируем логгер
logger = get_2fa_logger()

# Создаем диспетчер для Telegram бота и подключаем роутер
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(telegram_router)


async def start_telegram_bot():
    """Запуск Telegram бота"""
    try:
        logger.info(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.STARTUP,
            message="Запускаем Telegram бота для 2FA"
        )
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(
            section=LogSection.TELEGRAM,
            subsection=LogSubsection.TELEGRAM.BOT_ERROR,
            message=f"Ошибка запуска Telegram бота: {str(e)}"
        )


async def main():
    """Основная функция запуска"""
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.STARTUP,
        message="Запуск 2FA микросервиса"
    )
    
    # Запускаем Telegram бота
    bot_task = asyncio.create_task(start_telegram_bot())
    
    # Настраиваем и запускаем uvicorn
    config = Config(
        app="app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower()
    )
    server = Server(config=config)
    
    # Запускаем сервер в отдельной задаче
    api_task = asyncio.create_task(server.serve())
    
    try:
        # Ждем завершения обеих задач (что не должно произойти в нормальных условиях)
        await asyncio.gather(bot_task, api_task)
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.ERROR,
            message=f"Критическая ошибка: {str(e)}"
        )
    finally:
        # Останавливаем все задачи при выходе
        for task in [bot_task, api_task]:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


if __name__ == "__main__":
    # Запускаем все в асинхронном режиме
    asyncio.run(main()) 