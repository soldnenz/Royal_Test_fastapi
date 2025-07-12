import secrets
import json
import hashlib
from fastapi import HTTPException
from app.core.redis_client import get_multiplayer_redis_connection
from app.logging import get_logger, LogSection, LogSubsection

logger = get_logger(__name__)

def hash_token(token: str) -> str:
    """Хэширует токен для безопасного хранения."""
    return hashlib.sha256(token.encode()).hexdigest()

async def create_ws_token(user: dict, lobby_id: str) -> str:
    """
    Создает одноразовый токен для WebSocket, сохраняет его хэш в Redis.
    Возвращает оригинальный (нехэшированный) токен.
    """
    if not lobby_id:
        raise ValueError("lobby_id является обязательным для создания WS токена")

    user_id = str(user.get("id"))
    try:
        redis = await get_multiplayer_redis_connection()
        original_token = secrets.token_urlsafe(32)
        hashed_token = hash_token(original_token)

        is_guest = user.get("is_guest", False)
        
        user_info = {
            "user_id": user_id,
            "nickname": user.get("full_name", f"Гость {user_id[-8:]}"),
            "role": user.get("role", "user"),
            "is_guest": is_guest,
            "lobby_id": lobby_id
        }

        await redis.set(f"ws_token:{hashed_token}", json.dumps(user_info), ex=14400) # 4 часа
        await redis.set(f"user_ws_token:{user_id}", hashed_token, ex=14400)

        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.TOKEN_CREATE,
            message=f"Создан WS токен для пользователя {user_id} в лобби {lobby_id}"
        )
        return original_token
    except Exception as e:
        logger.error(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.ERROR,
            message=f"Ошибка создания WS токена для пользователя {user_id} в лобби {lobby_id}. Ошибка: {e}"
        )
        raise HTTPException(status_code=500, detail="Не удалось создать WebSocket токен")

async def clear_ws_token(user_id: str):
    """
    Находит и удаляет WS токен для указанного пользователя.
    """
    try:
        redis = await get_multiplayer_redis_connection()
        hashed_token = await redis.get(f"user_ws_token:{user_id}")

        if hashed_token:
            if isinstance(hashed_token, bytes):
                decoded_hashed_token = hashed_token.decode('utf-8')
            else:
                decoded_hashed_token = hashed_token
            await redis.delete(f"ws_token:{decoded_hashed_token}")
            await redis.delete(f"user_ws_token:{user_id}")
            logger.info(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.TOKEN_REVOKE,
                message=f"WS токен для пользователя {user_id} был успешно отозван."
            )
        else:
            logger.warning(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.TOKEN_REVOKE,
                message=f"Попытка отозвать несуществующий WS токен для пользователя {user_id}."
            )
    except Exception as e:
        logger.error(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.ERROR,
            message=f"Ошибка отзыва WS токена для пользователя {user_id}. Ошибка: {e}"
        ) 