from fastapi import APIRouter, Depends, HTTPException, Request, Query
from datetime import datetime
from bson import ObjectId

from app.core.security import get_current_actor
from app.db.database import db
from app.logging import get_logger, LogSection, LogSubsection
from app.rate_limit import rate_limit_ip
from app.multiplayer.lobby_utils import (
    get_user_id, 
    get_lobby_from_db, 
    get_user_subscription_from_db,
    MAX_LOBBY_LIFETIME, 
    EXAM_TIMER_DURATION
)
from app.core.response import success

router = APIRouter()
logger = get_logger(__name__)

@router.get("/lobbies/{lobby_id}", summary="Получить информацию о лобби")
@rate_limit_ip("lobby_info", max_requests=40, window_seconds=60)
async def get_lobby(
    lobby_id: str,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Получает информацию о лобби по его ID напрямую из базы данных.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Запрос информации о лобби: пользователь {user_id} запрашивает данные лобби {lobby_id}"
    )
    
    try:
        lobby = await get_lobby_from_db(lobby_id)
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Новая проверка: если пользователь в blacklisted_users, отказать
        if user_id in lobby.get("blacklisted_users", []):
            raise HTTPException(status_code=403, detail="Вы были исключены из лобби")
        
        is_host = user_id == lobby.get("host_id")
        
        host_subscription = await get_user_subscription_from_db(lobby["host_id"])
        host_subscription_type = host_subscription["subscription_type"] if host_subscription else "Demo"
        
        remaining_seconds = 0
        if lobby["status"] in ["waiting", "in_progress"] and lobby.get("created_at"):
            lobby_age = (datetime.utcnow() - lobby["created_at"]).total_seconds()
            remaining_seconds = max(0, MAX_LOBBY_LIFETIME - lobby_age)
            
        host_user = await db.users.find_one({"_id": ObjectId(lobby["host_id"])})
        host_name = host_user.get("full_name", "Неизвестный") if host_user else "Неизвестный"
        
        response_data = {
            "id": str(lobby["_id"]),
            "host_id": lobby["host_id"],
            "host_name": host_name,
            "is_host": is_host,
            "current_user_id": user_id,
            "status": lobby["status"],
            "participants": lobby.get("participants", []),
            "participants_count": len(lobby.get("participants", [])),
            "created_at": lobby["created_at"].isoformat(),
            "mode": lobby["mode"],
            "categories": lobby.get("categories", []),
            "sections": lobby.get("sections", []),
            "exam_mode": lobby.get("exam_mode", False),
            "question_ids": lobby.get("question_ids", []),
            "questions_count": lobby.get("questions_count", 0),
            "remaining_seconds": int(remaining_seconds),
            "max_participants": lobby.get("max_participants", 8),
            "host_subscription_type": host_subscription_type
        }
        
        if is_host:
            response_data["participants_answers"] = lobby.get("participants_answers", {})
            response_data["participants_raw_answers"] = lobby.get("participants_raw_answers", {})
        else:
            response_data["user_answers"] = lobby.get("participants_answers", {}).get(user_id, {})
        
        response_data["current_index"] = lobby.get("current_index", 0)
        
        if lobby.get("exam_mode", False):
            current_time = datetime.utcnow()
            expires_at = lobby.get("exam_timer_expires_at")
            if expires_at:
                exam_time_left = max(0, int((expires_at - current_time).total_seconds()))
                response_data["exam_timer"] = {
                    "time_left": exam_time_left,
                    "expires_at": expires_at.isoformat(),
                    "duration": lobby.get("exam_timer_duration", EXAM_TIMER_DURATION)
                }
            else:
                response_data["exam_timer"] = {
                    "time_left": EXAM_TIMER_DURATION,
                    "duration": EXAM_TIMER_DURATION
                }
        
        return success(data=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения информации о лобби: {lobby_id}, {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера") 

@router.get("/lobbies/{lobby_id}/public", summary="Получить публичную информацию о лобби")
@rate_limit_ip("lobby_public_info", max_requests=30, window_seconds=60)
async def get_lobby_public_info(lobby_id: str, request: Request = None):
    """
    Получает публичную информацию о лобби для страницы присоединения.
    Не требует аутентификации.
    """
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        host_user = await db.users.find_one({"_id": ObjectId(lobby["host_id"])})
        if not host_user:
            raise HTTPException(status_code=404, detail="Хост лобби не найден")
        
        host_subscription = await get_user_subscription_from_db(lobby["host_id"])
        host_subscription_type = host_subscription.get("subscription_type", "Demo") if host_subscription else "Demo"
        
        remaining_seconds = 0
        if lobby["status"] in ["waiting", "in_progress"] and lobby.get("created_at"):
            lobby_age = (datetime.utcnow() - lobby["created_at"]).total_seconds()
            remaining_seconds = max(0, MAX_LOBBY_LIFETIME - lobby_age)
        
        return success(data={
            "lobby_id": lobby_id,
            "status": lobby["status"],
            "mode": lobby.get("mode", "solo"),
            "categories": lobby.get("categories", []),
            "questions_count": lobby.get("questions_count", 40),
            "max_participants": lobby.get("max_participants", 8),
            "participants_count": len(lobby.get("participants", [])),
            "host_name": host_user.get("full_name", "Unknown"),
            "host_subscription_type": host_subscription_type,
            "allows_guests": host_subscription_type.lower() == "school",
            "created_at": lobby.get("created_at").isoformat() if lobby.get("created_at") and isinstance(lobby.get("created_at"), datetime) else str(lobby.get("created_at", "")),
            "remaining_seconds": int(remaining_seconds)
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения публичной информации: лобби {lobby_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при получении информации о лобби") 