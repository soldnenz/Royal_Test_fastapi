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

    # Настройки безопасности / JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 31

    TELEGRAM_BOT_TOKEN: str
    SUPER_ADMIN_IDS: str  # можно преобразовать позже в list[int

    pdd_categories: List[str]
    max_file_size_mb: int
    allowed_media_types: List[str]
    PDD_SECTIONS: Json[List[Dict[str, Any]]]
    DEFAULT_REFERRAL_RATE: int
    
    # Настройки медиафайлов
    MEDIA_BASE_PATH: str = "../video_test"  # Корневая папка проекта
    MEDIA_X_ACCEL_PREFIX: str = "/media"
    MEDIA_MAX_FILE_SIZE_MB: int = 50
    
    # Turnstile settings
    TURNSTILE_SECRET_KEY: str = ""  # Добавьте ваш секретный ключ здесь
    MEDIA_ALLOWED_TYPES: List[str] = [
        "video/mp4", "video/avi", "video/mov", "video/wmv", "video/flv",
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "audio/mpeg", "audio/wav", "audio/ogg", "audio/mp3",
        "application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    class Config:
        # Сообщаем Pydantic брать переменные окружения
        env_file = ".env"
        # Если нужно указать префикс для всех переменных:
        # env_prefix = "MYAPP_"
        # Тогда бы ждали: MYAPP_MONGO_URI, MYAPP_MONGO_DB_NAME, ...
        #
        # Но в данном примере не используем префикс

# Создаём экземпляр класса, и теперь по всему проекту можно импортировать
settings = Settings()
