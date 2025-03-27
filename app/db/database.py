# app/db/database.py

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Загрузим переменные из .env (если используете python-dotenv)
load_dotenv()

# Извлекаем необходимые переменные окружения
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME")

if not MONGO_URI:
    raise ValueError("MONGO_URI is not set in environment variables.")
if not MONGO_DB_NAME:
    raise ValueError("MONGO_DB_NAME is not set in environment variables.")

# Создаём асинхронный клиент MongoDB
client = AsyncIOMotorClient(MONGO_URI)

# Получаем нужную базу
db = client[MONGO_DB_NAME]