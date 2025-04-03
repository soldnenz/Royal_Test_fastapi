from fastapi import Depends, HTTPException, Request
from app.core.security import oauth2_scheme
from app.db.database import db
from bson import ObjectId
from datetime import datetime
import jwt
from app.core.config import settings
import os

SUPER_ADMINS = [int(uid) for uid in os.getenv("SUPER_ADMIN_IDS", "").split(",") if uid.strip()]

def is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS

async def get_current_admin_user(request: Request, token: str = Depends(oauth2_scheme)):
    """Проверка токена только для админов. Токены обычных пользователей не трогаются."""
    not_found_exception = HTTPException(status_code=404, detail="Not found")

    # 1. Расшифровка токена
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id or not ObjectId.is_valid(user_id):
            print(1)
            raise not_found_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Токен истёк")
    except jwt.PyJWTError:
        print(2)
        raise not_found_exception

    # 2. Поиск админа по ID и проверка токена в active_session
    admin = await db.admins.find_one({
        "_id": ObjectId(user_id),
        "active_session.token": token
    })

    if not admin:
        print(3)
        raise not_found_exception

    # 3. Проверка, не истёк ли токен по last_activity или expires_at (если ты хранишь expires_at)
    # Если добавишь active_session.expires_at — можно сравнить с datetime.utcnow()

    # 4. Обновление информации об активности
    await db.admins.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "active_session.last_activity": datetime.utcnow(),
                "active_session.ip": request.client.host,
                "active_session.user_agent": request.headers.get("User-Agent", "unknown")
            }
        }
    )

    # 5. Возврат информации о текущем админ-пользователе
    return {
        "_id": admin["_id"],
        "full_name": admin.get("full_name"),
        "role": admin.get("role"),
        "iin": admin.get("iin")
    }
