# app/core/config.py

import os
from pydantic import BaseSettings
from dotenv import load_dotenv

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
