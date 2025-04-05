# app/main.py

import logging
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logging_config import setup_logging
from app.core.config import settings
from app.routers import auth, user, reset_password, admin_router, test_router, subscription_router
from aiogram import Dispatcher
from app.admin.telegram_2fa import bot, router as telegram_router
from fastapi.staticfiles import StaticFiles

# Инициализация логирования
setup_logging()
logger = logging.getLogger(__name__)

# Создаём приложение
app = FastAPI(
    title="Royal_api!",
    description="TI KTO VAHE1?",
    version="1.0.0"
)

# CORS (для доступа с фронта)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(user.router, prefix="/users", tags=["users"])
app.include_router(reset_password.router, prefix="/reset", tags=["reset-password"])
app.include_router(admin_router.router)
app.include_router(test_router.router, prefix="/tests", tags=["tests"])
app.include_router(subscription_router.router, prefix="/subscriptions", tags=["subscriptions"])

app.mount("/", StaticFiles(directory="html_testing", html=True), name="static")

# Пример простого эндпоинта
@app.get("/")
def root():
    logger.info("Root endpoint called.")
    return {"message": "Hello from Pizdes!"}

# Запуск Telegram-бота через polling
async def start_bot():
    dp = Dispatcher()
    dp.include_router(telegram_router)
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_bot())