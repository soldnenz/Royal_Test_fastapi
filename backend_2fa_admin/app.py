from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from log_system import get_2fa_logger, LogSection, LogSubsection, close_all_rabbitmq_connections
from config import settings

# Инициализируем логгер
logger = get_2fa_logger()

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events handler"""
    # Startup
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.STARTUP,
        message=f"2FA микросервис запускается на {settings.host}:{settings.port}"
    )
    
    # Запускаем фоновые задачи
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    yield  # Здесь приложение работает
    
    # Shutdown
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.SHUTDOWN,
        message="2FA микросервис останавливается"
    )
    
    # Отменяем фоновые задачи
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    # Закрываем RabbitMQ соединения
    await close_all_rabbitmq_connections()

# Создаем FastAPI приложение
app = FastAPI(
    title="2FA Service",
    description="Микросервис для двухфакторной аутентификации через Telegram",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальный обработчик исключений
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений"""
    logger.error(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.ERROR,
        message=f"Необработанное исключение: {str(exc)}",
        extra_data={
            "path": request.url.path,
            "method": request.method,
            "exception": str(exc)
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={"message": "Внутренняя ошибка сервера"}
    )

# Импортируем роуты после создания приложения
from api import router as api_router
app.include_router(api_router) 