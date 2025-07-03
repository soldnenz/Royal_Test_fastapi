import re
import jwt
from datetime import datetime, timedelta
import os
from passlib.context import CryptContext
from fastapi import Request, HTTPException
import secrets  # Оставляем для token_id в create_token

# Новая структурированная система логирования
from app.logging import get_structured_logger, LogSection
from app.logging.log_models import LogSubsection


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

# КРИТИЧЕСКАЯ ПРОВЕРКА: SECRET_KEY должен быть установлен
if not SECRET_KEY:
    raise RuntimeError(
        "CRITICAL: SECRET_KEY environment variable must be set! "
        "This is required for JWT token security in both development and production."
    )

# Дополнительная проверка длины ключа для безопасности
if len(SECRET_KEY) < 32:
    raise RuntimeError(
        f"CRITICAL: SECRET_KEY too short ({len(SECRET_KEY)} characters). "
        f"Minimum required length is 32 characters for security."
    )

logger = get_structured_logger("admin.utils")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(user_id, role):
    """
    Безопасное создание JWT токена с дополнительными проверками
    """
    if not SECRET_KEY:
        raise RuntimeError("Cannot create token: SECRET_KEY not available")
    
    # Генерируем уникальный ID токена для отзыва
    token_id = secrets.token_urlsafe(16)
    
    payload = {
        "sub": str(user_id),  # Всегда строка для консистентности
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=24),  # 24 часа
        "iat": datetime.utcnow(),  # Время выдачи
        "jti": token_id,  # Уникальный ID токена
        "iss": "royal-test-api"  # Издатель токена
    }
    
    try:
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_VALIDATION,
            message=f"JWT токен успешно создан для пользователя {user_id} с ролью {role} - действует 24 часа до {(datetime.utcnow() + timedelta(hours=24)).strftime('%H:%M:%S %d.%m.%Y')}"
        )
        return token
    except Exception as e:
        logger.error(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_VALIDATION,
            message=f"ОШИБКА создания JWT токена для пользователя {user_id} с ролью {role}: {str(e)}"
        )
        raise RuntimeError(f"Token creation failed: {str(e)}")

def decode_token(token):
    """
    Безопасное декодирование JWT токена с улучшенной обработкой ошибок
    """
    if not SECRET_KEY:
        raise RuntimeError("Cannot decode token: SECRET_KEY not available")
    
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    
    try:
        # Декодируем токен с проверкой основных claims (обратная совместимость)
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": False,  # Не требуем iat для старых токенов
                "require": ["sub", "role", "exp"]  # Только обязательные поля
            }
        )
        
        # Дополнительные проверки
        if not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID")
        
        if not payload.get("role"):
            raise HTTPException(status_code=401, detail="Invalid token: missing role")
        
        # Проверяем издателя если он есть (опционально для обратной совместимости)
        if payload.get("iss") and payload["iss"] != "royal-test-api":
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.TOKEN_SECURITY,
                message=f"JWT токен с неправильным издателем {payload.get('iss')} - ожидался royal-test-api, но не блокируем для обратной совместимости"
            )
            # Не блокируем старые токены без issuer
        
        # Логируем информацию о токене для диагностики
        has_iat = "iat" in payload
        has_jti = "jti" in payload
        logger.debug(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_VALIDATION,
            message=f"JWT токен успешно расшифрован для пользователя {payload['sub']} - содержит дату выдачи: {has_iat}, содержит уникальный ID: {has_jti}"
        )
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_VALIDATION,
            message="Попытка использования истекшего JWT токена - пользователю нужно перелогиниться"
        )
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.TOKEN_SECURITY,
            message=f"Попытка использования недействительного JWT токена - возможная атака или поврежденный токен: {str(e)}"
        )
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_VALIDATION,
            message=f"Критическая ошибка при обработке JWT токена: {str(e)}"
        )
        raise HTTPException(status_code=401, detail="Token processing error")

def is_strong_password(password: str) -> bool:
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[0-9]", password)
    )

def sanitize_input(value: str) -> str:
    if any(c in value for c in ["$", "{", "}", "[", "]"]):
        raise ValueError("Неправильный ввод")
    return value

def get_ip(request):
    return request.client.host

def get_user_agent(request):
    return request.headers.get("user-agent", "")