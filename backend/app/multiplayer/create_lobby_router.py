from fastapi import APIRouter, HTTPException, Depends, Request
from app.db.database import db
from app.utils.id_generator import generate_unique_lobby_id
from datetime import datetime, timedelta
from app.core.security import get_current_actor
from app.core.response import success
from bson import ObjectId
from pydantic import BaseModel
from app.logging import get_logger, LogSection, LogSubsection
import asyncio
from typing import Optional, List
from app.rate_limit import rate_limit_ip
from app.multiplayer.ws_utils import create_ws_token

logger = get_logger(__name__)
router = APIRouter()

MAX_LOBBY_LIFETIME = 4 * 60 * 60
EXAM_TIMER_DURATION = 40 * 60

class LobbyCreate(BaseModel):
    categories: List[str] = None
    pdd_section_uids: Optional[List[str]] = None
    questions_count: int = 40
    exam_mode: bool = False
    max_participants: int = 8

def get_user_id(current_user):
    return str(current_user["id"])

async def get_user_subscription(user_id: str):
    if not user_id or user_id.startswith("guest_"):
        return None
    try:
        return await db.subscriptions.find_one({
            "user_id": ObjectId(user_id),
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })
    except Exception as e:
        logger.error(f"Ошибка получения подписки для {user_id}: {e}")
        return None

@router.post("/lobbies", summary="Создать новое мультиплеерное лобби")
@rate_limit_ip("lobby_create_multiplayer", max_requests=10, window_seconds=300)
async def create_multiplayer_lobby(
    lobby_data: LobbyCreate,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    user_id = get_user_id(current_user)
    
    try:
        # Проверка активных тестов и подписки
        active_lobby_task = db.lobbies.find_one({"participants": user_id, "status": {"$ne": "finished"}})
        subscription_task = get_user_subscription(user_id)
        active_lobby, subscription = await asyncio.gather(active_lobby_task, subscription_task)

        if active_lobby:
            raise HTTPException(status_code=400, detail="У вас уже есть активный тест.")

        subscription_type = subscription["subscription_type"] if subscription else "Demo"
        
        # Для мультиплеера нужна подписка Royal или School
        if subscription_type.lower() not in ["royal", "school"]:
            raise HTTPException(status_code=403, detail="Для создания многопользовательского лобби требуется подписка Royal или School")

        # Выбор вопросов
        query = {"deleted": False}
        if lobby_data.categories:
            query["categories"] = {"$in": lobby_data.categories}
        if lobby_data.pdd_section_uids and subscription_type.lower() in ["vip", "royal", "school"]:
            query["pdd_section_uids"] = {"$in": lobby_data.pdd_section_uids}

        total_questions = await db.questions.count_documents(query)
        if total_questions == 0:
            raise HTTPException(status_code=404, detail="Не найдено вопросов для выбранных категорий.")
        
        questions_count = min(lobby_data.questions_count, total_questions, 40)
        questions_cursor = db.questions.aggregate([{"$match": query}, {"$sample": {"size": questions_count}}])
        questions = await questions_cursor.to_list(length=questions_count)
        question_ids = [str(q["_id"]) for q in questions]

        correct_answers_map = {str(q["_id"]): ord(q.get("correct_label", "A").upper()) - ord('A') for q in questions}

        # Создание документа лобби
        lobby_id = await generate_unique_lobby_id()
        current_time = datetime.utcnow()
        lobby_doc = {
            "_id": lobby_id,
            "host_id": user_id,
            "status": "waiting", # Мультиплеерные лобби всегда начинают в статусе waiting
            "mode": "multiplayer",
            "question_ids": question_ids,
            "correct_answers": correct_answers_map,
            "participants": [user_id],
            "participants_answers": {user_id: {}},
            "current_index": 0,
            "created_at": current_time,
            "subscription_type": subscription_type.lower(),
            "exam_mode": lobby_data.exam_mode,
            "max_participants": lobby_data.max_participants,
            "questions_count": questions_count,
            "categories": lobby_data.categories or [],
            "sections": lobby_data.pdd_section_uids or [],
        }

        if lobby_data.exam_mode:
            lobby_doc["exam_timer_duration"] = EXAM_TIMER_DURATION
            lobby_doc["exam_timer_expires_at"] = current_time + timedelta(seconds=EXAM_TIMER_DURATION)

        await db.lobbies.insert_one(lobby_doc)
        
        # Создание WS токена
        ws_token = await create_ws_token(current_user, lobby_id)

        return success(data={
            "lobby_id": lobby_id, 
            "status": "waiting", 
            "ws_token": ws_token
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка создания мультиплеерного лобби: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера") 