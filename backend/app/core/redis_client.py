import redis.asyncio as redis
from typing import Optional
from app.core.config import settings

class MultiplayerRedisClient:
    """
    Асинхронный клиент Redis для многопользовательских функций (WS-токены и т.д.).
    Подключается к выделенной БД.
    """
    _redis: Optional[redis.Redis] = None

    @classmethod
    async def connect(cls):
        """
        Устанавливает и проверяет соединение с Redis.
        """
        if cls._redis is None:
            try:
                cls._redis = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD,
                    db=settings.REDIS_MULTIPLAYER_DB,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    health_check_interval=30
                )
                await cls._redis.ping()
                print(f"Successfully connected to Multiplayer Redis DB: {settings.REDIS_MULTIPLAYER_DB}")
            except redis.exceptions.ConnectionError as e:
                print(f"Error connecting to Multiplayer Redis: {e}")
                cls._redis = None
                raise

    @classmethod
    async def disconnect(cls):
        """Закрывает соединение с Redis."""
        if cls._redis:
            await cls._redis.close()
            cls._redis = None
            print("Multiplayer Redis connection closed.")
    
    @classmethod
    async def get_connection(cls) -> redis.Redis:
        """
        Возвращает существующее соединение с Redis.
        Если соединения нет, создает его.
        """
        if cls._redis is None:
            await cls.connect()
        return cls._redis

# Глобальный экземпляр клиента
multiplayer_redis_client = MultiplayerRedisClient()

async def get_multiplayer_redis_connection() -> redis.Redis:
    """Dependency для получения соединения с Redis."""
    return await multiplayer_redis_client.get_connection() 