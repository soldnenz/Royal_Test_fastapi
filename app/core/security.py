import logging
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from bson import ObjectId

from app.db.database import db
from app.core.config import settings

logger = logging.getLogger(__name__)

# Настраиваем bcrypt (passlib) для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Указываем эндпоинт, где выдаётся токен (логин)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    """
    Создаём access-токен (по умолчанию 7 дней).
    Возвращаем сам токен и время истечения (datetime),
    чтобы потом сохранить в БД.
    """
    to_encode = data.copy()
    expire_date = datetime.utcnow() + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire_date})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt, expire_date

async def store_token_in_db(token: str, user_id: ObjectId, expires_at: datetime):
    """
    Сохраняем токен в коллекцию tokens (MongoDB).
    """
    token_doc = {
        "user_id": user_id,
        "token": token,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "revoked": False
    }
    await db.tokens.insert_one(token_doc)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Декодируем JWT, проверяем, что:
      1) Токен синтаксически валиден (jwt.decode).
      2) Токен присутствует в БД (коллекция tokens).
      3) Токен не просрочен (expires_at).
      4) Токен не отозван (revoked).
      5) Пользователь (sub) есть в БД.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1) Декодируем и проверяем подпись
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("JWT payload missing 'sub' (user_id).")
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        logger.warning("Access token expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.PyJWTError as e:
        logger.warning(f"Invalid token: {e}")
        raise credentials_exception

    # 2) Ищем этот токен в БД
    token_doc = await db.tokens.find_one({"token": token})
    if not token_doc:
        logger.warning("Token not found in DB or was removed.")
        raise credentials_exception

    # 3) Не просрочен ли (с учётом expires_at в БД)
    now_utc = datetime.utcnow()
    if token_doc.get("expires_at") and token_doc["expires_at"] < now_utc:
        logger.warning("Token found in DB, but it's expired in DB. Marking as revoked.")
        # Можно сразу отозвать в БД, чтобы не было повторных проверок
        await db.tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {"revoked": True}}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 4) Проверяем, не отозван ли
    if token_doc.get("revoked"):
        logger.warning("Token is marked as revoked in DB.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 5) Проверяем наличие пользователя
    if not ObjectId.is_valid(user_id):
        logger.warning("Invalid user ID in token claims.")
        raise credentials_exception

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        logger.warning(f"User with ID={user_id} not found in database.")
        raise credentials_exception

    return user
