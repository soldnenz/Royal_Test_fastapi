import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from config import settings

# Load environment variables
load_dotenv()

# Get database configuration
MONGO_URI = settings.mongo_uri
MONGO_DB_NAME = settings.mongo_db_name

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set in .env")
if not MONGO_DB_NAME:
    raise RuntimeError("MONGO_DB_NAME is not set in .env")

# Create client with replica set support
client = AsyncIOMotorClient(MONGO_URI)

# Get database
db = client[MONGO_DB_NAME]

# FastAPI dependency
async def get_database():
    return db 