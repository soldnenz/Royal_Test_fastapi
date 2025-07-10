import logging
import random
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status, Request
from pydantic import EmailStr

from app.db.database import db
from app.schemas.auth_schemas import PasswordResetRequest, PasswordResetConfirm
from app.core.security import hash_password
from app.core.response import success
from app.logging import get_logger, LogSection, LogSubsection
from app.utils.twofa_client import twofa_client
from app.rate_limit import rate_limit_ip

router = APIRouter()
logger = logging.getLogger(__name__)

RESET_CODE_LENGTH = 6        # длина кода
RESET_CODE_EXPIRE_MIN = 30   # через сколько минут код протухает


@router.post("/request", response_model=dict)
@rate_limit_ip("password_reset_request", max_requests=3, window_seconds=900)
async def request_password_reset(data: PasswordResetRequest, request: Request):
    """
    Эндпоинт для запроса сброса пароля по e-mail.
    Генерируем одноразовый код и отправляем (пока только логируем).
    Сохраняем запись в отдельной коллекции password_resets.
    """
    email = data.email.strip().lower()

    user = await db.users.find_one({"email": email})
    if not user:
        logger.warning(f"[request_password_reset] Пользователь не найден: {email}")
        raise HTTPException(
            status_code=403,
            detail={"message": "Пользователь с таким email не найден"}
        )

    code = "".join(random.choices(string.digits, k=RESET_CODE_LENGTH))
    expires_at = datetime.utcnow() + timedelta(minutes=RESET_CODE_EXPIRE_MIN)

    reset_doc = {
        "user_id": user["_id"],
        "email": email,
        "code": code,
        "expires_at": expires_at,
        "used": False,
        "created_at": datetime.utcnow()
    }
    await db.password_resets.insert_one(reset_doc)

    logger.info(f"[request_password_reset] КОД ДЛЯ {email}: {code}")

    return success(message=f"Код для сброса пароля успешно отправлен на {email}")


@router.post("/confirm", response_model=dict)
@rate_limit_ip("password_reset_confirm", max_requests=5, window_seconds=600)
async def confirm_password_reset(data: PasswordResetConfirm, request: Request):
    """
    Эндпоинт подтверждения сброса пароля.
    Принимает email, code, new_password.
    Проверяет код в password_resets, если всё ок - обновляет пароль в users.
    """
    email = data.email.strip().lower()
    code = data.code.strip()
    new_password = data.new_password

    reset_doc = await db.password_resets.find_one({
        "email": email,
        "code": code,
        "used": False,
        "expires_at": {"$gte": datetime.utcnow()}
    })

    if not reset_doc:
        logger.warning("[confirm_password_reset] Некорректный или просроченный код.")
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный или просроченный код"}
        )

    user = await db.users.find_one({"_id": reset_doc["user_id"]})
    if not user:
        logger.error("[confirm_password_reset] Нет пользователя под user_id из reset_doc")
        raise HTTPException(
            status_code=404,
            detail={"message": "Пользователь не найден"}
        )

    hashed_pass = hash_password(new_password)

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"hashed_password": hashed_pass}}
    )

    await db.password_resets.update_one(
        {"_id": reset_doc["_id"]},
        {"$set": {"used": True}}
    )

    logger.info(f"[confirm_password_reset] Пароль обновлен для user_id={user['_id']} (email: {email})")

    return success(message="Пароль успешно изменён")
