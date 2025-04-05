import time
import logging
from datetime import datetime
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

router = APIRouter()
logger = logging.getLogger(__name__)
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
    if any(c in value for c in ['$', '{', '}', '<', '>']):
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
        raise HTTPException(status_code=400, detail="Ввод содержит запрещённые символы")

    # if not check_rate_limit(ip):
    #     raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    #                         detail="Too many login attempts. Please wait before retrying.")

    admin = await db.admins.find_one({"$or": [{"email": ident}, {"iin": ident}]})
    if admin:
        if not verify_password(data.password, admin["hashed_password"]):
            await db.login_logs.insert_one({"ident": ident, "timestamp": now, "success": False})
            raise HTTPException(status_code=401, detail="Неверные данные (admin)")

        if admin.get("active_session") and (
                admin["active_session"].get("ip") != ip or
                admin["active_session"].get("user_agent") != ua):
            await db.admins.update_one({"_id": admin["_id"]}, {"$set": {"is_verified": False}})
            await send_2fa_request(admin, ip, ua)
            raise HTTPException(status_code=403, detail="Подтвердите вход в Telegram")

        token = create_token({"sub": str(admin["_id"]), "role": admin["role"]})

        await db.admins.update_one({"_id": admin["_id"]}, {"$set": {
            "active_session": {"ip": ip, "user_agent": ua, "token": token},
            "last_login": {"timestamp": now, "ip": ip, "user_agent": ua},
            "is_verified": True
        }})

        await db.login_logs.insert_one({"ident": ident, "timestamp": now, "success": True})

        response = JSONResponse(content={
            "access_token": token,
            "token_type": "bearer"
        })
        return response

    user = await db.users.find_one({
        "$or": [
            {"iin": ident},
            {"email": ident.lower()}
        ]
    })

    if not user:
        # register_attempt(ip)
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    if not verify_password(data.password, user["hashed_password"]):
#         register_attempt(ip)
        raise HTTPException(status_code=400, detail="Incorrect username or password")

#     register_attempt(ip)

    token_data = {
        "sub": str(user["_id"]),
        "role": user.get("role", "user")
    }
    access_token, expires_at = create_access_token(token_data)

    await store_token_in_db(access_token, user["_id"], expires_at, ip, ua)

    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer"
    })
    return {"access_token": access_token, "token_type": "bearer"}



# -------------------------
# REGISTER
# -------------------------
@router.post("/register", response_model=TokenResponse)
async def register_user(user_data: UserCreate, request: Request):
    ip = request.client.host

    if not check_rate_limit(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много попыток регистрации. Попробуйте позже."
        )
    register_attempt(ip)

    if user_data.password != user_data.confirm_password:
        raise HTTPException(status_code=400, detail="Пароли не совпадают")

    existing_user = await db.users.find_one({
        "$or": [
            {"iin": user_data.iin},
            {"email": user_data.email.lower()},
            {"phone": user_data.phone}
        ]
    })
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким ИИН, Email или телефоном уже существует")

    hashed_pw = hash_password(user_data.password)

    new_user = {
        "iin": user_data.iin,
        "phone": user_data.phone,
        "email": user_data.email.lower(),
        "hashed_password": hashed_pw,
        "role": "user",
        "created_at": datetime.utcnow()
    }
    result = await db.users.insert_one(new_user)
    user_id = result.inserted_id

    logger.info(f"Регистрация нового пользователя: {user_data.email} (ID: {user_id})")

    # Генерируем JWT + узнаём время истечения
    token_data = {
        "sub": str(user_id),
        "role": "user"
    }
    access_token, expires_at = create_access_token(token_data)

    # Сохраняем в MongoDB (коллекция tokens)
    user_agent = request.headers.get("User-Agent", "unknown")
    await store_token_in_db(access_token, user_id, expires_at, ip, user_agent)

    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer"
    })
    return response


# -------------------------
# LOGOUT (Отзыв токена)
# -------------------------
@router.post("/logout")
async def logout_user(request: Request, credentials=Depends(security)):
    token = credentials.credentials
    payload = decode_token(token)
    user_id = payload.get("sub")
    role = payload.get("role")

    # Проверка допустимых ролей
    if role not in ["user", "admin", "moderator", "manager", "super_admin"]:
        raise HTTPException(status_code=403, detail="Недопустимая роль")

    # Логирование выхода
    logger.info(f"[LOGOUT] role={role} user_id={user_id} ip={request.client.host}")

    if role == "user":
        token_doc = await db.tokens.find_one({"token": token})
        if not token_doc:
            raise HTTPException(status_code=400, detail="Token not found or already invalid")

        await db.tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {"revoked": True}}
        )
        return {"detail": "Token has been revoked"}
    else:
        admin = await db.admins.find_one({"_id": ObjectId(user_id)})
        if not admin:
            raise HTTPException(status_code=404, detail="Админ не найден")

        await db.admins.update_one({"_id": ObjectId(user_id)}, {"$set": {"active_session": None}})
        return {"detail": f"Session closed for role: {role}"}
