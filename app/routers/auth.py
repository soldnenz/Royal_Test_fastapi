import time
import logging
from datetime import datetime
import pytz
from bson import ObjectId
from fastapi import APIRouter, Request, HTTPException, status

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

router = APIRouter()
logger = logging.getLogger(__name__)

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

# -------------------------
# LOGIN
# -------------------------
@router.post("/login", response_model=TokenResponse)
async def login_user(auth_data: AuthRequest, request: Request):
    ip = request.client.host

    if not check_rate_limit(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait before retrying."
        )

    user = await db.users.find_one({
        "$or": [
            {"iin": auth_data.username},
            {"email": auth_data.username.lower()}
        ]
    })

    if not user:
        register_attempt(ip)
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    if not verify_password(auth_data.password, user["hashed_password"]):
        register_attempt(ip)
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    register_attempt(ip)

    # Формируем данные для JWT
    token_data = {
        "sub": str(user["_id"]),        # ID пользователя
        "role": user.get("role", "user")  # Роль пользователя (по умолчанию user)
    }
    # Генерируем JWT + узнаём время истечения
    access_token, expires_at = create_access_token(token_data)

    # Сохраняем в MongoDB (коллекция tokens)
    await store_token_in_db(access_token, user["_id"], expires_at)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )

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

    tz = pytz.timezone("Asia/Almaty")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    new_user = {
        "iin": user_data.iin,
        "phone": user_data.phone,
        "email": user_data.email.lower(),
        "hashed_password": hashed_pw,
        "role": "user",
        "created_at": now
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
    await store_token_in_db(access_token, user_id, expires_at)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )

# -------------------------
# LOGOUT (Отзыв токена)
# -------------------------
@router.post("/logout")
async def logout_user(request: Request, token: str = None):
    """
    Пример эндпоинта для 'выхода': помечаем токен как 'revoked'.
    Пользователь может передать токен напрямую (GET-параметр)
    или оставить в заголовке Authorization: Bearer ...
    """
    if not token:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header"
            )
        scheme, _, provided_token = auth_header.partition(" ")
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")
        token = provided_token.strip()

    token_doc = await db.tokens.find_one({"token": token})
    if not token_doc:
        raise HTTPException(status_code=400, detail="Token not found or already invalid")

    # Помечаем как отозванный
    await db.tokens.update_one(
        {"_id": token_doc["_id"]},
        {"$set": {"revoked": True}}
    )
    return {"detail": "Token has been revoked"}
