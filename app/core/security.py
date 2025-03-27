import logging
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from bson import ObjectId

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


async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.PyJWTError:
        raise credentials_exception

    token_doc = await db.tokens.find_one({"token": token})
    if not token_doc:
        raise credentials_exception

    if token_doc.get("expires_at") < datetime.utcnow():
        await db.tokens.update_one({"_id": token_doc["_id"]}, {"$set": {"revoked": True}})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if token_doc.get("revoked"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not ObjectId.is_valid(user_id):
        raise credentials_exception

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise credentials_exception

    # Обновим информацию о последнем действии, IP и User-Agent
    await db.tokens.update_one(
        {"_id": token_doc["_id"]},
        {
            "$set": {
                "last_activity": datetime.utcnow(),
                "ip": request.client.host,
                "user_agent": request.headers.get("User-Agent", "unknown")
            }
        }
    )

    return user
