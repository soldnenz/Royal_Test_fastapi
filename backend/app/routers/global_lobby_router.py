from fastapi import APIRouter, HTTPException, Depends, Request, Query
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

# Настройка логгера
logger = get_logger(__name__)

# Создаем роутер
router = APIRouter()

# Maximum time a lobby can be active (4 hours in seconds)
MAX_LOBBY_LIFETIME = 4 * 60 * 60

# Exam mode timer (40 minutes in seconds)
EXAM_TIMER_DURATION = 40 * 60

class LobbyCreate(BaseModel):
    categories: List[str] = None
    pdd_section_uids: Optional[List[str]] = None
    questions_count: int = 40
    exam_mode: bool = False

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
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SUBSCRIPTION,
            message=f"Ошибка получения подписки: пользователь {user_id}, ошибка {str(e)}"
        )
        return None

@router.post("/lobbies", summary="Создать новое лобби")
@rate_limit_ip("lobby_create", max_requests=10, window_seconds=300)
async def create_lobby(
    lobby_data: LobbyCreate,
    request: Request = None, 
    current_user: dict = Depends(get_current_actor)
):
    user_id = get_user_id(current_user)
    mode = "solo"
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.CREATION,
        message=f"Запрос создания лобби: пользователь {user_id} создаёт {mode}-лобби на {lobby_data.questions_count} вопросов"
    )
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.CREATION,
        message=f"Параметры лобби: разделы ПДД {lobby_data.pdd_section_uids}, категории {lobby_data.categories}, экзамен {lobby_data.exam_mode}"
    )
    
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
                    logger.info(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.LIFECYCLE,
                        message=f"Автозавершение просроченного лобби: лобби {active_lobby['_id']} пользователя {user_id} закрыто по таймауту {MAX_LOBBY_LIFETIME} секунд"
                    )
                else:
                    logger.warning(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.SECURITY,
                        message=f"Блокировка создания лобби: пользователь {user_id} имеет активное лобби {active_lobby['_id']}, осталось {MAX_LOBBY_LIFETIME - lobby_age:.0f} секунд"
                    )
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
                logger.warning(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.SECURITY,
                    message=f"Блокировка создания лобби: пользователь {user_id} имеет активное лобби {active_lobby['_id']} без времени создания"
                )
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "message": "У вас уже есть активный тест. Завершите его перед началом нового.",
                        "active_lobby_id": active_lobby["_id"]
                    }
                )
        
        if not subscription:
            subscription_type = "Demo"
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SUBSCRIPTION,
                message=f"Подписка не найдена: пользователь {user_id} работает в Demo-режиме"
            )
        else:
            subscription_type = subscription["subscription_type"]
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SUBSCRIPTION,
                message=f"Подписка найдена: пользователь {user_id} имеет подписку {subscription_type}"
            )
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Проверка разделов ПДД: разделы {lobby_data.pdd_section_uids}, количество {len(lobby_data.pdd_section_uids) if lobby_data.pdd_section_uids else 0}, подписка {subscription_type}"
        )
        
        # Обрабатываем разделы ПДД (доступно для VIP, Royal и School)
        if lobby_data.pdd_section_uids is not None and len(lobby_data.pdd_section_uids) > 0 and subscription_type.lower() not in ["vip", "royal", "school"]:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Отказ в выборе разделов ПДД: пользователь {user_id} с подпиской {subscription_type} не может выбирать разделы, требуется VIP/Royal/School"
            )
            raise HTTPException(
                status_code=403,
                detail="Выбор разделов ПДД доступен только для подписок VIP, Royal и School"
            )
        
        # Ограничения по категориям в зависимости от подписки
        if subscription_type in ["Economy", "Demo"]:
            allowed_categories = ["A1", "A", "B1", "B", "BE"]
            if lobby_data.categories and not all(cat in allowed_categories for cat in lobby_data.categories):
                logger.warning(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.SECURITY,
                    message=f"Отказ в выборе категорий: пользователь {user_id} с подпиской {subscription_type} пытался выбрать {lobby_data.categories}, разрешены {allowed_categories}"
                )
                raise HTTPException(status_code=403, detail="Ваша подписка не даёт доступа к выбранным категориям")
            
            lobby_data.pdd_section_uids = None
            
            if lobby_data.categories and any(cat in ["A1", "A", "B1"] for cat in lobby_data.categories):
                category_group = ["A1", "A", "B1"]
            else:
                category_group = ["B", "BE"]
            
            lobby_data.categories = category_group
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.VALIDATION,
                message=f"Автоматический выбор категорий: для подписки {subscription_type} установлены категории {lobby_data.categories}"
            )
            
        elif subscription_type == "Vip":
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.VALIDATION,
                message=f"VIP подписка: пользователь {user_id} получил доступ ко всем категориям и разделам ПДД"
            )
            
        # Построение фильтра для запроса вопросов
        query = {"deleted": False}
        
        if lobby_data.categories:
            query["categories"] = {"$in": lobby_data.categories}
            
        if lobby_data.pdd_section_uids and subscription_type.lower() in ["vip", "royal", "school"]:
            query["pdd_section_uids"] = {"$in": lobby_data.pdd_section_uids}
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Фильтр для поиска вопросов: {query}"
        )
        
        # Выбор случайных вопросов из коллекции вопросов
        total_questions = await db.questions.count_documents(query)
        if total_questions == 0:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Вопросы не найдены: для фильтра {query} не найдено ни одного вопроса"
            )
            raise HTTPException(
                status_code=404, 
                detail="Не найдено вопросов для выбранных категорий и разделов"
            )
        
        questions_count = min(questions_count, total_questions)
        questions_count = min(questions_count, 40)
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Выборка вопросов: будет выбрано {questions_count} вопросов из {total_questions} доступных"
        )
        
        # Получаем случайную выборку вопросов из БД
        questions_cursor = db.questions.aggregate([
            {"$match": query}, 
            {"$sample": {"size": questions_count}}
        ])
        questions = await questions_cursor.to_list(length=questions_count)
        question_ids = [str(q["_id"]) for q in questions]
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Вопросы успешно выбраны: получено {len(question_ids)} вопросов для лобби"
        )
        
        # Составляем словарь правильных ответов для выбранных вопросов
        correct_answers_map = {}
        questions_data = {}
        
        for q in questions:
            # Конвертируем букву в индекс (A=0, B=1, C=2, D=3)
            correct_answer_raw = q.get("correct_label", "A")  # Используем correct_label!
            if isinstance(correct_answer_raw, str):
                correct_index = ord(correct_answer_raw.upper()) - ord('A')
            else:
                correct_index = correct_answer_raw if correct_answer_raw is not None else 0
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
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.CREATION,
            message=f"ID лобби сгенерирован: создано уникальное лобби {lobby_id}"
        )
        
        initial_status = "in_progress"
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.LIFECYCLE,
            message=f"Статус лобби установлен: лобби {lobby_id} получило статус {initial_status} для режима {mode}"
        )
        
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
            "participants_answers": {user_id: {}},  # для хранения правильности ответов (true/false)
            "participants_raw_answers": {user_id: {}},  # для хранения индексов выбранных ответов
            "current_index": 0,
            "created_at": current_time,
            "sections": lobby_data.pdd_section_uids or [],
            "categories": lobby_data.categories or [],
            "mode": mode,
            "subscription_type": subscription_type,
            "exam_mode": lobby_data.exam_mode,
            "max_participants": 1,
            "questions_count": questions_count
        }
        
        # Добавляем таймер экзамена, если включен режим экзамена
        if lobby_data.exam_mode:
            lobby_doc["exam_timer_duration"] = EXAM_TIMER_DURATION
            lobby_doc["exam_timer_expires_at"] = current_time + timedelta(seconds=EXAM_TIMER_DURATION)
            lobby_doc["exam_timer_started_at"] = current_time
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.EXAM,
                message=f"Таймер экзамена установлен: лобби {lobby_id} получило таймер на {EXAM_TIMER_DURATION} секунд до {lobby_doc['exam_timer_expires_at']}"
            )
        
        try:
            await db.lobbies.insert_one(lobby_doc)
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.DATABASE,
                message=f"Лобби сохранено в БД: лобби {lobby_id} успешно создано с {questions_count} вопросами в режиме {mode}"
            )
        

            response_data = {
                "lobby_id": lobby_id, 
                "status": initial_status, 
                "questions_count": questions_count,
                "categories": lobby_data.categories,
                "sections": lobby_data.pdd_section_uids,
                "auto_started": True,
                "exam_mode": lobby_data.exam_mode
            }
            
            # Добавляем информацию о таймере экзамена
            if lobby_data.exam_mode:
                response_data["exam_timer_duration"] = EXAM_TIMER_DURATION
                response_data["exam_timer_expires_at"] = lobby_doc["exam_timer_expires_at"].isoformat()
            
            return success(data=response_data)
        except Exception as e:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.DATABASE,
                message=f"Ошибка сохранения лобби: лобби {lobby_id}, ошибка {str(e)}"
            )
            raise HTTPException(status_code=500, detail=f"Ошибка при создании лобби: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Критическая ошибка создания лобби: пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get("/active-lobby", summary="Получить информацию об активном лобби пользователя")
@rate_limit_ip("lobby_active_get", max_requests=30, window_seconds=60)
async def get_user_active_lobby(request: Request, current_user: dict = Depends(get_current_actor)):
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Проверка активного лобби: пользователь {user_id} запрашивает информацию об активном лобби"
    )
    
    try:
        active_lobby = await db.lobbies.find_one({
            "participants": user_id,
            "status": {"$nin": ["finished", "closed"]}
        })
        
        if not active_lobby:
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Активное лобби не найдено: у пользователя {user_id} нет активных лобби"
            )
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
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.LIFECYCLE,
                    message=f"Автозакрытие просроченного лобби: лобби {active_lobby['_id']} пользователя {user_id} закрыто из-за превышения {MAX_LOBBY_LIFETIME} секунд"
                )
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
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка проверки активного лобби: пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при проверке активного лобби")

@router.get("/categories/stats", summary="Получить статистику по категориям и количеству вопросов")
@rate_limit_ip("categories_stats", max_requests=20, window_seconds=60)
async def get_categories_stats(request: Request, current_user: dict = Depends(get_current_actor)):
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.STATS,
        message=f"Запрос статистики категорий: пользователь {user_id} запрашивает статистику по категориям вопросов"
    )
    
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
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.STATS,
            message=f"Статистика категорий получена: {categories_dict}, общее количество вопросов {total_questions}"
        )
        
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
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения статистики категорий: пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}") 