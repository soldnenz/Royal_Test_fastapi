# app/main.py

import logging
from fastapi import FastAPI
import pytz
from app.core.logging_config import setup_logging
from app.core.config import settings
from app.routers import auth, user, reset_password
from fastapi.middleware.cors import CORSMiddleware

# Инициализация логирования
setup_logging()
logger = logging.getLogger(__name__)

# Создаём приложение
app = FastAPI(
    title="Royal_api!",
    description="TI KTO VAHE1?",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # ← frontend на python http.server
        "http://127.0.0.1:3000",  # ← если обращаешься с 127.0.0.1
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Подключаем роутеры
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(user.router, prefix="/users", tags=["users"])
app.include_router(reset_password.router, prefix="/reset", tags=["reset-password"])

# Пример простого эндпоинта на корне
@app.get("/")
def root():
    logger.info("Root endpoint called.")
    return {"message": "Hello from FastAPI!"}
