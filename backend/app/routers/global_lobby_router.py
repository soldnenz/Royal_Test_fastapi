from fastapi import APIRouter, HTTPException, Depends, Request, Query
from app.db.database import db
from app.utils.id_generator import generate_unique_lobby_id
from datetime import datetime, timedelta
from app.core.security import get_current_actor
from app.core.response import success
from app.websocket.lobby_ws import ws_manager
from bson import ObjectId
from pydantic import BaseModel
import logging
import asyncio
from typing import Optional, List

# Настройка логгера
logger = logging.getLogger(__name__)

# Создаем роутер
router = APIRouter(prefix="/global-lobby", tags=["Global Lobby"])

# Maximum time a lobby can be active (4 hours in seconds)
MAX_LOBBY_LIFETIME = 4 * 60 * 60

# Exam mode timer (40 minutes in seconds)
EXAM_TIMER_DURATION = 40 * 60

class LobbyCreate(BaseModel):
    mode: str = "solo"
    categories: List[str] = None
    pdd_section_uids: Optional[List[str]] = None
    questions_count: int = 40
    exam_mode: bool = False
    max_participants: int = 8

def get_user_id(current_user):
    """
    Извлекает ID пользователя из объекта, возвращаемого get_current_actor
    Поддерживает как обычных пользователей, так и гостей
    """
    user_id = current_user["id"]
    # Для гостей ID уже строка, для обычных пользователей - ObjectId
    if isinstance(user_id, str):
        return user_id
    return str(user_id)

async def get_user_subscription(user_id: str):
    """Получить подписку пользователя без кэширования"""
    if not user_id or (isinstance(user_id, str) and user_id.startswith("guest_")):
        return None
    
    try:
        subscription = await db.subscriptions.find_one({
            "user_id": ObjectId(user_id),
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        return subscription
    except Exception as e:
        logger.error(f"Ошибка при получении подписки для пользователя {user_id}: {str(e)}")
        return None

@router.post("/lobbies", summary="Создать новое лобби")
async def create_lobby(
    lobby_data: LobbyCreate,
    request: Request = None, 
    current_user: dict = Depends(get_current_actor)
):
    user_id = get_user_id(current_user)
    logger.info(f"Запрос на создание лобби от пользователя: {user_id}, режим: {lobby_data.mode}")
    logger.info(f"Данные лобби: pdd_section_uids={lobby_data.pdd_section_uids}, categories={lobby_data.categories}")
    
    try:
        questions_count = lobby_data.questions_count
        
        # Проверка активных тестов пользователя и получение подписки параллельно
        active_lobby_task = db.lobbies.find_one({
            "participants": user_id,
            "status": {"$ne": "finished"}
        })
        subscription_task = get_user_subscription(user_id)
        
        active_lobby, subscription = await asyncio.gather(active_lobby_task, subscription_task)
        
        if active_lobby:
            if active_lobby.get("created_at"):
                lobby_age = (datetime.utcnow() - active_lobby["created_at"]).total_seconds()
                if lobby_age > MAX_LOBBY_LIFETIME:
                    await db.lobbies.update_one(
                        {"_id": active_lobby["_id"]},
                        {"$set": {
                            "status": "finished",
                            "finished_at": datetime.utcnow(),
                            "auto_finished": True
                        }}
                    )
                    logger.info(f"Автоматически завершен просроченный тест {active_lobby['_id']} для пользователя {user_id}")
                else:
                    logger.warning(f"Пользователь {user_id} уже имеет активный тест: {active_lobby['_id']}")
                    remaining_seconds = MAX_LOBBY_LIFETIME - lobby_age
                    raise HTTPException(
                        status_code=400, 
                        detail={
                            "message": "У вас уже есть активный тест. Завершите его перед началом нового.",
                            "active_lobby_id": active_lobby["_id"],
                            "remaining_seconds": int(remaining_seconds)
                        }
                    )
            else:
                logger.warning(f"Пользователь {user_id} уже имеет активный тест: {active_lobby['_id']}")
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "message": "У вас уже есть активный тест. Завершите его перед началом нового.",
                        "active_lobby_id": active_lobby["_id"]
                    }
                )
        
        if not subscription:
            subscription_type = "Demo"
            logger.info(f"Пользователь {user_id} без подписки, установлен demo-режим")
        else:
            subscription_type = subscription["subscription_type"]
            logger.info(f"Пользователь {user_id} с подпиской: {subscription_type}")
        
        logger.info(f"Проверка разделов ПДД: pdd_section_uids={lobby_data.pdd_section_uids}, len={len(lobby_data.pdd_section_uids) if lobby_data.pdd_section_uids else 'None'}, subscription_type={subscription_type}")
        
        # Проверка прав на создание лобби
        if lobby_data.mode == "multi" and subscription_type not in ["Royal", "School"]:
            logger.warning(f"Отказ в создании multi-лобби пользователю {user_id} с подпиской {subscription_type}")
            raise HTTPException(
                status_code=403, 
                detail="Для создания многопользовательского лобби требуется подписка Royal или School"
            )
        
        # Обрабатываем разделы ПДД (доступно для VIP, Royal и School)
        if lobby_data.pdd_section_uids is not None and len(lobby_data.pdd_section_uids) > 0 and subscription_type.lower() not in ["vip", "royal", "school"]:
            logger.warning(f"Отказ в выборе разделов ПДД пользователю {user_id} с подпиской {subscription_type}")
            raise HTTPException(
                status_code=403,
                detail="Выбор разделов ПДД доступен только для подписок VIP, Royal и School"
            )
        
        # Ограничения по категориям в зависимости от подписки
        if subscription_type in ["Economy", "Demo"]:
            allowed_categories = ["A1", "A", "B1", "B", "BE"]
            if lobby_data.categories and not all(cat in allowed_categories for cat in lobby_data.categories):
                logger.warning(f"Отказ в выборе категории пользователю {user_id} с подпиской Economy")
                raise HTTPException(status_code=403, detail="Ваша подписка не даёт доступа к выбранным категориям")
            
            lobby_data.pdd_section_uids = None
            
            if lobby_data.categories and any(cat in ["A1", "A", "B1"] for cat in lobby_data.categories):
                category_group = ["A1", "A", "B1"]
            else:
                category_group = ["B", "BE"]
            
            lobby_data.categories = category_group
            logger.info(f"Установлены категории для {subscription_type}: {lobby_data.categories}")
            
        elif subscription_type == "Vip":
            logger.info(f"VIP подписка, разрешены все категории и разделы ПДД")
            
        # Построение фильтра для запроса вопросов
        query = {"deleted": False}
        
        if lobby_data.categories:
            query["categories"] = {"$in": lobby_data.categories}
            
        if lobby_data.pdd_section_uids and subscription_type.lower() in ["vip", "royal", "school"]:
            query["pdd_section_uids"] = {"$in": lobby_data.pdd_section_uids}
        
        logger.info(f"Фильтр для вопросов: {query}")
        
        # Выбор случайных вопросов из коллекции вопросов
        total_questions = await db.questions.count_documents(query)
        if total_questions == 0:
            logger.error(f"Не найдено вопросов для фильтра: {query}")
            raise HTTPException(
                status_code=404, 
                detail="Не найдено вопросов для выбранных категорий и разделов"
            )
        
        questions_count = min(questions_count, total_questions)
        questions_count = min(questions_count, 40)
        
        logger.info(f"Будет выбрано {questions_count} вопросов из {total_questions} доступных")
        
        # Получаем случайную выборку вопросов из БД
        questions_cursor = db.questions.aggregate([
            {"$match": query}, 
            {"$sample": {"size": questions_count}}
        ])
        questions = await questions_cursor.to_list(length=questions_count)
        question_ids = [str(q["_id"]) for q in questions]
        
        logger.info(f"Выбрано {len(question_ids)} вопросов")
        
        # Составляем словарь правильных ответов для выбранных вопросов
        correct_answers_map = {}
        questions_data = {}
        
        for q in questions:
            correct_label = q["correct_label"]
            correct_index = ord(correct_label) - ord('A')
            correct_answers_map[str(q["_id"])] = correct_index
            
            media_filename = q.get("media_filename")
            after_answer_media_filename = q.get("after_answer_media_filename")
            
            is_video = False
            if media_filename and isinstance(media_filename, str):
                is_video = media_filename.lower().endswith((".mp4", ".webm", ".mov"))
            
            is_after_answer_video = False
            if after_answer_media_filename and isinstance(after_answer_media_filename, str):
                is_after_answer_video = after_answer_media_filename.lower().endswith((".mp4", ".webm", ".mov"))
            
            questions_data[str(q["_id"])] = {
                "has_media": q.get("has_media", False),
                "media_type": "video" if is_video else "image",
                "media_file_id": str(q.get("media_file_id", "")),
                "has_after_answer_media": q.get("has_after_answer_media", False),
                "after_answer_media_type": "video" if is_after_answer_video else "image",
                "after_answer_media_id": str(q.get("after_answer_media_file_id", ""))
            }

        # Генерируем уникальный ID лобби
        lobby_id = await generate_unique_lobby_id()
        logger.info(f"Сгенерирован ID лобби: {lobby_id}")
        
        initial_status = "waiting" if lobby_data.mode in ["multi", "multiplayer"] else "in_progress"
        logger.info(f"Установлен начальный статус лобби: {initial_status}")
        
        # Подготавливаем данные лобби
        current_time = datetime.utcnow()
        lobby_doc = {
            "_id": lobby_id,
            "host_id": user_id,
            "status": initial_status,
            "question_ids": question_ids,
            "correct_answers": correct_answers_map,
            "questions_data": questions_data,
            "participants": [user_id],
            "participants_answers": {user_id: {}},
            "current_index": 0,
            "created_at": current_time,
            "sections": lobby_data.pdd_section_uids or [],
            "categories": lobby_data.categories or [],
            "mode": lobby_data.mode,
            "subscription_type": subscription_type,
            "exam_mode": lobby_data.exam_mode,
            "max_participants": lobby_data.max_participants,
            "questions_count": questions_count
        }
        
        # Добавляем таймер экзамена, если включен режим экзамена
        if lobby_data.exam_mode:
            lobby_doc["exam_timer_duration"] = EXAM_TIMER_DURATION
            lobby_doc["exam_timer_expires_at"] = current_time + timedelta(seconds=EXAM_TIMER_DURATION)
            lobby_doc["exam_timer_started_at"] = current_time
            logger.info(f"Установлен таймер экзамена на {EXAM_TIMER_DURATION} секунд для лобби {lobby_id}")
        
        try:
            await db.lobbies.insert_one(lobby_doc)
            logger.info(f"Лобби {lobby_id} успешно создано в базе данных")
            
            # Если solo режим, отправляем WebSocket сообщение о начале теста
            if lobby_data.mode not in ["multi", "multiplayer"]:
                first_question_id = question_ids[0] if question_ids else None
                if first_question_id:
                    try:
                        logger.info(f"Отправка WS-сообщения start, вопрос: {first_question_id} для solo режима")
                        await ws_manager.send_json(lobby_id, {
                            "type": "start",
                            "data": {"question_id": first_question_id}
                        })
                    except Exception as e:
                        logger.error(f"Ошибка при отправке WebSocket сообщения: {str(e)}")
            
            response_data = {
                "lobby_id": lobby_id, 
                "status": initial_status, 
                "questions_count": questions_count,
                "categories": lobby_data.categories,
                "sections": lobby_data.pdd_section_uids,
                "auto_started": lobby_data.mode not in ["multi", "multiplayer"],
                "exam_mode": lobby_data.exam_mode
            }
            
            if lobby_data.exam_mode:
                response_data["exam_timer_duration"] = EXAM_TIMER_DURATION
                response_data["exam_timer_expires_at"] = lobby_doc["exam_timer_expires_at"].isoformat()
            
            return success(data=response_data)
        except Exception as e:
            logger.error(f"Ошибка при создании лобби: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при создании лобби: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при создании лобби: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get("/active-lobby", summary="Получить информацию об активном лобби пользователя")
async def get_user_active_lobby(current_user: dict = Depends(get_current_actor)):
    user_id = get_user_id(current_user)
    logger.info(f"Проверка активного лобби для пользователя {user_id}")
    
    try:
        active_lobby = await db.lobbies.find_one({
            "participants": user_id,
            "status": {"$nin": ["finished", "closed"]}
        })
        
        if not active_lobby:
            logger.info(f"У пользователя {user_id} нет активных лобби")
            return success(data={"has_active_lobby": False})
        
        if active_lobby.get("created_at"):
            lobby_age = (datetime.utcnow() - active_lobby["created_at"]).total_seconds()
            if lobby_age > MAX_LOBBY_LIFETIME:
                await db.lobbies.update_one(
                    {"_id": active_lobby["_id"]},
                    {"$set": {
                        "status": "finished",
                        "finished_at": datetime.utcnow(),
                        "auto_finished": True
                    }}
                )
                logger.info(f"Автоматически завершено просроченное лобби {active_lobby['_id']}")
                return success(data={"has_active_lobby": False})
            
            remaining_seconds = MAX_LOBBY_LIFETIME - lobby_age
            
            host_user = await db.users.find_one({"_id": ObjectId(active_lobby["host_id"])})
            host_name = host_user.get("full_name", "Неизвестный пользователь") if host_user else "Неизвестный пользователь"
            
            return success(data={
                "has_active_lobby": True,
                "lobby_id": active_lobby["_id"],
                "mode": active_lobby.get("mode", "solo"),
                "status": active_lobby.get("status"),
                "created_at": active_lobby["created_at"].isoformat() if isinstance(active_lobby["created_at"], datetime) else str(active_lobby["created_at"]),
                "host_name": host_name,
                "is_host": active_lobby["host_id"] == user_id,
                "remaining_seconds": int(remaining_seconds),
                "exam_mode": active_lobby.get("exam_mode", False)
            })
        
        return success(data={
            "has_active_lobby": True,
            "lobby_id": active_lobby["_id"],
            "mode": active_lobby.get("mode", "solo"),
            "status": active_lobby.get("status")
        })
    except Exception as e:
        logger.error(f"Ошибка при проверке активного лобби: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при проверке активного лобби")

@router.get("/categories/stats", summary="Получить статистику по категориям и количеству вопросов")
async def get_categories_stats(current_user: dict = Depends(get_current_actor)):
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} запрашивает статистику по категориям")
    
    try:
        pipeline = [
            {"$match": {"deleted": False}},
            {"$unwind": "$categories"},
            {"$group": {
                "_id": "$categories",
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        category_stats = await db.questions.aggregate(pipeline).to_list(None)
        total_questions = await db.questions.count_documents({"deleted": False})
        
        categories_dict = {}
        for stat in category_stats:
            categories_dict[stat["_id"]] = stat["count"]
        
        logger.info(f"Статистика по категориям: {categories_dict}, общее количество: {total_questions}")
        
        category_groups = [
            {
                "id": "cat1",
                "categories": ["A1", "A", "B1"],
                "title": "A1, A, B1"
            },
            {
                "id": "cat2", 
                "categories": ["B", "BE"],
                "title": "B, BE"
            },
            {
                "id": "cat3",
                "categories": ["C", "C1"], 
                "title": "C, C1"
            },
            {
                "id": "cat4",
                "categories": ["BC1"],
                "title": "BC1"
            },
            {
                "id": "cat5",
                "categories": ["D1", "D", "Tb"],
                "title": "D1, D, Tb"
            },
            {
                "id": "cat6",
                "categories": ["C1", "CE", "D1", "DE"],
                "title": "C1, CE, D1, DE"
            },
            {
                "id": "cat7",
                "categories": ["Tm"],
                "title": "Tm"
            }
        ]
        
        grouped_categories = []
        for group in category_groups:
            unique_questions_count = await db.questions.count_documents({
                "deleted": False,
                "categories": {"$in": group["categories"]}
            })
            
            breakdown = {}
            for cat in group["categories"]:
                breakdown[cat] = categories_dict.get(cat, 0)
            
            grouped_categories.append({
                "id": group["id"],
                "categories": group["categories"],
                "title": group["title"], 
                "total_questions": unique_questions_count,
                "breakdown": breakdown
            })
        
        return success(data={
            "categories": grouped_categories,
            "total_questions": total_questions,
            "individual_categories": categories_dict
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики категорий: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# Добавляем новый эндпоинт для получения информации о лобби
@router.get("/lobbies/{lobby_id}", summary="Получить информацию о лобби")
async def get_lobby_info(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor),
    t: str = Query(None, description="Timestamp for cache busting"),
    retry: str = Query(None, description="Retry flag for cache refresh")
):
    """
    Получает информацию о лобби по его ID.
    """
    user_id = get_user_id(current_user)
    logger.info(f"Запрос информации о лобби {lobby_id} от пользователя {user_id}")
    
    try:
        # Получаем лобби напрямую из БД (без кэша)
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        is_host = user_id == lobby.get("host_id")
        
        # Получаем тип подписки хоста
        host_subscription = await get_user_subscription(lobby["host_id"])
        host_subscription_type = host_subscription["subscription_type"] if host_subscription else "Demo"
        
        # Calculate remaining time if lobby is active
        remaining_seconds = 0
        if lobby["status"] in ["waiting", "in_progress"] and lobby.get("created_at"):
            lobby_age = (datetime.utcnow() - lobby["created_at"]).total_seconds()
            remaining_seconds = max(0, MAX_LOBBY_LIFETIME - lobby_age)
            
            # Логирование для отладки
            logger.info(f"Lobby {lobby_id} time calculation: created_at={lobby['created_at']}, "
                       f"lobby_age={lobby_age:.2f}s, remaining_seconds={remaining_seconds:.2f}s")
        
        # Получаем имя хоста
        host_user = await db.users.find_one({"_id": ObjectId(lobby["host_id"])})
        host_name = host_user.get("full_name", "Неизвестный пользователь") if host_user else "Неизвестный пользователь"
        
        # Формируем ответ
        response_data = {
            "id": str(lobby["_id"]),
            "host_id": lobby["host_id"],
            "host_name": host_name,
            "is_host": is_host,
            "current_user_id": user_id,
            "status": lobby["status"],
            "participants": lobby.get("participants", []),  # Добавляем массив участников
            "participants_count": len(lobby["participants"]),
            "created_at": lobby["created_at"].isoformat() if isinstance(lobby["created_at"], datetime) else str(lobby["created_at"]),
            "mode": lobby["mode"],
            "categories": lobby["categories"],
            "sections": lobby["sections"],
            "exam_mode": lobby.get("exam_mode", False),
            "question_ids": lobby.get("question_ids", []),
            "questions_count": lobby.get("questions_count", len(lobby.get("question_ids", []))),  # Добавляем количество вопросов
            "remaining_seconds": int(remaining_seconds),
            "max_participants": lobby.get("max_participants", 8),  # Добавляем максимальное количество участников
            "host_subscription_type": host_subscription_type  # Добавляем тип подписки хоста
        }
        
        # Добавляем ответы участников для хоста
        if is_host:
            response_data["participants_answers"] = lobby.get("participants_answers", {})
            response_data["participants_raw_answers"] = lobby.get("participants_raw_answers", {})
        else:
            # Для обычных участников добавляем только их собственные ответы
            response_data["user_answers"] = lobby.get("participants_answers", {}).get(user_id, {})
        
        # Добавляем current_index для всех участников (нужно для валидации доступа к вопросам)
        response_data["current_index"] = lobby.get("current_index", 0)
        
        # Добавляем информацию о таймере экзамена
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
        
        logger.info(f"Возвращена информация о лобби {lobby_id}")
        return success(data=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении информации о лобби {lobby_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера") 