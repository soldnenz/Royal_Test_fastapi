import time
import logging
from datetime import datetime, timedelta, timezone
import pytz
from bson import ObjectId
from fastapi import APIRouter, Request, HTTPException, status, Response, Depends
from fastapi.responses import JSONResponse
from app.schemas.user_schemas import UserCreate
from app.schemas.auth_schemas import AuthRequest, TokenResponse
from app.db.database import db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    store_token_in_db
)
from app.core.config import settings
from fastapi.security import HTTPBearer
from app.schemas.admin_schemas import AdminToken
from app.admin.telegram_2fa import send_2fa_request
from app.admin.utils import create_token, get_ip, get_user_agent
from app.admin.utils import decode_token
from app.admin.permissions import get_current_admin_user
import string
import secrets
from app.core.response import success

router = APIRouter()
logger = logging.getLogger("auth")
security = HTTPBearer()
# -------------------------
# RATE LIMIT (упрощённо)
# -------------------------
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300
login_attempts = {}

def check_rate_limit(ip: str) -> bool:
    now = time.time()
    if ip not in login_attempts:
        login_attempts[ip] = []
    # Оставляем только недавние попытки (в пределах WINDOW_SECONDS)
    login_attempts[ip] = [t for t in login_attempts[ip] if (now - t) <= WINDOW_SECONDS]
    return len(login_attempts[ip]) < MAX_ATTEMPTS

def register_attempt(ip: str):
    now = time.time()
    if ip not in login_attempts:
        login_attempts[ip] = []
    login_attempts[ip].append(now)


def get_ip(request: Request) -> str:
    return request.client.host or "unknown"

def get_user_agent(request: Request) -> str:
    return request.headers.get("User-Agent", "unknown")

def sanitize_input(value: str) -> str:
    # Определяем запрещённые символы для предотвращения NoSQL инъекций
    forbidden_characters = ['$','{','}','<','>','|','&','$','*','?','^']
    if any(c in value for c in forbidden_characters):
        raise ValueError("Запрещённые символы во входе")
    return value.strip()

# -------------------------
# LOGIN
# -------------------------
@router.post("/login")
async def unified_login(data: AuthRequest, request: Request):
    ip = get_ip(request)
    ua = get_user_agent(request)
    now = datetime.utcnow()

    try:
        ident = sanitize_input(data.username)
    except ValueError:
        logger.warning(f"[LOGIN][{ip}] Некорректный ввод логина")
        raise HTTPException(
            status_code=400,
            detail={"message": "Ввод содержит запрещённые символы"}
        )

    if not check_rate_limit(ip):
        logger.warning(f"[LOGIN][{ip}] Превышен лимит попыток входа")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": "Превышен лимит попыток входа"}
        )

    admin = await db.admins.find_one({"$or": [{"email": ident}, {"iin": ident}]})
    if admin:
        if not verify_password(data.password, admin["hashed_password"]):
            logger.info(f"[LOGIN][{ip}] Неуспешный вход: admin={admin['email'] or admin['iin']}")
            await db.login_logs.insert_one({"ident": ident, "timestamp": now, "success": False})
            raise HTTPException(
                status_code=401,
                detail={"message": "Неправильный IIN, Email или пароль"}
            )

        # 2FA если другой IP или UA
        if admin.get("active_session") and (
                admin["active_session"].get("ip") != ip or
                admin["active_session"].get("user_agent") != ua):
            logger.info(f"[LOGIN][{ip}] Требуется 2FA: admin={admin['email'] or admin['iin']}")
            await db.admins.update_one({"_id": admin["_id"]}, {"$set": {"is_verified": False}})
            await send_2fa_request(admin, ip, ua)
            raise HTTPException(
                status_code=403,
                detail={"message": "Подтвердите вход в приложение 2FA"}
            )

        token = create_token(str(admin["_id"]), admin["role"])

        await db.admins.update_one({"_id": admin["_id"]}, {"$set": {
            "active_session": {"ip": ip, "user_agent": ua, "token": token},
            "last_login": {"timestamp": now, "ip": ip, "user_agent": ua},
            "is_verified": True
        }})

        await db.login_logs.insert_one({"ident": ident, "timestamp": now, "success": True})

        logger.info(f"[LOGIN][{ip}] Успешный вход: admin={admin['email'] or admin['iin']}, role={admin['role']}")

        response = success(data={"access_token": token, "token_type": "bearer"})

        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=60 * 60 * 24,  # 1 день
            expires=(datetime.now(timezone.utc) + timedelta(days=1)),
            path="/"
        )
        return response

    # ========== USER BLOCK ==========

    user = await db.users.find_one({
        "$or": [
            {"iin": ident},
            {"email": ident.lower()}
        ]
    })

    if not user:
        logger.info(f"[LOGIN][{ip}] Неуспешный вход: user not found — {ident}")
        register_attempt(ip)
        raise HTTPException(
            status_code=401,
            detail={"message": "Неправильный IIN, Email или пароль"}
        )

    if not verify_password(data.password, user["hashed_password"]):
        logger.info(f"[LOGIN][{ip}] Неверный пароль: user={user['email'] or user['iin']}")
        register_attempt(ip)
        raise HTTPException(
            status_code=401,
            detail={"message": "Неправильный IIN, Email или пароль"}
        )

    register_attempt(ip)

    token_data = {
        "sub": str(user["_id"]),
        "role": user.get("role", "user")
    }
    access_token, expires_at = create_access_token(token_data)

    await store_token_in_db(access_token, user["_id"], expires_at, ip, ua)

    logger.info(f"[LOGIN][{ip}] Успешный вход: user={user['email'] or user['iin']}")

    response = success(data={"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="None",
        max_age=60 * 60 * 24 * 31,  # 31 день
        expires=datetime.now(timezone.utc) + timedelta(days=31),
        path="/"
    )
    return response



# -------------------------
# REGISTER
# -------------------------
@router.post("/register", response_model=TokenResponse)
async def register_user(user_data: UserCreate, request: Request):
    ip = request.client.host

    if not check_rate_limit(ip):
        logger.warning(f"[REGISTER][{ip}] Превышен лимит попыток")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": "Превышен лимит попыток входа"}
        )

    register_attempt(ip)

    try:
        user_data.iin = sanitize_input(user_data.iin)
        user_data.email = sanitize_input(user_data.email)
        user_data.phone = sanitize_input(user_data.phone)
        user_data.full_name = sanitize_input(user_data.full_name)
        if user_data.referred_by:
            user_data.referred_by = sanitize_input(user_data.referred_by)
    except ValueError as e:
        logger.warning(f"[REGISTRATION][{ip}] Ввод содержит запрещённые символы: {e.args[0]}")
        raise HTTPException(
            status_code=400,
            detail={"message": f"Ввод содержит запрещённые символы"}
        )
    if user_data.password != user_data.confirm_password:
        logger.info(f"[REGISTER][{ip}] Пароли не совпадают — {user_data.email}")
        raise HTTPException(
            status_code=400,
            detail={"message": "Пароли не совпадают"}
        )

    existing_user = await db.users.find_one({
        "$or": [
            {"iin": user_data.iin},
            {"email": user_data.email.lower()},
            {"phone": user_data.phone}
        ]
    })
    if existing_user:
        logger.info(f"[REGISTER][{ip}] Уже существует: {user_data.email or user_data.iin}")
        raise HTTPException(
            status_code=400,
            detail={"message": "Пользователь с таким ИИН, Email или телефоном уже существует"}
        )

    # ✅ Проверяем, существует ли пригласивший
    referred_by = None
    if user_data.referred_by:
        ref_owner = await db.referrals.find_one({"code": user_data.referred_by})
        if not ref_owner:
            logger.warning(f"[REGISTER][{ip}] Указанный реферальный код не найден — {user_data.referred_by}")
            raise HTTPException(
                status_code=400,
                detail={"message": "Указанный реферальный код не найден"}
            )
        referred_by = user_data.referred_by  # Привязываем к пользователю, который пригласил
        logger.info(f"[REGISTER][{ip}] Пользователь привязан к рефералке: {referred_by}")

    hashed_password = hash_password(user_data.password)

    new_user = {
        "full_name": user_data.full_name,
        "iin": user_data.iin,
        "phone": user_data.phone,
        "email": user_data.email.lower(),
        "hashed_password": hashed_password,
        "role": "user",
        "created_at": datetime.utcnow(),
        "referred_by": referred_by,
        "money": user_data.money,  # добавлено поле money (включая значение по умолчанию 0.0)
        "referred_use": user_data.referred_use  # добавлено поле referred_use
    }

    result = await db.users.insert_one(new_user)
    user_id = result.inserted_id

    logger.info(f"[REGISTER][{ip}] Успешно: {user_data.email} (ID: {user_id})")

    token_data = {
        "sub": str(user_id),
        "role": "user"
    }
    access_token, expires_at = create_access_token(token_data)

    user_agent = request.headers.get("User-Agent", "unknown")
    await store_token_in_db(access_token, user_id, expires_at, ip, user_agent)

    response = success(data={"access_token": access_token, "token_type": "bearer"})

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="None",
        max_age=60 * 60 * 24 * 31,
        expires=datetime.now(timezone.utc) + timedelta(days=31),
        path="/"
    )
    return response


# -------------------------
# LOGOUT (Отзыв токена)
# -------------------------
@router.post("/logout")
async def logout_user(request: Request):
    # Получаем токен из cookies
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail={"message": "Не передан токен (cookie)", "hint": "Добавьте токен в cookie"}
        )

    # Декодируем токен
    try:
        payload = decode_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=403,
            detail={"message": "Ошибка декодирования токена", "hint": str(e)}
        )

    user_id = payload.get("sub")
    role = payload.get("role")

    # Проверка роли
    if role not in ["user", "admin", "moderator", "manager", "super_admin"]:
        logger.warning(f"[LOGOUT][{request.client.host}] Недопустимая роль: {role}")
        raise HTTPException(
            status_code=403,
            detail={"message": "Недопустимая роль"}
        )

    # Подготовка ответа
    response = success(message="Вы успешно вышли из системы")
    response.delete_cookie("access_token")  # Удаляем куку с токеном

    # Логика для пользователя
    if role == "user":
        token_doc = await db.tokens.find_one({"token": token})
        if not token_doc:
            logger.info(f"[LOGOUT][{request.client.host}] Пользователь не найден по токену. user_id={user_id}")
            raise HTTPException(
                status_code=404,
                detail={"message": "Пользователь не найден по токену"}
            )

        await db.tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {"revoked": True}}
        )

        logger.info(f"[LOGOUT][{request.client.host}] Успешный выход: user_id={user_id}")
        return response

    # Логика для администраторов
    admin = await db.admins.find_one({"_id": ObjectId(user_id)})
    if not admin:
        logger.warning(f"[LOGOUT][{request.client.host}] Админ не найден. user_id={user_id}")
        raise HTTPException(
            status_code=404,
            detail={"message": "Админ не найден"}
        )

    await db.admins.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"active_session": None}}
    )

    logger.info(f"[LOGOUT][{request.client.host}] Успешный выход: admin_id={user_id}, role={role}")
    return response


# --------------------------------------------------------------------------- #
# /validate-admin  (для Nginx auth_request)
# --------------------------------------------------------------------------- #
@router.get("/validate-admin", include_in_schema=False)
async def validate_admin(admin = Depends(get_current_admin_user)):
    """
    204 → JWT валиден и роль = admin|moderator.
    Используется Nginx‑ом в auth_request.
    """
    if admin["role"] not in ["admin", "moderator", "super_admin"]:
        logger.warning(f"[VALIDATE-ADMIN] Недостаточно прав: user_id={admin['_id']}, role={admin['role']}")
        return Response(status_code=404)
    
    logger.info(f"[VALIDATE-ADMIN] Успешная валидация: user_id={admin['_id']}, role={admin['role']}")
    return Response(status_code=204)