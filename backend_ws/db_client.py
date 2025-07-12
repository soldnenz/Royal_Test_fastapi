import motor.motor_asyncio
from config import settings
from bson import ObjectId

class DBClient:
    """
    Асинхронный клиент MongoDB для WebSocket-сервиса.
    """
    def __init__(self, uri: str, db_name: str):
        try:
            self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
            self.db = self._client[db_name]
            print("INFO:     Successfully connected to MongoDB for ws_service.")
        except Exception as e:
            print(f"ERROR:    Error connecting to MongoDB for ws_service: {e}")
            raise
    
    def get_collection(self, collection_name: str):
        """Возвращает объект коллекции по имени."""
        return self.db[collection_name]
    
    async def close(self):
        """Закрывает соединение."""
        if self._client:
            self._client.close()
            print("INFO:     MongoDB connection for ws_service closed.")

# Инициализируем синглтон клиента
db_client = DBClient(settings.MONGO_URI, settings.MONGO_DB_NAME)


async def get_lobby_by_id(lobby_id: str) -> dict | None:
    """
    Получает информацию о лобби по его ID.
    """
    try:
        lobbies_collection = db_client.get_collection("lobbies")
        return await lobbies_collection.find_one({"_id": lobby_id})
    except Exception as e:
        print(f"ERROR:    Failed to fetch lobby {lobby_id}: {e}")
        return None


async def get_user_by_id(user_id: str) -> dict | None:
    """
    Получает информацию о пользователе по его ID.
    Не работает для гостей, так как они не хранятся в коллекции users.
    """
    if not user_id or user_id.startswith("guest_"):
        return None
    try:
        users_collection = db_client.get_collection("users")
        # Конвертируем строку в ObjectId для поиска
        user_obj_id = ObjectId(user_id)
        return await users_collection.find_one({"_id": user_obj_id})
    except Exception as e:
        print(f"ERROR:    Failed to fetch user {user_id}: {e}")
        return None 