import time
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
from app.admin.utils import create_token, get_ip, get_user_agent
from app.admin.utils import decode_token
from app.admin.permissions import get_current_admin_user
from app.utils.twofa_client import twofa_client
import string
import secrets
import re
from app.core.response import success
from app.logging import get_logger, LogSection, LogSubsection

logger = get_logger(__name__)
router = APIRouter()
security = HTTPBearer()
# -------------------------
# SECURITY: INPUT VALIDATION
# -------------------------
def strict_validate_input(value: str, field_name: str, max_length: int = 100) -> str:
    """
    Строгая валидация входных данных для предотвращения NoSQL injection
    """
    if not isinstance(value, str):
        raise HTTPException(
            status_code=400,
            detail={"message": f"{field_name} должен быть строкой"}
        )
    
    # Запрещаем MongoDB операторы и специальные символы
    forbidden_chars = ['$', '{', '}', '[', ']', '<', '>', '|', '&', '*', '?', '^', '\\', '/', '"', "'"]
    if any(char in value for char in forbidden_chars):
        raise HTTPException(
            status_code=400,
            detail={"message": f"Поле {field_name} содержит запрещённые символы"}
        )
    
    # Проверяем на попытки инъекции
    injection_patterns = [
        r'\$\w+',  # MongoDB операторы типа $ne, $gt, etc.
        r'{\s*\$',  # Начало объекта с $
        r'"\s*:\s*{',  # JSON объекты
        r'null',  # null значения
        r'true|false',  # булевы значения
    ]
    
    for pattern in injection_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise HTTPException(
                status_code=400,
                detail={"message": f"Поле {field_name} содержит подозрительные конструкции"}
            )
    
    # Ограничиваем длину
    if len(value) > max_length:
        raise HTTPException(
            status_code=400,
            detail={"message": f"Поле {field_name} слишком длинное (максимум {max_length} символов)"}
        )
    
    # Убираем лишние пробелы
    return value.strip()

def validate_iin(iin: str) -> str:
    """Валидация ИИН - только 12 цифр"""
    iin = iin.strip()
    if not re.match(r'^\d{12}$', iin):
        raise HTTPException(
            status_code=400,
            detail={"message": "ИИН должен содержать ровно 12 цифр"}
        )
    return iin

def validate_email(email: str) -> str:
    """Валидация email"""
    email = email.strip().lower()
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise HTTPException(
            status_code=400,
            detail={"message": "Неверный формат email"}
        )
    return email

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

# Функции get_ip и get_user_agent импортированы из app.admin.utils
# Функция sanitize_input удалена - используем strict_validate_input

# -------------------------
# LOGIN
# -------------------------
@router.post("/login")
async def unified_login(data: AuthRequest, request: Request):
    ip = get_ip(request)
    ua = get_user_agent(request)
    now = datetime.utcnow()

    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.LOGIN_ATTEMPT,
        message=f"Попытка входа с IP {ip} - логин: {data.username[:10]}..."
    )

    # СТРОГАЯ ВАЛИДАЦИЯ входных данных
    try:
        # Определяем тип ввода (ИИН или email) и валидируем соответственно
        username_input = strict_validate_input(data.username, "username", 100)
        password_input = strict_validate_input(data.password, "password", 200)
        
        # Дополнительная валидация по типу
        if re.match(r'^\d{12}$', username_input):
            # Это ИИН
            ident = validate_iin(username_input)
            search_field = "iin"
        elif '@' in username_input:
            # Это email
            ident = validate_email(username_input)
            search_field = "email"
        else:
            raise HTTPException(
                status_code=400,
                detail={"message": "Логин должен быть валидным ИИН (12 цифр) или email"}
            )
    except HTTPException:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.LOGIN_FAILED,
            message=f"Некорректный ввод данных входа с IP {ip} - логин: {data.username[:10]}..."
        )
        register_attempt(ip)
        raise

    if not check_rate_limit(ip):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.RATE_LIMIT,
            message=f"Превышен лимит попыток входа с IP {ip} - заблокировано на 5 минут"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": "Превышен лимит попыток входа"}
        )

    # БЕЗОПАСНЫЙ поиск админа (используем точное соответствие поля)
    admin = await db.admins.find_one({search_field: ident})
    if admin:
        if not verify_password(data.password, admin["hashed_password"]):
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.LOGIN_FAILED,
                message=f"Неверный пароль администратора {admin.get('full_name', 'неизвестен')} ({admin.get('email') or admin.get('iin')}) с IP {ip}"
            )
            await db.login_logs.insert_one({"ident": ident, "timestamp": now, "success": False})
            raise HTTPException(
                status_code=401,
                detail={"message": "Неправильный IIN, Email или пароль"}
            )

        # 2FA если другой IP или UA
        requires_2fa = False
        old_ip = "неизвестен"
        
        # Проверяем активную сессию
        if admin.get("active_session"):
            if (admin["active_session"].get("ip") != ip or
                admin["active_session"].get("user_agent") != ua):
                requires_2fa = True
                old_ip = admin["active_session"].get("ip", "неизвестен")
        # Если нет активной сессии, проверяем last_login
        elif admin.get("last_login"):
            if (admin["last_login"].get("ip") != ip or
                admin["last_login"].get("user_agent") != ua):
                requires_2fa = True
                old_ip = admin["last_login"].get("ip", "неизвестен")
        
        if requires_2fa:
            logger.info(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                message=f"Требуется 2FA для администратора {admin.get('full_name', 'неизвестен')} ({admin.get('email') or admin.get('iin')}) - смена IP с {old_ip} на {ip}"
            )
            await db.admins.update_one({"_id": admin["_id"]}, {"$set": {"is_verified": False}})
            
            # Отправляем 2FA запрос через микросервис
            result = await twofa_client.send_2fa_request(admin, ip, ua)
            
            if not result.get("success"):
                logger.error(
                    section=LogSection.AUTH,
                    subsection=LogSubsection.AUTH.TWO_FACTOR_REQUIRED,
                    message=f"Ошибка отправки 2FA запроса для администратора {admin.get('full_name', 'неизвестен')}: {result.get('message', 'Неизвестная ошибка')}"
                )
                raise HTTPException(
                    status_code=500,
                    detail={"message": "Ошибка сервиса 2FA. Попробуйте позже."}
                )
            
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

        logger.info(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.ADMIN_LOGIN_SUCCESS,
            message=f"Успешный вход администратора {admin.get('full_name', 'неизвестен')} ({admin.get('email') or admin.get('iin')}) с ролью {admin['role']} с IP {ip}"
        )

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

    # БЕЗОПАСНЫЙ поиск пользователя (используем точное соответствие поля)
    user = await db.users.find_one({search_field: ident})

    if not user:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.LOGIN_FAILED,
            message=f"Пользователь не найден с логином {ident} с IP {ip}"
        )
        register_attempt(ip)
        raise HTTPException(
            status_code=401,
            detail={"message": "Неправильный IIN, Email или пароль"}
        )

    # Проверяем, заблокирован ли пользователь
    if user.get("is_banned", False):
        ban_info = user.get("ban_info", {})
        
        # Формируем сообщение о блокировке
        if ban_info.get("ban_type") == "permanent":
            error_message = "Ваш аккаунт заблокирован навсегда. Причина: " + ban_info.get("reason", "Нарушение правил")
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.LOGIN_BLOCKED,
                message=f"Попытка входа заблокированного навсегда пользователя {user.get('full_name', 'неизвестен')} ({user.get('email') or user.get('iin')}) с IP {ip} - причина блокировки: {ban_info.get('reason', 'Нарушение правил')}"
            )
            raise HTTPException(status_code=403, detail={"message": error_message, "ban_type": "permanent"})
        else:
            ban_until = ban_info.get("ban_until")
            if ban_until:
                now = datetime.utcnow()
                if ban_until > now:
                    # Вычисляем оставшееся время
                    time_left = ban_until - now
                    days = time_left.days
                    hours, remainder = divmod(time_left.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    
                    time_str = ""
                    if days > 0:
                        time_str += f"{days} дн. "
                    if hours > 0:
                        time_str += f"{hours} ч. "
                    if minutes > 0:
                        time_str += f"{minutes} мин."
                    
                    ban_until_str = ban_until.strftime("%H:%M:%S %d.%m.%Y")
                    error_message = f"Ваш аккаунт временно заблокирован. Осталось: {time_str}. Причина: {ban_info.get('reason', 'Нарушение правил')}"
                    logger.warning(
                        section=LogSection.AUTH,
                        subsection=LogSubsection.AUTH.LOGIN_BLOCKED,
                        message=f"Попытка входа временно заблокированного пользователя {user.get('full_name', 'неизвестен')} ({user.get('email') or user.get('iin')}) с IP {ip} - бан до {ban_until_str}, осталось {time_str}, причина: {ban_info.get('reason', 'Нарушение правил')}"
                    )
                    raise HTTPException(
                        status_code=403, 
                        detail={"message": error_message, "ban_type": "temporary", "time_left": time_str}
                    )
                else:
                    # Срок бана истек, разблокируем пользователя
                    await db.users.update_one(
                        {"_id": user["_id"]},
                        {
                            "$set": {"is_banned": False},
                            "$unset": {"ban_info": ""}
                        }
                    )
                    
                    # Деактивируем запись о блокировке в коллекции user_bans
                    if "ban_id" in ban_info:
                        await db.user_bans.update_one(
                            {"_id": ObjectId(ban_info["ban_id"]), "is_active": True},
                            {
                                "$set": {
                                    "is_active": False,
                                    "auto_unbanned_at": now
                                }
                            }
                        )
                    logger.info(
                        section=LogSection.AUTH,
                        subsection=LogSubsection.AUTH.AUTO_UNBAN,
                        message=f"Автоматическая разблокировка пользователя {user.get('full_name', 'неизвестен')} ({user.get('email') or user.get('iin')}) с IP {ip} - срок временной блокировки истек"
                    )

    if not verify_password(data.password, user["hashed_password"]):
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.LOGIN_FAILED,
            message=f"Неверный пароль пользователя {user.get('full_name', 'неизвестен')} ({user.get('email') or user.get('iin')}) с IP {ip}"
        )
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

    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.LOGIN_SUCCESS,
        message=f"Успешный вход пользователя {user.get('full_name', 'неизвестен')} ({user.get('email') or user.get('iin')}) с IP {ip} - создан токен действующий до {expires_at.strftime('%H:%M:%S %d.%m.%Y')}"
    )

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

    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.REGISTER_ATTEMPT,
        message=f"Попытка регистрации пользователя с IP {ip} - email: {user_data.email}, ИИН: {user_data.iin[:8]}..."
    )

    if not check_rate_limit(ip):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.RATE_LIMIT,
            message=f"Превышен лимит попыток регистрации с IP {ip} - заблокировано на 5 минут"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": "Превышен лимит попыток входа"}
        )

    register_attempt(ip)

    # БЕЗОПАСНАЯ ВАЛИДАЦИЯ входных данных
    try:
        user_data.iin = validate_iin(user_data.iin)
        user_data.email = validate_email(user_data.email)
        user_data.phone = strict_validate_input(user_data.phone, "phone", 20)
        user_data.full_name = strict_validate_input(user_data.full_name, "full_name", 100)
        if user_data.referred_by:
            user_data.referred_by = strict_validate_input(user_data.referred_by, "referred_by", 50)
    except HTTPException:
        # strict_validate_input уже вызывает HTTPException
        raise
    except Exception as e:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.REGISTER_FAILED,
            message=f"Некорректный ввод данных регистрации с IP {ip} - {str(e)}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Ввод содержит запрещённые символы"}
        )
    if user_data.password != user_data.confirm_password:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.REGISTER_FAILED,
            message=f"Пароли не совпадают при регистрации с IP {ip} - email: {user_data.email}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Пароли не совпадают"}
        )

    # БЕЗОПАСНЫЙ поиск существующего пользователя (защита от NoSQL injection)
    existing_user = await db.users.find_one({
        "$or": [
            {"iin": user_data.iin},  # уже валидированный ИИН
            {"email": user_data.email},  # уже валидированный email
            {"phone": user_data.phone}  # уже валидированный phone
        ]
    })
    if existing_user:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.REGISTER_FAILED,
            message=f"Попытка регистрации с уже существующими данными с IP {ip} - email: {user_data.email}, ИИН: {user_data.iin}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Пользователь с таким ИИН, Email или телефоном уже существует"}
        )

    # БЕЗОПАСНЫЙ поиск существующего админа
    existing_admin = await db.admins.find_one({
        "$or": [
            {"iin": user_data.iin},  # уже валидированный ИИН
            {"email": user_data.email}  # уже валидированный email
        ]
    })
    if existing_admin:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
            message=f"Попытка регистрации пользователя с данными администратора с IP {ip} - ИИН: {user_data.iin}, email: {user_data.email}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Пользователь с таким ИИН, Email или телефоном уже существует"}
        )

    # ✅ Проверяем, существует ли пригласивший
    referred_by = None
    if user_data.referred_by:
        ref_owner = await db.referrals.find_one({"code": user_data.referred_by})
        if not ref_owner:
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.REGISTER_FAILED,
                message=f"Использован несуществующий реферальный код {user_data.referred_by} при регистрации с IP {ip} - email: {user_data.email}"
            )
            raise HTTPException(
                status_code=400,
                detail={"message": "Указанный реферальный код не найден"}
            )
        referred_by = user_data.referred_by  # Привязываем к пользователю, который пригласил
        logger.info(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.REFERRAL_USED,
            message=f"Пользователь {user_data.full_name} ({user_data.email}) использовал реферальный код {referred_by} при регистрации с IP {ip}"
        )

    hashed_password = hash_password(user_data.password)

    new_user = {
        "full_name": user_data.full_name,
        "iin": user_data.iin,
        "phone": user_data.phone,
        "email": user_data.email,  # уже приведен к lower() в validate_email
        "hashed_password": hashed_password,
        "role": "user",
        "created_at": datetime.utcnow(),
        "referred_by": referred_by,
        "money": user_data.money,  # добавлено поле money (включая значение по умолчанию 0.0)
        "referred_use": user_data.referred_use,  # добавлено поле referred_use
        "is_banned": False  # инициализация статуса бана
    }

    result = await db.users.insert_one(new_user)
    user_id = result.inserted_id

    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.REGISTER_SUCCESS,
        message=f"Успешная регистрация пользователя {user_data.full_name} ({user_data.email}) с ID {user_id} с IP {ip}"
    )

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
# GUEST REGISTER
# -------------------------
@router.post("/guest-register")
async def guest_register(data: dict, request: Request):
    """Register a guest user for School lobbies"""
    ip = request.client.host

    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.GUEST_REGISTER_ATTEMPT,
        message=f"Попытка гостевой регистрации с IP {ip} - имя: {data.get('name', 'неизвестно')[:20]}..., лобби: {data.get('lobby_id', 'неизвестно')[:10]}..."
    )

    if not check_rate_limit(ip):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.RATE_LIMIT,
            message=f"Превышен лимит попыток гостевой регистрации с IP {ip} - заблокировано на 5 минут"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": "Превышен лимит попыток входа"}
        )

    register_attempt(ip)

    name = data.get("name", "").strip()
    lobby_id = data.get("lobby_id", "").strip()

    if not name or len(name) < 1:
        raise HTTPException(
            status_code=400,
            detail={"message": "Имя должно содержать минимум 1 символ"}
        )

    if len(name) > 50:
        raise HTTPException(
            status_code=400,
            detail={"message": "Имя не должно превышать 50 символов"}
        )

    if not lobby_id:
        raise HTTPException(
            status_code=400,
            detail={"message": "ID лобби обязателен"}
        )

    try:
        name = strict_validate_input(name, "name", 50)
    except HTTPException:
        # strict_validate_input уже вызывает HTTPException, просто перебрасываем
        raise
    except Exception as e:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.GUEST_REGISTER_FAILED,
            message=f"Некорректное имя при гостевой регистрации с IP {ip}: {str(e)}"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Имя содержит запрещённые символы"}
        )

    # Check if lobby exists and allows guests (School subscription)
    lobby = await db.lobbies.find_one({"_id": lobby_id})
    if not lobby:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.GUEST_REGISTER_FAILED,
            message=f"Попытка регистрации в несуществующее лобби {lobby_id} с IP {ip}"
        )
        raise HTTPException(
            status_code=404,
            detail={"message": "Лобби не найдено"}
        )

    # Check if lobby host has School subscription
    host = await db.users.find_one({"_id": ObjectId(lobby["host_id"])})
    if not host:
        logger.error(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.GUEST_REGISTER_FAILED,
            message=f"Хост лобби {lobby['host_id']} не найден при гостевой регистрации в лобби {lobby_id} с IP {ip}"
        )
        raise HTTPException(
            status_code=404,
            detail={"message": "Хост лобби не найден"}
        )

    # Check host subscription
    host_subscription = await db.subscriptions.find_one({
        "user_id": ObjectId(lobby["host_id"]),
        "is_active": True,
        "expires_at": {"$gt": datetime.utcnow()}
    })

    if not host_subscription or host_subscription.get("subscription_type", "").lower() != "school":
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.GUEST_REGISTER_FAILED,
            message=f"Попытка гостевой регистрации в лобби {lobby_id} без School подписки хоста {host.get('full_name', 'неизвестен')} ({lobby['host_id']}) с IP {ip}"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Только лобби с подпиской School разрешают гостевой доступ"}
        )

    # Generate unique guest ID
    guest_id = f"guest_{secrets.token_urlsafe(8)}"

    # Create guest user document
    guest_user = {
        "_id": guest_id,
        "full_name": name,
        "email": f"{guest_id}@guest.local",
        "role": "guest",
        "is_guest": True,
        "lobby_id": lobby_id,
        "created_at": datetime.utcnow(),
        "ip_address": ip
    }

    await db.guests.insert_one(guest_user)

    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.GUEST_REGISTER_SUCCESS,
        message=f"Успешная гостевая регистрация: {name} (ID: {guest_id}) для лобби {lobby_id} хоста {host.get('full_name', 'неизвестен')} с IP {ip}"
    )

    # Create token for guest
    token_data = {
        "sub": guest_id,
        "role": "guest",
        "lobby_id": lobby_id
    }
    access_token, expires_at = create_access_token(token_data)

    user_agent = request.headers.get("User-Agent", "unknown")
    await store_token_in_db(access_token, guest_id, expires_at, ip, user_agent)

    return success(data={
        "access_token": access_token, 
        "token_type": "bearer",
        "guest_id": guest_id,
        "guest_name": name
    })


# -------------------------
# LOGOUT (Отзыв токена)
# -------------------------
@router.post("/logout")
async def logout_user(request: Request):
    ip = request.client.host
    
    # Получаем токен из cookies
    token = request.cookies.get("access_token")

    if not token:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.LOGOUT_FAILED,
            message=f"Попытка выхода без токена с IP {ip}"
        )
        raise HTTPException(
            status_code=401,
            detail={"message": "Не передан токен (cookie)", "hint": "Добавьте токен в cookie"}
        )

    # Декодируем токен
    try:
        payload = decode_token(token)
    except Exception as e:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.LOGOUT_FAILED,
            message=f"Ошибка декодирования токена при выходе с IP {ip}: {str(e)}"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Ошибка декодирования токена", "hint": str(e)}
        )

    user_id = payload.get("sub")
    role = payload.get("role")

    # Проверка роли
    if role not in ["user", "admin", "moderator", "manager", "super_admin", "guest"]:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
            message=f"Недопустимая роль {role} при выходе пользователя {user_id} с IP {ip}"
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Недопустимая роль"}
        )

    # Подготовка ответа
    response = success(message="Вы успешно вышли из системы")
    response.delete_cookie("access_token")  # Удаляем куку с токеном

    # Логика для пользователя и гостя
    if role in ["user", "guest"]:
        token_doc = await db.tokens.find_one({"token": token})
        if not token_doc:
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.LOGOUT_FAILED,
                message=f"Токен не найден в БД при выходе пользователя {user_id} с ролью {role} с IP {ip}"
            )
            raise HTTPException(
                status_code=404,
                detail={"message": "Пользователь не найден по токену"}
            )

        await db.tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {"revoked": True}}
        )

        # Для гостей также удаляем запись из коллекции guests
        if role == "guest":
            guest = await db.guests.find_one({"_id": user_id})
            guest_name = guest.get("full_name", "неизвестен") if guest else "неизвестен"
            await db.guests.delete_one({"_id": user_id})
            logger.info(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.LOGOUT_SUCCESS,
                message=f"Успешный выход гостя {guest_name} ({user_id}) с IP {ip} - запись удалена из БД"
            )
        else:
            # Получаем информацию о пользователе для лога
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            user_name = user.get("full_name", "неизвестен") if user else "неизвестен"
            logger.info(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.LOGOUT_SUCCESS,
                message=f"Успешный выход пользователя {user_name} ({user_id}) с IP {ip} - токен отозван"
            )

        return response

    # Логика для администраторов
    admin = await db.admins.find_one({"_id": ObjectId(user_id)})
    if not admin:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.LOGOUT_FAILED,
            message=f"Администратор {user_id} не найден при выходе с IP {ip}"
        )
        raise HTTPException(
            status_code=404,
            detail={"message": "Админ не найден"}
        )

    await db.admins.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"active_session": None}}
    )

    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.LOGOUT_SUCCESS,
        message=f"Успешный выход администратора {admin.get('full_name', 'неизвестен')} ({user_id}) с ролью {role} с IP {ip} - сессия закрыта"
    )
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
    if admin["role"] not in ["admin", "moderator", "super_admin", "tests_creator"]:
        logger.warning(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.ADMIN_VALIDATION_FAILED,
            message=f"Недостаточно прав для доступа к админ-панели: {admin.get('full_name', 'неизвестен')} ({admin['_id']}) с ролью {admin['role']}"
        )
        return Response(status_code=404)
    
    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.ADMIN_VALIDATION_SUCCESS,
        message=f"Успешная валидация доступа к админ-панели: {admin.get('full_name', 'неизвестен')} ({admin['_id']}) с ролью {admin['role']}"
    )
    return Response(status_code=204)
