# app/main.py

import logging
import asyncio
from app.core.validation_translator import translate_error_ru
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from aiogram import Dispatcher

from app.core.logging_config import setup_logging
from app.core.response import error
from app.routers import auth, user, reset_password, admin_router, test_router, subscription_router, referrals_router, transaction_router
from app.admin.telegram_2fa import bot, router as telegram_router


# Инициализация логирования
setup_logging()
logger = logging.getLogger(__name__)

# Создаём приложение
app = FastAPI(
    title="Royal_api!",
    description="TI KTO VAHE1?",
    version="1.0.1",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost",
        "https://royal-test.duckdns.org",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(user.router, prefix="/users", tags=["users"])
app.include_router(reset_password.router, prefix="/reset", tags=["reset-password"])
app.include_router(admin_router.router)
app.include_router(test_router.router, prefix="/tests", tags=["tests"])
app.include_router(subscription_router.router, prefix="/subscriptions")
app.include_router(referrals_router.router, prefix="/referrals", tags=["referrals"])
app.include_router(transaction_router.router, prefix="/transactions", tags=["transactions"])

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    path = request.url.path
    code = exc.status_code

    # Если detail — это просто строка
    if isinstance(exc.detail, str):
        return error(code=code, message=exc.detail, details={"path": path})

    # Если detail — словарь (с кастомным message)
    if isinstance(exc.detail, dict):
        details = exc.detail.copy()
        if "path" not in details:
            details["path"] = path
        return error(
            code=code,
            message=details.get("message", "Ошибка запроса"),
            details=details
        )

    # Стандартные коды
    if code == HTTP_405_METHOD_NOT_ALLOWED:
        return error(code, "Метод не разрешён", details={"method": request.method, "path": path})
    if code == HTTP_404_NOT_FOUND:
        return error(code, "Страница не найдена", details={"path": path})
    if code == HTTP_401_UNAUTHORIZED:
        return error(code, "Требуется авторизация", details={"path": path})
    if code == HTTP_403_FORBIDDEN:
        return error(code, "Доступ запрещён", details={"path": path})
    if code == HTTP_429_TOO_MANY_REQUESTS:
        return error(code, "Слишком много запросов", details={"hint": "Попробуйте позже", "path": path})

    # На всякий случай
    return error(code=code, message="Ошибка запроса", details={"path": path})




@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    error_list = []
    for err in exc.errors():
        field = err.get("loc", ["неизвестное поле"])[-1]
        message = err.get("msg", "Некорректное значение")
        # Удаляем префикс "Value error, " если он присутствует
        prefix = "Value error, "
        if message.startswith(prefix):
            message = message[len(prefix):]
        error_list.append({"field": field, "message": message})

    # Форматируем каждую ошибку в строку и объединяем через "; "
    formatted_error_details = "; ".join(
        [f"Поле «{item['field']}»: {item['message']}" for item in error_list]
    )
    return error(
        code=HTTP_422_UNPROCESSABLE_ENTITY,
        details="Ошибка валидации данных",
        message=formatted_error_details
    )

# Запуск Telegram-бота через polling
async def start_bot():
    dp = Dispatcher()
    dp.include_router(telegram_router)
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_bot())
