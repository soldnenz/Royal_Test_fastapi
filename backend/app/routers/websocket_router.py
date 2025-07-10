from fastapi import APIRouter, Depends, HTTPException, status, Request
from datetime import datetime, timedelta
import jwt
from app.core.config import settings
from app.core.security import get_current_actor  # ← заменили импорт
from app.db.database import db
from app.core.response import success
from app.logging import get_logger, LogSection, LogSubsection
from app.rate_limit import rate_limit_ip

logger = get_logger(__name__)
router = APIRouter()


async def create_ws_token(user_id: str, hours: float = 0.5):
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

        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.TOKEN_CREATE,
            message=f"Создан WebSocket-токен для пользователя {user_id} (действителен до {expire.isoformat()})"
        )
        return token
    except Exception as e:
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Ошибка при создании WebSocket-токена для пользователя {user_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при генерации токена")


@router.get("/ws-token", summary="Получить временный токен для WebSocket")
@rate_limit_ip("websocket_token_get", max_requests=60, window_seconds=60)
async def get_ws_token(request: Request, current_user: dict = Depends(get_current_actor)):
    if not current_user:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message="Попытка получить WebSocket-токен без аутентификации"
        )
        raise HTTPException(status_code=401, detail="Требуется аутентификация")

    try:
        user_id = str(current_user.get("id"))
        if not user_id:
            logger.error(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message="Не удалось получить ID пользователя для WebSocket-токена"
            )
            raise HTTPException(status_code=401, detail="Неверный формат ID пользователя")

        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.TOKEN_CREATE,
            message=f"Запрос на генерацию WebSocket-токена пользователем {user_id}"
        )
        token = await create_ws_token(user_id)

        return success(data={"token": token})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Ошибка при получении WebSocket-токена для пользователя {current_user.get('id')}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при получении токена")
