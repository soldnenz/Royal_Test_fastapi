import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# 1) читаем .env
load_dotenv()

# 2) вытягиваем из окружения
MONGO_URI     = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set in .env")
if not MONGO_DB_NAME:
    raise RuntimeError("MONGO_DB_NAME is not set in .env")

# 3) создаём клиент с поддержкой replica set
client = AsyncIOMotorClient(MONGO_URI)

# 4) получаем базу
db = client[MONGO_DB_NAME]

# 5) dependency для FastAPI
async def get_database():
    return db

# 6) Импорт функции создания индексов
from .indexes import create_database_indexes
