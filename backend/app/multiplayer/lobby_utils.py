from datetime import datetime
from typing import Dict, Optional
from app.db.database import db
from app.logging import get_logger, LogSection, LogSubsection
from bson import ObjectId
from bson.errors import InvalidId


logger = get_logger(__name__)

# Maximum time a lobby can be active (4 hours in seconds)
MAX_LOBBY_LIFETIME = 4 * 60 * 60

# Exam mode timer (40 minutes in seconds)
EXAM_TIMER_DURATION = 40 * 60

async def get_lobby_from_db(lobby_id: str) -> Optional[dict]:
    """Получить лобби напрямую из MongoDB."""
    return await db.lobbies.find_one({"_id": lobby_id})

async def get_user_subscription_from_db(user_id: str) -> Optional[dict]:
    """Получить активную подписку пользователя напрямую из MongoDB."""
    if not user_id or user_id.startswith("guest_"):
        return None
    try:
        # Проверяем, является ли user_id валидным ObjectId
        if not ObjectId.is_valid(user_id):
            logger.warning(
                section=LogSection.DATABASE,
                subsection=LogSubsection.DATABASE.VALIDATION,
                message=f"Попытка запроса подписки с невалидным user_id: {user_id}"
            )
            return None
        
        subscription = await db.subscriptions.find_one({
            "user_id": ObjectId(user_id),
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        return subscription
    except InvalidId:
        logger.warning(
            section=LogSection.DATABASE,
            subsection=LogSubsection.DATABASE.VALIDATION,
            message=f"Передан невалидный ObjectId в get_user_subscription_from_db: {user_id}"
        )
        return None


def get_user_id(current_user: dict) -> str:
    """Извлекает ID пользователя из объекта current_user."""
    if not current_user:
        return "anonymous"
    user_id = current_user.get("id")
    # Для пользователей BSON ObjectId, для гостей - строка
    return str(user_id) if user_id else "anonymous" 