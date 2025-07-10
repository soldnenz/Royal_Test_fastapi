from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
import time
from typing import Optional

from database import get_database
from telegram_bot import send_2fa_request, cleanup_expired_requests
from schemas import TwoFARequest, TwoFAResponse, TwoFAStatus, HealthCheck
from log_system import get_2fa_logger, LogSection, LogSubsection

logger = get_2fa_logger()

# Создаем роутер
router = APIRouter()

# Rate limiting
MAX_REQUESTS_PER_MINUTE = 10
request_counts = {}


def check_rate_limit(ip: str) -> bool:
    """Проверка rate limit"""
    # Нормализуем IP адрес для rate limiting
    if not ip or ip.lower() in ["unknown", "none", "null", ""]:
        ip = "unknown"
    
    now = time.time()
    if ip not in request_counts:
        request_counts[ip] = []
    
    # Удаляем старые запросы (старше 1 минуты)
    request_counts[ip] = [t for t in request_counts[ip] if (now - t) <= 60]
    
    if len(request_counts[ip]) >= MAX_REQUESTS_PER_MINUTE:
        return False
    
    request_counts[ip].append(now)
    return True


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        # Проверяем подключение к базе данных
        db = await get_database()
        await db.command("ping")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # Проверяем Telegram бота
    try:
        from telegram_bot import bot
        await bot.get_me()
        bot_status = "connected"
    except Exception as e:
        bot_status = f"error: {str(e)}"
    
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        database=db_status,
        telegram_bot=bot_status
    )


@router.post("/send-2fa", response_model=TwoFAResponse)
async def send_2fa_request_endpoint(
    request_data: TwoFARequest,
    http_request: Request,
    db=Depends(get_database)
):
    """Отправка 2FA запроса"""
    ip = http_request.client.host if http_request.client and http_request.client.host else "unknown"
    
    logger.info(
        section=LogSection.API,
        subsection=LogSubsection.API.REQUEST,
        message=f"Получен запрос на отправку 2FA для администратора {request_data.admin_name} с IP {ip}"
    )
    
    # Проверяем rate limit
    if not check_rate_limit(ip):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.RATE_LIMIT,
            message=f"Превышен лимит запросов с IP {ip}"
        )
        raise HTTPException(
            status_code=429,
            detail={"message": "Превышен лимит запросов"}
        )
    
    # Валидация входных данных
    if not request_data.admin_id or not request_data.telegram_id:
        logger.warning(
            section=LogSection.API,
            subsection=LogSubsection.API.VALIDATION,
            message=f"Некорректные данные запроса с IP {ip} - отсутствует admin_id или telegram_id"
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Отсутствуют обязательные поля"}
        )
    
    # Проверяем, есть ли уже активный запрос для этого админа
    existing_request = await db.twofa_requests.find_one({
        "admin_id": request_data.admin_id,
        "status": "pending",
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if existing_request:
        logger.warning(
            section=LogSection.TWO_FA,
            subsection=LogSubsection.TWO_FA.REQUEST_FAILED,
            message=f"Попытка создать дублирующий 2FA запрос для администратора {request_data.admin_name} с IP {ip}"
        )
        raise HTTPException(
            status_code=409,
            detail={"message": "Уже есть активный 2FA запрос для этого администратора"}
        )
    
    # Подготавливаем данные для отправки
    admin_data = {
        "admin_id": request_data.admin_id,
        "admin_name": request_data.admin_name,
        "admin_email": request_data.admin_email,
        "telegram_id": request_data.telegram_id
    }
    
    # Отправляем 2FA запрос
    result = await send_2fa_request(admin_data, request_data.ip_address, request_data.user_agent)
    
    if result["success"]:
        logger.info(
            section=LogSection.API,
            subsection=LogSubsection.API.RESPONSE,
            message=f"2FA запрос успешно отправлен для администратора {request_data.admin_name} с IP {ip}"
        )
        
        return TwoFAResponse(
            success=True,
            message=result["message"],
            request_id=result["request_id"],
            expires_at=result["expires_at"]
        )
    else:
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Ошибка отправки 2FA запроса для администратора {request_data.admin_name} с IP {ip}: {result['message']}"
        )
        
        raise HTTPException(
            status_code=500,
            detail={"message": result["message"]}
        )


@router.get("/status/{request_id}", response_model=TwoFAStatus)
async def get_2fa_status(request_id: str, db=Depends(get_database)):
    """Получение статуса 2FA запроса"""
    try:
        from bson import ObjectId
        request_obj_id = ObjectId(request_id)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный ID запроса"}
        )
    
    request = await db.twofa_requests.find_one({"_id": request_obj_id})
    
    if not request:
        raise HTTPException(
            status_code=404,
            detail={"message": "Запрос не найден"}
        )
    
    return TwoFAStatus(
        request_id=str(request["_id"]),
        status=request["status"],
        admin_id=str(request["admin_id"]),
        created_at=request["created_at"],
        expires_at=request["expires_at"],
        ip_address=request["ip"],
        user_agent=request["user_agent"]
    )


@router.post("/cleanup")
async def cleanup_endpoint():
    """Ручная очистка истекших запросов"""
    try:
        await cleanup_expired_requests()
        return {"message": "Очистка завершена"}
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.MAINTENANCE,
            message=f"Ошибка при ручной очистке: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail={"message": f"Ошибка очистки: {str(e)}"}
        ) 