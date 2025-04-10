from fastapi import Depends, HTTPException, Request
from app.core.security import oauth2_scheme
from app.db.database import db
from bson import ObjectId
from datetime import datetime
import jwt
from app.core.config import settings
import os
from app.core.response import error


SUPER_ADMINS = [int(uid) for uid in os.getenv("SUPER_ADMIN_IDS", "").split(",") if uid.strip()]

def is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS


async def get_current_admin_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=404,
            detail={"message": "Не передан токен", "hint": "Токен отсутствует в cookie"}
        )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id or not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=404,
                detail={"message": "Не удалось декодировать данные токена", "hint": "Неверные данные в токене"}
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Токен истёк", "hint": "Пожалуйста, повторите вход"}
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=404,
            detail={"message": "Ошибка токена", "hint": "Токен недействителен или повреждён"}
        )

    admin = await db.admins.find_one({
        "_id": ObjectId(user_id),
        "active_session.token": token
    })

    if not admin:
        raise HTTPException(
            status_code=404,
            detail={"message": "Пользователь не найден", "hint": "Сессия устарела или удалена"}
        )

    # Обновляем активность
    await db.admins.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "active_session.last_activity": datetime.utcnow(),
            "active_session.ip": request.client.host,
            "active_session.user_agent": request.headers.get("User-Agent", "unknown")
        }}
    )

    return {
        "_id": admin["_id"],
        "full_name": admin.get("full_name"),
        "role": admin.get("role"),
        "iin": admin.get("iin")
    }
