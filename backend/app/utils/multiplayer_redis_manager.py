import redis.asyncio as redis
from redis.asyncio import Redis
from typing import Optional

from app.core.config import settings
from app.logging import get_logger, LogSection, LogSubsection

logger = get_logger(__name__)

class MultiplayerRedisManager:
    """
    Класс для управления сессиями мультиплеера в Redis.
    Использует отдельную БД Redis для изоляции данных.
    """
    _redis: Optional[Redis] = None

    @classmethod
    async def _get_redis_connection(cls) -> Redis:
        """Получить асинхронное соединение с Redis."""
        if cls._redis is None or not await cls._redis.ping():
            try:
                redis_instance = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD,
                    db=settings.REDIS_MULTIPLAYER_DB,
                    decode_responses=True,
                    socket_timeout=2,
                    socket_connect_timeout=2,
                )
                await redis_instance.ping()
                cls._redis = redis_instance
                logger.info(
                    section=LogSection.REDIS,
                    subsection=LogSubsection.REDIS.CONNECTION,
                    message=f"Multiplayer Redis connection established to DB {settings.REDIS_MULTIPLAYER_DB}"
                )
            except Exception as e:
                logger.critical(
                    section=LogSection.REDIS,
                    subsection=LogSubsection.REDIS.ERROR,
                    message=f"Failed to connect to Multiplayer Redis DB {settings.REDIS_MULTIPLAYER_DB}: {e}"
                )
                raise
        return cls._redis

    @classmethod
    async def store_session(cls, lobby_id: str, user_id: str, token: str, expire_seconds: int):
        """
        Сохранить сессию пользователя в Redis.
        Ключ: session:<lobby_id>:<user_id>
        """
        try:
            r = await cls._get_redis_connection()
            key = f"session:{lobby_id}:{user_id}"
            await r.set(key, token, ex=expire_seconds)
            logger.info(
                section=LogSection.MULTIPLAYER,
                subsection=LogSubsection.MULTIPLAYER.WEBSOCKET,
                message=f"Stored session for user {user_id} in lobby {lobby_id}."
            )
        except Exception as e:
            logger.error(
                section=LogSection.MULTIPLAYER,
                subsection=LogSubsection.MULTIPLAYER.ERROR,
                message=f"Failed to store session for user {user_id} in lobby {lobby_id}: {e}"
            )
    
    @classmethod
    async def get_session(cls, lobby_id: str, user_id: str) -> Optional[str]:
        """Получить сессию пользователя из Redis."""
        try:
            r = await cls._get_redis_connection()
            key = f"session:{lobby_id}:{user_id}"
            return await r.get(key)
        except Exception as e:
            logger.error(
                section=LogSection.MULTIPLAYER,
                subsection=LogSubsection.MULTIPLAYER.ERROR,
                message=f"Failed to get session for user {user_id} in lobby {lobby_id}: {e}"
            )
            return None

    @classmethod
    async def delete_session(cls, lobby_id: str, user_id: str):
        """Удалить сессию пользователя из Redis."""
        try:
            r = await cls._get_redis_connection()
            key = f"session:{lobby_id}:{user_id}"
            await r.delete(key)
        except Exception as e:
            logger.error(
                section=LogSection.MULTIPLAYER,
                subsection=LogSubsection.MULTIPLAYER.ERROR,
                message=f"Failed to delete session for user {user_id} in lobby {lobby_id}: {e}"
            )

    @classmethod
    async def close_connection(cls):
        """Закрыть соединение с Redis."""
        if cls._redis:
            await cls._redis.close()
            cls._redis = None
            logger.info(
                section=LogSection.REDIS,
                subsection=LogSubsection.REDIS.DISCONNECTION,
                message=f"Multiplayer Redis connection closed for DB {settings.REDIS_MULTIPLAYER_DB}."
            )

# Рекомендуется добавить в shutdown hook в main.py:
# from app.multiplayer.redis_manager import MultiplayerRedisManager
# @app.on_event("shutdown")
# async def shutdown_event():
#     await MultiplayerRedisManager.close_connection() 