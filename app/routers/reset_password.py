# app/routers/reset_password.py

import logging
import random
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import EmailStr

from app.db.database import db
from app.schemas.auth_schemas import PasswordResetRequest, PasswordResetConfirm
from app.core.security import hash_password

router = APIRouter()
logger = logging.getLogger(__name__)

RESET_CODE_LENGTH = 6        # длина кода
RESET_CODE_EXPIRE_MIN = 30   # через сколько минут код протухает


@router.post("/request", response_model=dict)
async def request_password_reset(data: PasswordResetRequest):
    """
    Эндпоинт для запроса сброса пароля по e-mail.
    Генерируем одноразовый код и отправляем (пока только логируем).
    Сохраняем запись в отдельной коллекции password_resets.
    """
    email = data.email.strip().lower()

    # Ищем пользователя в коллекции users
    user = await db.users.find_one({"email": email})
    if not user:
        logger.warning(f"[request_password_reset] Пользователь не найден: {email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with provided email not found"
        )

    # Генерируем случайный код
    code = "".join(random.choices(string.digits, k=RESET_CODE_LENGTH))

    # Ставим срок годности (UTC now + X минут)
    expires_at = datetime.utcnow() + timedelta(minutes=RESET_CODE_EXPIRE_MIN)

    # Сохраняем в коллекции password_resets
    reset_doc = {
        "user_id": user["_id"],
        "email": email,
        "code": code,
        "expires_at": expires_at,
        "used": False,
        "created_at": datetime.utcnow()
    }
    await db.password_resets.insert_one(reset_doc)

    # Логируем или отправляем письмо
    # В реальном проекте - тут вы зовёте почтовый сервис.
    logger.info(f"[request_password_reset] КОД ДЛЯ {email}: {code}")

    return {"message": f"Reset code sent to {email}. Check logs or email."}


@router.post("/confirm", response_model=dict)
async def confirm_password_reset(data: PasswordResetConfirm):
    """
    Эндпоинт подтверждения сброса пароля.
    Принимает email, code, new_password.
    Проверяет код в password_resets, если всё ок - обновляет пароль в users.
    """
    email = data.email.strip().lower()
    code = data.code.strip()
    new_password = data.new_password

    # Ищем активную (не использованную, не просроченную) запись в password_resets
    reset_doc = await db.password_resets.find_one({
        "email": email,
        "code": code,
        "used": False,
        "expires_at": {"$gte": datetime.utcnow()}
    })

    if not reset_doc:
        logger.warning("[confirm_password_reset] Некорректный или просроченный код.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code"
        )

    # Ищем пользователя
    user = await db.users.find_one({"_id": reset_doc["user_id"]})
    if not user:
        logger.error("[confirm_password_reset] Нет пользователя под user_id из reset_doc")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Всё ок, хешируем новый пароль
    hashed_pass = hash_password(new_password)

    # Обновляем пароль у пользователя
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"hashed_password": hashed_pass}}
    )

    # Помечаем reset_doc как использованный
    await db.password_resets.update_one(
        {"_id": reset_doc["_id"]},
        {"$set": {"used": True}}
    )

    logger.info(f"[confirm_password_reset] Пароль обновлен для user_id={user['_id']} (email: {email})")

    return {"message": "Password reset successful. You can now log in with new password."}
