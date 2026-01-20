# app/core/config.py

import os
from pydantic_settings import BaseSettings
from pydantic import Json
from dotenv import load_dotenv
from typing import List, Dict, Any

# Загружаем переменные окружения из .env (если нужен dotenv)
load_dotenv()

class Settings(BaseSettings):
    # Настройки MongoDB
    MONGO_URI: str
    MONGO_DB_NAME: str

    # Настройки Redis для рейт лимитов
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "Royal_Redis_1337"  # Устанавливаем пароль по умолчанию
    REDIS_DB: int = 1  # Используем БД 1 для рейт лимитов
    REDIS_MULTIPLAYER_DB: int = 2 # Используем БД 2 для мультиплеера
    REDIS_RATE_LIMIT_PREFIX: str = "royal_rate_limit"
    REDIS_FAIL_OPEN: bool = True
    REDIS_WARNING_THRESHOLD: float = 0.8

    # Настройки безопасности / JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 31
    
    # Настройки окружения
    ENVIRONMENT: str = "development"  # development или production
    REQUIRE_2FA: bool = False  # Требовать 2FA для админов (по умолчанию отключено)

    TELEGRAM_BOT_TOKEN: str
    SUPER_ADMIN_IDS: str  # можно преобразовать позже в list[int

    pdd_categories: List[str]
    max_file_size_mb: int
    allowed_media_types: List[str]
    PDD_SECTIONS: Json[List[Dict[str, Any]]]
    DEFAULT_REFERRAL_RATE: int
    
    # Настройки медиафайлов
    MEDIA_BASE_PATH: str = "video_test"  # Корневая папка для медиа файлов
    MEDIA_X_ACCEL_PREFIX: str = "/media"
    MEDIA_MAX_FILE_SIZE_MB: int = 50
    MEDIA_ALLOWED_TYPES: List[str] = [
        "video/mp4", "video/avi", "video/mov", "video/wmv", "video/flv",
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "audio/mpeg", "audio/wav", "audio/ogg", "audio/mp3",
        "application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    class Config:
        # Сообщаем Pydantic брать переменные окружения
        env_file = ".env"
        env_file_encoding = 'utf-8'
        # Если нужно указать префикс для всех переменных:
        # env_prefix = "MYAPP_"
        # Тогда бы ждали: MYAPP_MONGO_URI, MYAPP_MONGO_DB_NAME, ...
        #
        # Но в данном примере не используем префикс

# Создаём экземпляр класса, и теперь по всему проекту можно импортировать
settings = Settings()
