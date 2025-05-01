from fastapi import APIRouter, Depends, HTTPException, Response
from app.db.database import get_database
from app.schemas.user_schemas import UserLogin, UserOut
from app.core.security import verify_password, create_access_token, create_refresh_token
from app.core.response import success
from bson import ObjectId
from datetime import datetime, timedelta
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/login", response_model=dict)
async def login(data: UserLogin, response: Response, db=Depends(get_database)):
    try:
        # Получаем пользователя по email и паролю
        user = await db.users.find_one({"email": data.email})
        if not user:
            raise HTTPException(
                status_code=401,
                detail={"message": "Неверный email или пароль"}
            )

        # Проверяем, заблокирован ли пользователь
        if user.get("is_banned", False):
            ban_info = user.get("ban_info", {})
            
            # Формируем сообщение о блокировке
            if ban_info.get("ban_type") == "permanent":
                error_message = "Ваш аккаунт заблокирован навсегда. Причина: " + ban_info.get("reason", "Нарушение правил")
                raise HTTPException(status_code=403, detail={"message": error_message, "ban_type": "permanent"})
            else:
                ban_until = ban_info.get("ban_until")
                if ban_until:
                    now = datetime.utcnow()
                    if ban_until > now:
                        # Вычисляем оставшееся время
                        time_left = ban_until - now
                        days = time_left.days
                        hours, remainder = divmod(time_left.seconds, 3600)
                        minutes, _ = divmod(remainder, 60)
                        
                        time_str = ""
                        if days > 0:
                            time_str += f"{days} дн. "
                        if hours > 0:
                            time_str += f"{hours} ч. "
                        if minutes > 0:
                            time_str += f"{minutes} мин."
                        
                        error_message = f"Ваш аккаунт временно заблокирован. Осталось: {time_str}. Причина: {ban_info.get('reason', 'Нарушение правил')}"
                        raise HTTPException(
                            status_code=403, 
                            detail={"message": error_message, "ban_type": "temporary", "time_left": time_str}
                        )
                    else:
                        # Срок бана истек, разблокируем пользователя
                        await db.users.update_one(
                            {"_id": user["_id"]},
                            {
                                "$set": {"is_banned": False},
                                "$unset": {"ban_info": ""}
                            }
                        )
                        
                        # Деактивируем запись о блокировке в коллекции user_bans
                        if "ban_id" in ban_info:
                            await db.user_bans.update_one(
                                {"_id": ObjectId(ban_info["ban_id"]), "is_active": True},
                                {
                                    "$set": {
                                        "is_active": False,
                                        "auto_unbanned_at": now
                                    }
                                }
                            )

        # Проверяем пароль
        if not verify_password(data.password, user.get("password", "")):
            raise HTTPException(
                status_code=401,
                detail={"message": "Неверный email или пароль"}
            )

        # Создаем токены
        user_id = str(user["_id"])
        access_token = create_access_token(data={"sub": user_id})
        refresh_token = create_refresh_token(data={"sub": user_id})
        
        # Обновляем последний вход
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        # Возвращаем токены и данные пользователя
        return success(data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": user.get("email"),
                "full_name": user.get("full_name"),
                "role": user.get("role", "user")
            }
        })
        
    except HTTPException as e:
        # Пробрасываем ошибки HTTP дальше
        raise e
    except Exception as e:
        logger.error(f"[LOGIN ERROR] {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Внутренняя ошибка сервера"}
        ) 