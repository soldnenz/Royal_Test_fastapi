import redis.asyncio as redis
from typing import Optional
from config import settings

class RedisClient:
    """
    Асинхронный клиент Redis для WebSocket сервера.
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
                print(f"Successfully connected to Redis DB: {settings.REDIS_MULTIPLAYER_DB}")
            except redis.exceptions.ConnectionError as e:
                print(f"Error connecting to Redis: {e}")
                cls._redis = None
                raise

    @classmethod
    async def disconnect(cls):
        """Закрывает соединение с Redis."""
        if cls._redis:
            await cls._redis.close()
            cls._redis = None
            print("Redis connection closed.")
    
    @classmethod
    async def get_connection(cls) -> redis.Redis:
        """
        Возвращает существующее соединение с Redis.
        """
        if cls._redis is None:
            await cls.connect()
        return cls._redis

redis_client = RedisClient() 