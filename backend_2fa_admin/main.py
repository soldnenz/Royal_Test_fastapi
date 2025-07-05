import asyncio
import uvicorn
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from api import app
from telegram_bot import router as telegram_router
from database import get_database
from log_system import get_2fa_logger, LogSection, LogSubsection, close_all_rabbitmq_connections
from config import settings

logger = get_2fa_logger()

# Создаем диспетчер для Telegram бота
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(telegram_router)


async def start_telegram_bot():
    """Запуск Telegram бота"""
    try:
        from telegram_bot import bot
        logger.info(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.STARTUP,
            message="Запускаем Telegram бота для 2FA"
        )
        
        # Запускаем бота в фоновом режиме
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(
            section=LogSection.TELEGRAM,
            subsection=LogSubsection.TELEGRAM.BOT_ERROR,
            message=f"Ошибка запуска Telegram бота: {str(e)}"
        )


async def periodic_cleanup():
    """Периодическая очистка истекших запросов"""
    while True:
        try:
            await asyncio.sleep(300)  # Каждые 5 минут
            from telegram_bot import cleanup_expired_requests
            await cleanup_expired_requests()
        except Exception as e:
            logger.error(
                section=LogSection.SYSTEM,
                subsection=LogSection.SYSTEM.MAINTENANCE,
                message=f"Ошибка при периодической очистке: {str(e)}"
            )


@app.on_event("startup")
async def startup_event():
    """Событие запуска приложения"""
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.STARTUP,
        message=f"2FA микросервис запускается на {settings.host}:{settings.port}"
    )
    
    # Запускаем фоновые задачи
    asyncio.create_task(periodic_cleanup())
    asyncio.create_task(start_telegram_bot())


@app.on_event("shutdown")
async def shutdown_event():
    """Событие остановки приложения"""
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.SHUTDOWN,
        message="2FA микросервис останавливается"
    )
    
    # Закрываем RabbitMQ соединения
    await close_all_rabbitmq_connections()


if __name__ == "__main__":
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.STARTUP,
        message="Запуск 2FA микросервиса"
    )
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False,  # В продакшене отключаем автоперезагрузку
        log_level=settings.log_level.lower()
    ) 