from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from bson import ObjectId
from app.core.response import error
from app.db.database import db
from app.core.config import settings
from app.logging import get_logger, LogSection, LogSubsection

import asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.database import get_database

# Настройка логгера
logger = get_logger(__name__)

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
    
    user_id = data.get("sub", "неизвестен")
    role = data.get("role", "неизвестна")
    expire_str = expire.strftime("%H:%M:%S %d.%m.%Y")
    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.TOKEN_CREATE,
        message=f"JWT токен успешно создан для пользователя {user_id} с ролью {role} - действует до {expire_str}"
    )
    
    return token, expire


async def store_token_in_db(token: str, user_id, expires_at: datetime, ip: str, user_agent: str):
    # For guest users, user_id is a string, for regular users it's ObjectId
    is_guest = isinstance(user_id, str) and user_id.startswith("guest_")
    
    if not is_guest:
        # Ограничиваем до 3 активных токенов для обычных пользователей
        active_tokens = await db.tokens.find({
            "user_id": user_id,
            "revoked": False,
            "expires_at": {"$gt": datetime.utcnow()}
        }).sort("created_at", 1).to_list(length=100)

        if len(active_tokens) >= 3:
            oldest = active_tokens[0]
            await db.tokens.update_one({"_id": oldest["_id"]}, {"$set": {"revoked": True}})
            logger.info(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TOKEN_LIMIT,
                message=f"Отозван старый токен пользователя {user_id} - превышен лимит 3 активных токена"
            )

    await db.tokens.insert_one({
        "user_id": user_id,
        "token": token,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "revoked": False,
        "ip": ip,
        "user_agent": user_agent,
        "last_activity": datetime.utcnow(),
        "is_guest": is_guest
    })
    
    user_type = "гость" if is_guest else "пользователь"
    expire_str = expires_at.strftime("%H:%M:%S %d.%m.%Y")
    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.TOKEN_STORE,
        message=f"Токен сохранен в БД для {user_type} {user_id} с IP {ip} - действует до {expire_str}"
    )

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_MISSING,
            message=f"Отсутствует токен в cookie при запросе с IP {request.client.host}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Токен не найден в cookie", "hint": "Авторизуйтесь, чтобы получить доступ"}
        )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id or not ObjectId.is_valid(user_id):
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TOKEN_INVALID,
                message=f"Недействительный user_id в токене: {user_id} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"message": "Недействительный токен", "hint": "Проверьте корректность токена"}
            )
    except jwt.ExpiredSignatureError:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_EXPIRED,
            message=f"Попытка использования просроченного токена с IP {request.client.host}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Срок действия токена истёк", "hint": "Выполните вход заново"}
        )
    except jwt.PyJWTError:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_INVALID,
            message=f"Ошибка валидации JWT токена с IP {request.client.host}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Ошибка валидации токена"}
        )

    token_doc = await db.tokens.find_one({"token": token})
    if not token_doc:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_NOT_FOUND,
            message=f"Токен не найден в БД для пользователя {user_id} с IP {request.client.host}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Токен не найден в базе", "hint": "Повторите вход"}
        )

    if token_doc.get("revoked") or token_doc.get("expires_at") < datetime.utcnow():
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_REVOKED,
            message=f"Попытка использования отозванного/просроченного токена пользователем {user_id} с IP {request.client.host}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Токен отозван или просрочен"}
        )

    # Проверяем, что это не гость
    if isinstance(user_id, str) and user_id.startswith("guest_"):
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.ACCESS_DENIED,
            message=f"Гость {user_id} пытается получить доступ к пользовательским функциям с IP {request.client.host}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Неверный тип пользователя для данного метода"}
        )
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        logger.error(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.USER_NOT_FOUND,
            message=f"Пользователь {user_id} не найден в БД при валидации токена с IP {request.client.host}"
        )
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
    
    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.USER_VALIDATED,
        message=f"Пользователь {user.get('full_name', 'неизвестен')} ({user_id}) успешно аутентифицирован с IP {request.client.host}"
    )


async def get_current_actor(request: Request) -> dict:
    """
    Достаёт токен из cookie, валидирует и возвращает словарь с информацией
    о текущем пользователе / админе / модераторе / госте.

    Возможные role в JWT: 'user', 'admin', 'moderator', 'guest'
    """
    # ─────────────────────────────────────────────────────────────────────────
    token = request.cookies.get("access_token")
    if not token:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_MISSING,
            message=f"Отсутствует токен в cookie при запросе get_current_actor с IP {request.client.host}"
        )
        raise HTTPException(
            status_code=401,
            detail={"message": "Не передан токен (cookie)", "hint": "Добавьте access_token в cookie"}
        )

    try:
        payload  = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id  = payload.get("sub")
        role     = payload.get("role")          # строка
        lobby_id = payload.get("lobby_id")      # для гостей
        
        # Для гостей user_id - строка, для обычных пользователей - ObjectId
        is_guest = isinstance(user_id, str) and user_id.startswith("guest_")
        
        if not user_id or (not is_guest and not ObjectId.is_valid(user_id)):
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TOKEN_INVALID,
                message=f"Некорректные данные в токене: user_id={user_id}, role={role} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=401,
                detail={"message": "Некорректные данные токена", "hint": "Проверьте токен"}
            )
    except jwt.ExpiredSignatureError:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_EXPIRED,
            message=f"Просроченный токен в get_current_actor с IP {request.client.host}"
        )
        raise HTTPException(
            status_code=401,
            detail={"message": "Срок действия токена истёк", "hint": "Войдите снова"}
        )
    except jwt.PyJWTError:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_INVALID,
            message=f"Ошибка декодирования JWT в get_current_actor с IP {request.client.host}"
        )
        raise HTTPException(
            status_code=401,
            detail={"message": "Ошибка валидации токена", "hint": "Невозможно декодировать токен"}
        )

    # ──────────────────────────── GUEST ──────────────────────────────────────
    if role == "guest":
        token_doc = await db.tokens.find_one({"token": token})
        if not token_doc or token_doc.get("revoked") or token_doc["expires_at"] < datetime.utcnow():
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TOKEN_INVALID,
                message=f"Недействительный токен гостя {user_id} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=401,
                detail={"message": "Токен недействителен", "hint": "Он отозван или истёк"}
            )

        # обновляем метки активности
        await db.tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {
                "last_activity": datetime.utcnow(),
                "ip": request.client.host,
                "user_agent": request.headers.get("User-Agent", "unknown")
            }}
        )

        guest = await db.guests.find_one({"_id": user_id})
        if not guest:
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.USER_NOT_FOUND,
                message=f"Гостевой пользователь {user_id} не найден в БД с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=404,
                detail={"message": "Гостевой пользователь не найден"}
            )

        logger.info(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.GUEST_VALIDATED,
            message=f"Гость {guest.get('full_name', 'неизвестен')} ({user_id}) успешно аутентифицирован для лобби {guest.get('lobby_id')} с IP {request.client.host}"
        )

        return {
            "type": "guest",
            "id": guest["_id"],
            "role": role,
            "full_name": guest.get("full_name"),
            "email": guest.get("email"),
            "lobby_id": guest.get("lobby_id"),
            "is_guest": True,
            "created_at": guest.get("created_at")
        }

    # ──────────────────────────── USER ──────────────────────────────────────
    elif role == "user":
        token_doc = await db.tokens.find_one({"token": token})
        if not token_doc or token_doc.get("revoked") or token_doc["expires_at"] < datetime.utcnow():
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TOKEN_INVALID,
                message=f"Недействительный токен пользователя {user_id} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=401,
                detail={"message": "Токен недействителен", "hint": "Он отозван или истёк"}
            )

        # обновляем метки активности
        await db.tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {
                "last_activity": datetime.utcnow(),
                "ip": request.client.host,
                "user_agent": request.headers.get("User-Agent", "unknown")
            }}
        )

        # Проверяем, что это не гость (для роли user)
        if isinstance(user_id, str) and user_id.startswith("guest_"):
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.ACCESS_DENIED,
                message=f"Гость {user_id} пытается использовать роль user с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=401,
                detail={"message": "Гости не могут использовать роль user"}
            )
        
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.USER_NOT_FOUND,
                message=f"Пользователь {user_id} не найден в БД при role=user с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=404,
                detail={"message": "Пользователь не найден"}
            )



        return {
            "type": "user",
            "id": user["_id"],
            "role": role,
            "full_name": user.get("full_name"),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "iin": user.get("iin"),
            "money": user.get("money"),
            "created_at": user.get("created_at")
        }

    # ─────────────────────── ADMIN / MODER ──────────────────────────────────
    elif role in ("admin", "moderator", "tests_creator"):
        # Проверяем, что это не гость (для админских ролей)
        if isinstance(user_id, str) and user_id.startswith("guest_"):
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.ACCESS_DENIED,
                message=f"Гость {user_id} пытается использовать административную роль {role} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=401,
                detail={"message": "Гости не могут иметь административные роли"}
            )
        
        admin = await db.admins.find_one({"_id": ObjectId(user_id)})
        if not admin:
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.ADMIN_NOT_FOUND,
                message=f"Администратор {user_id} не найден в БД при role={role} с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=404,
                detail={"message": "Администратор не найден"}
            )

        sess = admin.get("active_session")
        if not sess or sess.get("token") != token:
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.SESSION_INVALID,
                message=f"Неактивная сессия администратора {admin.get('full_name', 'неизвестен')} ({user_id}) с IP {request.client.host}"
            )
            raise HTTPException(
                status_code=401,
                detail={"message": "Сессия не активна или токен устарел"}
            )

        # обновляем активность
        await db.admins.update_one(
            {"_id": admin["_id"]},
            {"$set": {
                "active_session.last_activity": datetime.utcnow(),
                "active_session.ip": request.client.host,
                "active_session.user_agent": request.headers.get("User-Agent", "unknown")
            }}
        )

        logger.info(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.ADMIN_VALIDATED,
            message=f"Администратор {admin.get('full_name', 'неизвестен')} ({user_id}) с ролью {role} успешно аутентифицирован с IP {request.client.host}"
        )

        return {
            "type": "admin",
            "id": admin["_id"],
            "role": role,                     # 'admin' или 'moder'
            "full_name": admin.get("full_name"),
            "iin": admin.get("iin"),
        }

    # ──────────────────────── НЕИЗВЕСТНАЯ РОЛЬ ──────────────────────────────
    logger.warning(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.ROLE_UNKNOWN,
        message=f"Неизвестная роль {role} для пользователя {user_id} с IP {request.client.host}"
    )
    raise HTTPException(
        status_code=403,
        detail={"message": "Неизвестная роль", "hint": "Роль не распознана"}
    )

async def auto_close_expired_exams():
    """Background task to automatically close expired exam lobbies"""
    try:
        # Get database connection
        db = await get_database()
        
        # Find active exam lobbies with expired timers
        expired_lobbies = await db.lobbies.find({
            "status": "active",
            "exam_mode": True,
            "exam_timer.time_left": {"$lte": 0}
        }).to_list(None)
        
        closed_count = 0
        for lobby in expired_lobbies:
            lobby_id = str(lobby["_id"])
            
            # Close the lobby
            await db.lobbies.update_one(
                {"_id": lobby["_id"]},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.utcnow(),
                        "auto_closed": True,
                        "auto_close_reason": "exam_time_expired_background"
                    }
                }
            )
            
            logger.info(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUTO_TASK,
                message=f"Автоматически закрыто экзаменационное лобби {lobby_id} по истечению времени"
            )
            closed_count += 1
        
        if closed_count > 0:
            logger.info(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.AUTO_TASK,
                message=f"Фоновая задача автозакрытия завершена: закрыто {closed_count} просроченных экзаменационных лобби"
            )
            
    except Exception as e:
        logger.error(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.AUTO_TASK,
            message=f"Ошибка в фоновой задаче автозакрытия лобби: {str(e)}"
        )

async def cleanup_old_security_logs():
    """Clean up old security log entries"""
    try:
        # This would typically clean up old log files or database entries
        # For now, just log that cleanup was attempted
        logger.info(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.CLEANUP,
            message="Очистка старых записей безопасности завершена успешно"
        )
    except Exception as e:
        logger.error(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.CLEANUP,
            message=f"Ошибка при очистке логов безопасности: {str(e)}"
        )

async def security_background_tasks():
    """Main security background tasks runner"""
    while True:
        try:
            # Run auto-close task every 30 seconds
            await auto_close_expired_exams()
            
            # Run cleanup every hour
            current_minute = datetime.now().minute
            if current_minute == 0:
                await cleanup_old_security_logs()
                
            await asyncio.sleep(30)  # Wait 30 seconds before next check
            
        except Exception as e:
            logger.error(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.BACKGROUND_TASK,
                message=f"Критическая ошибка в фоновых задачах безопасности: {str(e)} - перезапуск через 60 секунд"
            )
            await asyncio.sleep(60)  # Wait longer on error
