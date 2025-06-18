from fastapi import APIRouter, Depends, Request, HTTPException
from datetime import datetime, timedelta
import jwt
from app.core.config import settings
from app.core.security import get_current_actor  # ← заменили импорт
from app.db.database import db
from app.core.response import success
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


async def create_ws_token(user_id: str, hours: float = 1.0):
    try:
        expire = datetime.utcnow() + timedelta(hours=hours)
        to_encode = {
            "sub": user_id,
            "exp": expire,
            "type": "ws_token"
        }

        token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        # Очищаем старые токены пользователя
        await db.ws_tokens.delete_many({
            "user_id": user_id,
            "$or": [
                {"expires_at": {"$lt": datetime.utcnow()}},
                {"used": True}
            ]
        })

        await db.ws_tokens.insert_one({
            "token": token,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "expires_at": expire,
            "used": False
        })

        return token
    except Exception as e:
        logger.error(f"Ошибка при создании WS токена: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при генерации токена")


@router.get("/ws-token", summary="Получить временный токен для WebSocket")
async def get_ws_token(request: Request, current_user: dict = Depends(get_current_actor)):  # ← заменили Depends
    if not current_user:
        logger.error("Попытка получить WS токен без аутентификации")
        raise HTTPException(status_code=401, detail="Требуется аутентификация")

    try:
        user_id = str(current_user.get("id"))
        if not user_id:
            logger.error("Не удалось получить ID пользователя")
            raise HTTPException(status_code=401, detail="Неверный формат ID пользователя")

        logger.info(f"Генерация WS токена для пользователя {user_id}")
        token = await create_ws_token(user_id)

        return success(data={"token": token})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении WS токена: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при получении токена")
