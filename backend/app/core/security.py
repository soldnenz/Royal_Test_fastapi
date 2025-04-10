import logging
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from bson import ObjectId
from app.core.response import error
from app.db.database import db
from app.core.config import settings

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta = None) -> tuple[str, datetime]:
    expire = datetime.utcnow() + (expires_delta or timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, expire


async def store_token_in_db(token: str, user_id: ObjectId, expires_at: datetime, ip: str, user_agent: str):
    # Ограничиваем до 3 активных токенов
    active_tokens = await db.tokens.find({
        "user_id": user_id,
        "revoked": False,
        "expires_at": {"$gt": datetime.utcnow()}
    }).sort("created_at", 1).to_list(length=100)

    if len(active_tokens) >= 3:
        oldest = active_tokens[0]
        await db.tokens.update_one({"_id": oldest["_id"]}, {"$set": {"revoked": True}})

    await db.tokens.insert_one({
        "user_id": user_id,
        "token": token,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "revoked": False,
        "ip": ip,
        "user_agent": user_agent,
        "last_activity": datetime.utcnow()
    })

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Токен не найден в cookie", "hint": "Авторизуйтесь, чтобы получить доступ"}
        )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id or not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"message": "Недействительный токен", "hint": "Проверьте корректность токена"}
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Срок действия токена истёк", "hint": "Выполните вход заново"}
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Ошибка валидации токена"}
        )

    token_doc = await db.tokens.find_one({"token": token})
    if not token_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Токен не найден в базе", "hint": "Повторите вход"}
        )

    if token_doc.get("revoked") or token_doc.get("expires_at") < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Токен отозван или просрочен"}
        )

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Пользователь не найден"}
        )

    await db.tokens.update_one(
        {"_id": token_doc["_id"]},
        {"$set": {
            "last_activity": datetime.utcnow(),
            "ip": request.client.host,
            "user_agent": request.headers.get("User-Agent", "unknown")
        }}
    )


async def get_current_actor(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"message": "Не передан токен (cookie)", "hint": "Добавьте токен в cookie"}
        )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")

        if not user_id or not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=401,
                detail={"message": "Некорректные данные токена", "hint": "Проверьте корректность токена"}
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"message": "Срок действия токена истёк", "hint": "Попробуйте войти снова"}
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail={"message": "Ошибка валидации токена", "hint": "Невозможно декодировать токен"}
        )

    if role == "user":
        token_doc = await db.tokens.find_one({"token": token})
        if not token_doc or token_doc.get("revoked") or token_doc["expires_at"] < datetime.utcnow():
            raise HTTPException(
                status_code=401,
                detail={"message": "Токен недействителен", "hint": "Он отозван или срок действия истёк"}
            )

        await db.tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {
                "last_activity": datetime.utcnow(),
                "ip": request.client.host,
                "user_agent": request.headers.get("User-Agent", "unknown")
            }}
        )

        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                status_code=404,
                detail={"message": "Пользователь не найден", "hint": "Нет пользователя с таким ID"}
            )

        return {
            "type": "user",
            "id": user["_id"],
            "role": role,
            "full_name": user.get("full_name"),  # 👈 добавляем ФИО
            "email": user.get("email"),
            "phone": user.get("phone"),
            "iin": user.get("iin"),
        }


    elif role == "admin":
        admin = await db.admins.find_one({"_id": ObjectId(user_id)})
        if not admin:
            raise HTTPException(
                status_code=404,
                detail={"message": "Администратор не найден", "hint": "Нет администратора с таким ID"}
            )

        active_session = admin.get("active_session")
        if not active_session or active_session.get("token") != token:
            raise HTTPException(
                status_code=401,
                detail={"message": "Сессия администратора не активна", "hint": "Неверный или устаревший токен"}
            )

        await db.admins.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "active_session.last_activity": datetime.utcnow(),
                "active_session.ip": request.client.host,
                "active_session.user_agent": request.headers.get("User-Agent", "unknown")
            }}
        )

        return {
            "type": "admin",
            "id": admin["_id"],
            "role": role,
            "full_name": admin.get("full_name"),
            "iin": admin.get("iin"),
        }

    raise HTTPException(
        status_code=403,
        detail={"message": "Неизвестная роль", "hint": "Роль не распознана"}
    )
