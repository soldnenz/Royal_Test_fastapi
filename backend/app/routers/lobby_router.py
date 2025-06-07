# app/routers/lobby.py (фрагмент)
from fastapi import APIRouter, HTTPException, Depends, Request, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.db.database import db  # предположим, db - это подключение к Mongo (AsyncIOMotorDatabase)
from app.utils.id_generator import generate_unique_lobby_id
from datetime import datetime, timedelta
from app.core.security import get_current_actor
from app.core.response import success
from app.websocket.lobby_ws import ws_manager
from bson import ObjectId
import json
from pydantic import BaseModel
import logging
import asyncio
from app.core.gridfs_utils import get_media_file
import base64
from typing import Optional, List, Dict, Any, Union

# Настройка логгера
logger = logging.getLogger(__name__)

# Maximum time a lobby can be active (6 hours in seconds)
MAX_LOBBY_LIFETIME = 6 * 60 * 60

class AnswerSubmit(BaseModel):
    question_id: str
    answer_index: int

class LobbyCreate(BaseModel):
    mode: str = "solo"  # По умолчанию solo
    categories: List[str] = None
    pdd_section_uids: Optional[List[str]] = None
    questions_count: int = 40
    exam_mode: bool = False  # По умолчанию выключен режим экзамена

router = APIRouter()

def get_user_id(current_user):
    """
    Извлекает ID пользователя из объекта, возвращаемого get_current_actor
    """
    return str(current_user["id"])

async def auto_finish_expired_lobbies():
    """
    Background task to check and finish lobbies that have been active for more than 6 hours
    """
    while True:
        try:
            # Find lobbies that are older than 6 hours and still active
            expiration_time = datetime.utcnow() - timedelta(seconds=MAX_LOBBY_LIFETIME)
            expired_lobbies = await db.lobbies.find({
                "status": "in_progress",
                "created_at": {"$lt": expiration_time}
            }).to_list(None)
            
            for lobby in expired_lobbies:
                logger.info(f"Auto-finishing expired lobby {lobby['_id']} (created at {lobby['created_at']})")
                
                # Set the lobby as finished
                await db.lobbies.update_one(
                    {"_id": lobby["_id"]},
                    {"$set": {
                        "status": "finished",
                        "finished_at": datetime.utcnow(),
                        "auto_finished": True
                    }}
                )
                
                # Notify all participants via WebSocket
                try:
                    await ws_manager.send_json(lobby["_id"], {
                        "type": "test_finished",
                        "data": {"auto_finished": True, "reason": "Time limit exceeded (6 hours)"}
                    })
                except Exception as e:
                    logger.error(f"Error sending WebSocket notification: {str(e)}")
            
            # Check every minute
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error in auto_finish_expired_lobbies: {str(e)}")
            await asyncio.sleep(60)  # Still wait before retrying

# Create a function to start background tasks that will be registered in main.py
async def start_background_tasks():
    asyncio.create_task(auto_finish_expired_lobbies())

@router.post("/lobbies", summary="Создать новое лобби")
async def create_lobby(
    lobby_data: LobbyCreate,
    request: Request = None, 
    current_user: dict = Depends(get_current_actor)
):
    """
    Создает новое лобби для прохождения теста с учетом подписки пользователя.
    
    - Всегда используется 40 вопросов
    - School подписка может выбирать разделы ПДД через pdd_section_uids
    - Проверяется наличие активных тестов пользователя
    - В solo режиме тест запускается автоматически
    """
    user_id = get_user_id(current_user)
    logger.info(f"Запрос на создание лобби от пользователя: {user_id}, режим: {lobby_data.mode}")
    
    try:
        # Принудительно установим количество вопросов в 40
        questions_count = 40
        
        # Проверка активных тестов пользователя
        active_lobby = await db.lobbies.find_one({
            "participants": user_id,
            "status": {"$ne": "finished"}
        })
        if active_lobby:
            # Check if the lobby is more than 6 hours old - if so, automatically finish it
            if active_lobby.get("created_at"):
                lobby_age = (datetime.utcnow() - active_lobby["created_at"]).total_seconds()
                if lobby_age > MAX_LOBBY_LIFETIME:
                    # Auto-finish the expired lobby
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
                    # Lobby is still active and not expired
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
                # If created_at is missing for some reason, just report the lobby as active
                logger.warning(f"Пользователь {user_id} уже имеет активный тест: {active_lobby['_id']}")
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "message": "У вас уже есть активный тест. Завершите его перед началом нового.",
                        "active_lobby_id": active_lobby["_id"]
                    }
                )
        
        # Получаем информацию о подписке пользователя
        subscription = await db.subscriptions.find_one({
            "user_id": ObjectId(user_id),
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if not subscription:
            # Демо-режим или бесплатный доступ
            subscription_type = "Demo"
            logger.info(f"Пользователь {user_id} без подписки, установлен demo-режим")
        else:
            subscription_type = subscription["subscription_type"]
            logger.info(f"Пользователь {user_id} с подпиской: {subscription_type}")
        
        # Проверка прав на создание лобби
        if lobby_data.mode == "multi" and subscription_type not in ["Royal", "School"]:
            logger.warning(f"Отказ в создании multi-лобби пользователю {user_id} с подпиской {subscription_type}")
            raise HTTPException(
                status_code=403, 
                detail="Для создания многопользовательского лобби требуется подписка Royal или School"
            )
        
        # Обрабатываем разделы ПДД (доступно для VIP, Royal и School)
        if lobby_data.pdd_section_uids is not None and subscription_type.lower() not in ["vip", "royal", "school"]:
            logger.warning(f"Отказ в выборе разделов ПДД пользователю {user_id} с подпиской {subscription_type}")
            raise HTTPException(
                status_code=403,
                detail="Выбор разделов ПДД доступен только для подписок VIP, Royal и School"
            )
        
        # Ограничения по категориям в зависимости от подписки
        if subscription_type == "Economy":
            allowed_categories = ["A1", "A", "B1", "B", "BE"]
            if lobby_data.categories and not all(cat in allowed_categories for cat in lobby_data.categories):
                logger.warning(f"Отказ в выборе категории пользователю {user_id} с подпиской Economy")
                raise HTTPException(status_code=403, detail="Ваша подписка не даёт доступа к выбранным категориям")
            
            # Для Economy нельзя выбирать разделы
            lobby_data.pdd_section_uids = None
            
            # Определяем группу (мото или авто)
            if lobby_data.categories and any(cat in ["A1", "A", "B1"] for cat in lobby_data.categories):
                category_group = ["A1", "A", "B1"]
            else:
                category_group = ["B", "BE"]
            
            lobby_data.categories = category_group
            logger.info(f"Установлены категории для Economy: {lobby_data.categories}")
            
        elif subscription_type == "Vip":
            # Vip может выбирать любые категории и разделы ПДД
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
        
        # Ограничим количество запрашиваемых вопросов количеством доступных
        questions_count = min(questions_count, total_questions)
        # Убедимся, что не больше 40 вопросов
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
            
            # Determine media type safely with proper null checks
            media_filename = q.get("media_filename")
            after_answer_media_filename = q.get("after_answer_media_filename")
            
            # Check if filename exists and then check extension
            is_video = False
            if media_filename and isinstance(media_filename, str):
                is_video = media_filename.lower().endswith((".mp4", ".webm", ".mov"))
            
            is_after_answer_video = False
            if after_answer_media_filename and isinstance(after_answer_media_filename, str):
                is_after_answer_video = after_answer_media_filename.lower().endswith((".mp4", ".webm", ".mov"))
            
            # Сохраняем информацию о типе медиа для каждого вопроса
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
        
        # Определяем начальный статус - для solo сразу in_progress, для multi - waiting
        initial_status = "waiting" if lobby_data.mode == "multi" else "in_progress"
        logger.info(f"Установлен начальный статус лобби: {initial_status}")
        
        lobby_doc = {
            "_id": lobby_id,
            "host_id": user_id,
            "status": initial_status,
            "question_ids": question_ids,
            "correct_answers": correct_answers_map,
            "questions_data": questions_data,  # Сохраняем дополнительную информацию о вопросах
            "participants": [user_id],
            "participants_answers": {user_id: {}},
            "current_index": 0,
            "created_at": datetime.utcnow(),
            "sections": lobby_data.pdd_section_uids or [],
            "categories": lobby_data.categories or [],
            "mode": lobby_data.mode,
            "subscription_type": subscription_type,
            "exam_mode": lobby_data.exam_mode
        }
        
        try:
            await db.lobbies.insert_one(lobby_doc)
            logger.info(f"Лобби {lobby_id} успешно создано в базе данных")
            
            # Если solo режим, отправляем WebSocket сообщение о начале теста
            if lobby_data.mode == "solo":
                first_question_id = question_ids[0] if question_ids else None
                if first_question_id:
                    try:
                        # Отправляем событие START и ID первого вопроса
                        logger.info(f"Отправка WS-сообщения start, вопрос: {first_question_id} для solo режима")
                        await ws_manager.send_json(lobby_id, {
                            "type": "start",
                            "data": {"question_id": first_question_id}
                        })

                    except Exception as e:
                        logger.error(f"Ошибка при отправке WebSocket сообщения: {str(e)}")
            
            return success(data={
                "lobby_id": lobby_id, 
                "status": initial_status, 
                "questions_count": questions_count,
                "categories": lobby_data.categories,
                "sections": lobby_data.pdd_section_uids,
                "auto_started": lobby_data.mode == "solo",
                "exam_mode": lobby_data.exam_mode
            })
        except Exception as e:
            # Логируем ошибку
            logger.error(f"Ошибка при создании лобби: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при создании лобби: {str(e)}")
    except HTTPException:
        # Пропускаем HTTP исключения дальше
        raise
    except Exception as e:
        # Логируем и обрабатываем неожиданные ошибки
        logger.error(f"Непредвиденная ошибка при создании лобби: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.post("/lobbies/{lobby_id}/join", summary="Присоединиться к лобби")
async def join_lobby(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Присоединяет указанного пользователя к лобби с учетом его подписки.
    - Проверяет нет ли у пользователя других активных лобби
    - Проверяет доступ к категориям и разделам на основе подписки
    """
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} пытается присоединиться к лобби {lobby_id}")
    
    try:
        # Проверка на наличие активных лобби у пользователя
        active_lobby = await db.lobbies.find_one({
            "participants": user_id,
            "_id": {"$ne": lobby_id},  # Исключаем текущее лобби
            "status": {"$ne": "finished"}
        })
        
        if active_lobby:
            logger.warning(f"Пользователь {user_id} уже в активном лобби {active_lobby['_id']}")
            raise HTTPException(
                status_code=400, 
                detail="У вас уже есть активное лобби. Завершите его перед присоединением к новому."
            )
        
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.error(f"Лобби {lobby_id} не найдено")
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if lobby["status"] != "waiting":
            logger.warning(f"Пользователь {user_id} пытается присоединиться к лобби {lobby_id} со статусом {lobby['status']}")
            raise HTTPException(status_code=400, detail="Нельзя присоединиться: тест уже начат или завершен")
        
        if user_id in lobby["participants"]:
            # Если пользователь уже в лобби, просто возвращаем успех
            logger.info(f"Пользователь {user_id} уже в лобби {lobby_id}")
            return success(data={"message": f"Вы уже присоединены к лобби {lobby_id}"})
        
        if len(lobby["participants"]) >= 35:
            raise HTTPException(status_code=400, detail="Лобби заполнено (максимум 35 участников)")
        
        # Для режима solo можно присоединиться только создателю
        if lobby["mode"] == "solo" and lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Это одиночный тест, нельзя присоединиться")
        
        # Проверка подписки пользователя
        subscription = await db.subscriptions.find_one({
            "user_id": ObjectId(user_id),
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if not subscription:
            # Демо-режим или бесплатный доступ
            user_subscription_type = "Demo"
        else:
            user_subscription_type = subscription["subscription_type"]
        
        # Проверка доступа к категориям (только для Royal-лобби)
        if lobby.get("subscription_type") == "Royal" and user_id != lobby["host_id"]:
            lobby_categories = lobby.get("categories", [])
            
            # Определяем доступные категории пользователя
            if user_subscription_type == "Economy":
                allowed_categories = ["A1", "A", "B1", "B", "BE"]
            elif user_subscription_type in ["Vip", "Royal", "School"]:
                # Полный доступ ко всем категориям
                allowed_categories = None
            else:
                # Демо-режим - ограниченный набор
                allowed_categories = ["B"]
            
            # Проверяем доступ
            if allowed_categories and lobby_categories:
                if not any(cat in allowed_categories for cat in lobby_categories):
                    raise HTTPException(
                        status_code=403, 
                        detail="Ваша подписка не позволяет присоединиться к лобби с данными категориями"
                    )
        
        # Обновляем документ лобби: добавляем участника
        await db.lobbies.update_one({"_id": lobby_id}, {
            "$push": {"participants": user_id},
            "$set": {f"participants_answers.{user_id}": {}}  # создаем запись ответов для нового участника
        })
        
        # Оповещаем других участников о новом пользователе через WebSocket
        try:
            await ws_manager.send_json(lobby_id, {
                "type": "user_joined",
                "data": {"user_id": user_id}
            })
        except Exception as e:
            print(f"Error sending WebSocket notification: {str(e)}")
            # Не прерываем выполнение, если не удалось отправить WebSocket сообщение
        
        return success(data={"message": f"Пользователь присоединился к лобби {lobby_id}"})
    except HTTPException:
        # Пропускаем HTTP исключения дальше
        raise
    except Exception as e:
        # Логируем неожиданные ошибки
        print(f"Unexpected error joining lobby {lobby_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при присоединении к лобби")

@router.post("/lobbies/{lobby_id}/start", summary="Начать тест")
async def start_test(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Начинает тест в лобби. Только создатель лобби может начать тест.
    """
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} пытается начать тест в лобби {lobby_id}")
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.error(f"Лобби {lobby_id} не найдено")
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if lobby["host_id"] != user_id:
            logger.warning(f"Пользователь {user_id} пытается начать тест в чужом лобби {lobby_id}")
            raise HTTPException(status_code=403, detail="Только создатель лобби может начать тест")
        
        if lobby["status"] != "waiting":
            logger.warning(f"Попытка начать тест в лобби {lobby_id} со статусом {lobby['status']}")
            raise HTTPException(status_code=400, detail="Тест уже начат или завершен")
        
        if len(lobby["participants"]) < 2:
            logger.warning(f"Попытка начать тест в лобби {lobby_id} с недостаточным количеством участников")
            raise HTTPException(status_code=400, detail="Необходимо минимум 2 участника для начала теста")
        
        # Обновляем статус лобби
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": {"status": "in_progress"}}
        )
        
        logger.info(f"Тест в лобби {lobby_id} успешно начат")
        
        # Отправляем WebSocket сообщение о начале теста
        try:
            await ws_manager.send_json(lobby_id, {
                "type": "test_started",
                "data": {
                    "message": "Тест начат",
                    "first_question": lobby["question_ids"][0] if lobby["question_ids"] else None
                }
            })
        except Exception as e:
            logger.error(f"Ошибка при отправке WebSocket сообщения о начале теста: {str(e)}")
        
        return success(data={"message": "Тест успешно начат"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при начале теста: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при начале теста")

@router.get("/lobbies/{lobby_id}/current-question", summary="Получить текущий вопрос")
async def get_current_question(lobby_id: str, current_user: dict = Depends(get_current_actor)):
    """
    Получает текущий вопрос в лобби.
    """
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} запрашивает текущий вопрос в лобби {lobby_id}")
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.error(f"Лобби {lobby_id} не найдено")
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if lobby["status"] != "in_progress":
            logger.warning(f"Попытка получить вопрос в лобби {lobby_id} со статусом {lobby['status']}")
            raise HTTPException(status_code=400, detail="Тест не начат или уже завершен")
        
        if user_id not in lobby["participants"]:
            logger.warning(f"Пользователь {user_id} пытается получить вопрос в чужом лобби {lobby_id}")
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        current_question_index = lobby.get("current_index", 0)
        if current_question_index >= len(lobby["question_ids"]):
            logger.warning(f"Попытка получить вопрос за пределами списка в лобби {lobby_id}")
            raise HTTPException(status_code=400, detail="Все вопросы уже пройдены")
        
        current_question = lobby["question_ids"][current_question_index]
        logger.info(f"Текущий вопрос {current_question_index + 1} успешно получен для лобби {lobby_id}")
        
        return success(data={"question": current_question})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении текущего вопроса: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при получении вопроса")

@router.get("/lobbies/{lobby_id}/questions/{question_id}", summary="Получить данные вопроса")
async def get_question(lobby_id: str, question_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Возвращает текст и варианты ответа для вопроса `question_id` из лобби `lobby_id`.
    
    Безопасность:
    - Проверяет, что пользователь является участником этого лобби
    - Проверяет, что лобби в статусе "in_progress"
    - Проверяет, что запрашиваемый вопрос входит в список вопросов лобби
    - Проверяет, что пользователь ответил на все предыдущие вопросы
    - Запрашиваемый вопрос должен быть текущим или уже отвеченным
    """
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} запрашивает вопрос {question_id} в лобби {lobby_id}")
    
    try:
        # Получаем данные о лобби
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.warning(f"Лобби {lobby_id} не найдено")
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем, что пользователь участник лобби
        if user_id not in lobby["participants"]:
            logger.warning(f"Пользователь {user_id} не является участником лобби {lobby_id}")
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        # Проверяем статус лобби - должен быть "in_progress"
        if lobby["status"] != "in_progress":
            logger.warning(f"Лобби {lobby_id} не в статусе 'in_progress', текущий статус: {lobby['status']}")
            raise HTTPException(status_code=400, detail="Тест не активен. Статус лобби должен быть 'in_progress'")
        
        # Проверяем, что запрашиваемый вопрос входит в список вопросов лобби
        if question_id not in lobby["question_ids"]:
            logger.warning(f"Запрашиваемый вопрос {question_id} не входит в список вопросов лобби {lobby_id}")
            raise HTTPException(status_code=403, detail="Запрашиваемый вопрос не является частью этого теста")

        # Проверяем, является ли этот вопрос текущим или уже отвеченным
        current_index = lobby.get("current_index", 0)
        
        if current_index >= len(lobby["question_ids"]):
            logger.error(f"Некорректный индекс текущего вопроса в лобби {lobby_id}: {current_index}")
            raise HTTPException(status_code=500, detail="Некорректный индекс текущего вопроса")
            
        current_question_id = lobby["question_ids"][current_index]
        
        user_answers = lobby.get("participants_answers", {}).get(user_id, {})
        question_index = lobby["question_ids"].index(question_id)
        
        # Хост лобби может получить любой вопрос
        is_host = user_id == lobby.get("host_id")
        
        # Проверка, что все предыдущие вопросы отвечены
        all_previous_answered = True
        for i in range(question_index):
            prev_question_id = lobby["question_ids"][i]
            if prev_question_id not in user_answers:
                all_previous_answered = False
                break
        
        # Пользователь должен либо быть хостом, либо:
        # 1. Этот вопрос должен быть текущим и все предыдущие должны быть отвечены, или
        # 2. Пользователь уже ответил на этот вопрос
        if not is_host and question_id != current_question_id and question_id not in user_answers:
            logger.warning(f"Пользователь {user_id} пытается получить вопрос {question_id}, который не является текущим и на который пользователь не ответил")
            raise HTTPException(status_code=403, detail="Вам необходимо сначала ответить на все предыдущие вопросы")
        
        if not is_host and question_id == current_question_id and not all_previous_answered:
            logger.warning(f"Пользователь {user_id} пытается получить текущий вопрос {question_id} без ответа на предыдущие вопросы")
            raise HTTPException(status_code=403, detail="Вам необходимо сначала ответить на все предыдущие вопросы")

        # Запрашиваем вопрос из коллекции вопросов
        question = await db.questions.find_one({"_id": ObjectId(question_id)})
        if not question:
            logger.error(f"Вопрос {question_id} не найден в базе данных")
            raise HTTPException(status_code=404, detail="Вопрос не найден")
        
        # Проверяем, отвечал ли уже пользователь на этот вопрос
        answer = lobby.get("participants_answers", {}).get(user_id, {}).get(question_id)
        has_answered = answer is not None
        
        # Получаем информацию о медиа-файлах для вопроса
        question_data = lobby.get("questions_data", {}).get(question_id, {})
        has_media = question_data.get("has_media", False) or question.get("has_media", False)
        media_type = question_data.get("media_type", "image") 
        
        # Очищаем данные, не нужные клиенту
        question_out = {
            "id": str(question["_id"]),
            "question_text": question.get("question_text", {}),
            "answers": [option["text"] for option in question.get("options", [])],
            "has_media": has_media,
            "media_type": media_type,
            "has_after_answer_media": question_data.get("has_after_answer_media", False) and has_answered,
            "after_answer_media_type": question_data.get("after_answer_media_type", "image") if has_answered else None
        }
        
        # Если пользователь уже ответил и это не экзаменационный режим, добавляем объяснение
        if has_answered and not lobby.get("exam_mode", False):
            question_out["explanation"] = question.get("explanation", {})
        else:
            question_out["explanation"] = None  # Объяснение будет доступно только после ответа
        
        logger.info(f"Успешно возвращен вопрос {question_id} для пользователя {user_id} в лобби {lobby_id}")
        return success(data=question_out)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении вопроса {question_id} в лобби {lobby_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.get("/files/media/{question_id}", summary="Получить медиа-файл вопроса")
async def get_question_media(
    question_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """
    Получает медиа-файл для конкретного вопроса.
    
    Безопасность:
    - Проверяет, что пользователь имеет доступ к данному вопросу через активное лобби
    - Проверяет, что вопрос является текущим или уже отвеченным
    """
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} запрашивает медиа для вопроса {question_id}")
    
    try:
        # Находим вопрос в базе данных
        question = await db.questions.find_one({"_id": ObjectId(question_id)})
        if not question:
            logger.warning(f"Вопрос {question_id} не найден")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=not_found.svg'}
            )
        
        # Проверяем наличие медиа-файла
        media_file_id = question.get("media_file_id")
        if not media_file_id:
            logger.warning(f"У вопроса {question_id} нет media_file_id")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=no_media.svg'}
            )
        
        # Проверяем, что вопрос принадлежит хотя бы одному активному лобби пользователя
        active_lobby = None
        active_lobbies = await db.lobbies.find({
            "participants": user_id,
            "question_ids": question_id,
            "status": "in_progress"
        }).to_list(None)
        
        if not active_lobbies:
            logger.warning(f"Пользователь {user_id} запрашивает медиа для вопроса {question_id}, который не входит в активные лобби пользователя")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=no_access.svg'}
            )
        
        # Проверяем доступ к вопросу по каждому лобби
        has_access = False
        for lobby in active_lobbies:
            current_index = lobby.get("current_index", 0)
            current_question_id = lobby["question_ids"][current_index] if current_index < len(lobby["question_ids"]) else None
            user_answers = lobby.get("participants_answers", {}).get(user_id, {})
            
            # Доступ разрешен, если пользователь хост, или если вопрос текущий или уже отвеченный
            is_host = user_id == lobby.get("host_id")
            is_current = question_id == current_question_id
            is_answered = question_id in user_answers
            
            if is_host or is_current or is_answered:
                has_access = True
                active_lobby = lobby
                break
                
        if not has_access:
            logger.warning(f"Пользователь {user_id} не имеет доступа к медиа для вопроса {question_id}")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=no_access.svg'}
            )
            
        # Получаем медиа-файл из GridFS
        try:
            logger.info(f"Получение медиа-файла с ID {media_file_id} для вопроса {question_id}")
            media_data = await get_media_file(str(media_file_id), db)
            if not media_data:
                logger.error(f"Медиа-файл {media_file_id} не найден в GridFS")
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=not_found.svg'}
                )
                
            # Получение информации о файле (content type)
            file_info = await db.fs.files.find_one({"_id": ObjectId(media_file_id)})
            if not file_info:
                logger.error(f"Информация о файле {media_file_id} не найдена в GridFS")
                content_type = "application/octet-stream"
                filename = "media_file"
            else:
                content_type = file_info.get("contentType", "application/octet-stream")
                filename = file_info.get("filename", "media_file")
            
            logger.info(f"Тип содержимого медиа-файла: {content_type}")
            
            # Проверяем, является ли это видеофайлом
            is_video = content_type.startswith("video/")
            
            # Добавляем эту информацию в вопрос, если has_media не установлен
            if not question.get("has_media") and media_data:
                logger.info(f"Обновляем информацию о медиа для вопроса {question_id}")
                await db.questions.update_one(
                    {"_id": ObjectId(question_id)},
                    {"$set": {
                        "has_media": True,
                        "media_type": "video" if is_video else "image"
                    }}
                )
                
                # Также обновляем кэшированную информацию в лобби
                if active_lobby and active_lobby.get("questions_data") and active_lobby["questions_data"].get(question_id):
                    logger.info(f"Обновляем кэшированную информацию о медиа в лобби {active_lobby['_id']}")
                    await db.lobbies.update_one(
                        {"_id": active_lobby["_id"]},
                        {"$set": {
                            f"questions_data.{question_id}.has_media": True,
                            f"questions_data.{question_id}.media_type": "video" if is_video else "image"
                        }}
                    )
            
            # Return streaming response similar to the admin endpoint
            return StreamingResponse(
                iter([media_data]),
                media_type=content_type,
                headers={
                    'Content-Disposition': f'inline; filename={filename}',
                    'Content-Length': str(len(media_data))
                }
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении медиа-файла для вопроса {question_id}: {str(e)}")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=error.svg'}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении медиа для вопроса {question_id}: {str(e)}")
        return StreamingResponse(
            iter([b'']),
            media_type='image/svg+xml',
            headers={'Content-Disposition': 'inline; filename=server_error.svg'}
        )

@router.get("/files/after-answer-media/{question_id}", summary="Получить дополнительный медиа-файл после ответа")
async def get_after_answer_media(
    question_id: str,
    lobby_id: str = Query(None, description="ID лобби, в котором пользователь ответил на вопрос"),
    current_user: dict = Depends(get_current_actor)
):
    """
    Получает дополнительный медиа-файл для показа после ответа на вопрос.
    
    Безопасность:
    - Проверяет, что пользователь ответил на этот вопрос
    - Если указан lobby_id, проверяет ответ в конкретном лобби
    - Не позволяет получить медиа, если пользователь не ответил на вопрос
    """
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} запрашивает медиа после ответа для вопроса {question_id} в лобби {lobby_id or 'любом'}")
    
    try:
        # Находим вопрос в базе данных
        question = await db.questions.find_one({"_id": ObjectId(question_id)})
        if not question:
            logger.warning(f"Вопрос {question_id} не найден")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=not_found.svg'}
            )
        
        # Проверяем наличие дополнительного медиа-файла
        after_answer_media_id = question.get("after_answer_media_file_id") or question.get("after_answer_media_id")
        if not after_answer_media_id:
            logger.warning(f"У вопроса {question_id} нет дополнительного медиа-файла")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=no_media.svg'}
            )
        
        # Проверяем, ответил ли пользователь на этот вопрос в указанном или любом лобби
        has_answered = False
        
        if lobby_id:
            # Проверяем конкретное лобби
            lobby = await db.lobbies.find_one({"_id": lobby_id, "participants": user_id})
            if not lobby:
                logger.warning(f"Лобби {lobby_id} не найдено или пользователь {user_id} не является его участником")
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=no_access.svg'}
                )
                
            # Проверяем, входит ли вопрос в это лобби
            if question_id not in lobby.get("question_ids", []):
                logger.warning(f"Вопрос {question_id} не входит в лобби {lobby_id}")
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=question_not_in_lobby.svg'}
                )
                
            # Проверяем, ответил ли пользователь на этот вопрос
            participant_answers = lobby.get("participants_answers", {}).get(user_id, {})
            has_answered = question_id in participant_answers
            
        else:
            # Проверяем все активные лобби пользователя
            active_lobbies = await db.lobbies.find({
                "participants": user_id,
                "question_ids": question_id
            }).to_list(None)
            
            for lobby in active_lobbies:
                participant_answers = lobby.get("participants_answers", {}).get(user_id, {})
                if question_id in participant_answers:
                    has_answered = True
                    break
        
        if not has_answered:
            logger.warning(f"Пользователь {user_id} пытается получить медиа после ответа, не ответив на вопрос {question_id}")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=answer_first.svg'}
            )
        
        # Получаем медиа-файл из GridFS
        try:
            media_data = await get_media_file(str(after_answer_media_id), db)
            if not media_data:
                return StreamingResponse(
                    iter([b'']),
                    media_type='image/svg+xml',
                    headers={'Content-Disposition': 'inline; filename=not_found.svg'}
                )
                
            # Получение информации о файле (content type)
            file_info = await db.fs.files.find_one({"_id": ObjectId(after_answer_media_id)})
            if not file_info:
                content_type = "application/octet-stream"
                filename = "after_answer_media"
            else:
                content_type = file_info.get("contentType", "application/octet-stream")
                filename = file_info.get("filename", "after_answer_media")
            
            # Return streaming response for after-answer media
            return StreamingResponse(
                iter([media_data]),
                media_type=content_type,
                headers={
                    'Content-Disposition': f'inline; filename={filename}',
                    'Content-Length': str(len(media_data))
                }
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении дополнительного медиа-файла для вопроса {question_id}: {str(e)}")
            return StreamingResponse(
                iter([b'']),
                media_type='image/svg+xml',
                headers={'Content-Disposition': 'inline; filename=error.svg'}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении дополнительного медиа для вопроса {question_id}: {str(e)}")
        return StreamingResponse(
            iter([b'']),
            media_type='image/svg+xml',
            headers={'Content-Disposition': 'inline; filename=server_error.svg'}
        )

@router.get("/lobbies/{lobby_id}/get-next-question", summary="Получить следующий вопрос")
async def get_next_question(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """
    Возвращает ID следующего вопроса, если пользователь ответил на текущий.
    
    Безопасность:
    - Проверяет, что пользователь ответил на все предыдущие вопросы включая текущий
    - Предотвращает пропуск вопросов
    """
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} запрашивает следующий вопрос в лобби {lobby_id}")
    
    try:
        # Получаем данные о лобби
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.warning(f"Лобби {lobby_id} не найдено")
            raise HTTPException(status_code=404, detail="Лобби не найдено")
            
        # Проверяем, является ли пользователь участником лобби
        if user_id not in lobby["participants"]:
            logger.warning(f"Пользователь {user_id} не является участником лобби {lobby_id}")
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
            
        # Проверяем статус лобби
        if lobby["status"] != "in_progress":
            logger.warning(f"Лобби {lobby_id} не в статусе 'in_progress', текущий статус: {lobby['status']}")
            raise HTTPException(status_code=400, detail="Тест не активен")
            
        current_index = lobby.get("current_index", 0)
        question_ids = lobby.get("question_ids", [])
        
        # Проверяем, есть ли следующий вопрос
        if current_index >= len(question_ids) - 1:
            logger.info(f"Пользователь {user_id} запросил следующий вопрос, но все вопросы уже пройдены")
            return success(data={"message": "Все вопросы пройдены", "is_last": True})
            
        # Проверяем, ответил ли пользователь на текущий вопрос
        current_question_id = question_ids[current_index]
        user_answers = lobby.get("participants_answers", {}).get(user_id, {})
        
        # Хост может переходить к следующему вопросу
        is_host = user_id == lobby.get("host_id")
        
        if not is_host and current_question_id not in user_answers:
            logger.warning(f"Пользователь {user_id} пытается получить следующий вопрос, не ответив на текущий {current_question_id}")
            raise HTTPException(status_code=403, detail="Вы должны сначала ответить на текущий вопрос")
            
        # Проверяем, ответил ли пользователь на все предыдущие вопросы
        for i in range(current_index + 1):
            q_id = question_ids[i]
            if not is_host and q_id not in user_answers:
                logger.warning(f"Пользователь {user_id} пытается получить следующий вопрос, не ответив на вопрос {q_id}")
                raise HTTPException(status_code=403, detail="Вы должны ответить на все предыдущие вопросы")
                
        # Возвращаем ID следующего вопроса
        next_index = current_index + 1
        next_question_id = question_ids[next_index]
        
        logger.info(f"Пользователь {user_id} успешно получил следующий вопрос {next_question_id}")
        return success(data={
            "next_question_id": next_question_id,
            "next_index": next_index,
            "total_questions": len(question_ids)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении следующего вопроса в лобби {lobby_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

def get_user_id(current_user):
    return str(current_user["id"])

@router.get("/lobbies/{lobby_id}/correct-answer", summary="Получить индекс правильного ответа на вопрос")
async def get_correct_answer(
    lobby_id: str,
    question_id: str = Query(..., description="ID вопроса"),
    current_user: dict = Depends(get_current_actor)
):
    """
    Получает индекс правильного ответа и объяснение для вопроса.
    
    Безопасность:
    - Доступно только после того, как пользователь ответил на вопрос
    - В экзаменационном режиме не доступно до окончания теста
    - Правильные ответы на предыдущие вопросы доступны всегда
    - Хост может получить правильный ответ для любого вопроса
    """
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} запрашивает правильный ответ для вопроса {question_id} в лобби {lobby_id}")

    try:
        # Получаем информацию о лобби
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.warning(f"Лобби {lobby_id} не найдено")
            raise HTTPException(status_code=404, detail="Лобби не найдено")

        # Проверяем статус лобби
        if lobby["status"] != "in_progress" and lobby["status"] != "finished":
            logger.warning(f"Некорректный статус лобби {lobby_id}: {lobby['status']}")
            raise HTTPException(status_code=400, detail="Тест неактивен или завершен")

        # Проверяем, является ли пользователь участником лобби
        if user_id not in lobby["participants"]:
            logger.warning(f"Пользователь {user_id} не является участником лобби {lobby_id}")
            raise HTTPException(status_code=403, detail="Вы не участник этого лобби")

        # Проверяем, относится ли вопрос к этому лобби
        if question_id not in lobby.get("question_ids", []):
            logger.warning(f"Вопрос {question_id} не относится к лобби {lobby_id}")
            raise HTTPException(status_code=403, detail="Вопрос не относится к этому лобби")

        # Проверяем, является ли пользователь хостом
        is_host = user_id == lobby["host_id"]
        
        # Проверяем ответы пользователя
        user_answers = lobby.get("participants_answers", {}).get(user_id, {})
        has_answered = question_id in user_answers
        
        # Получаем индекс вопроса в списке вопросов
        question_index = lobby["question_ids"].index(question_id)
        current_index = lobby.get("current_index", 0)
        
        # Правила доступа к правильному ответу:
        # 1. Хост всегда имеет доступ
        # 2. В экзаменационном режиме ответы доступны только после завершения теста
        # 3. Пользователь должен ответить на вопрос, чтобы увидеть правильный ответ
        # 4. Правильные ответы на предыдущие вопросы доступны всегда
        is_past_question = question_index < current_index
        
        if not is_host:
            # Проверяем экзаменационный режим
            if lobby.get("exam_mode", False) and lobby["status"] != "finished":
                logger.warning(f"Пользователь {user_id} пытается получить правильный ответ в экзаменационном режиме до завершения теста")
                raise HTTPException(status_code=403, detail="В экзаменационном режиме правильные ответы доступны только после завершения теста")
            
            # Проверяем, ответил ли пользователь на этот вопрос
            if not has_answered and not is_past_question:
                logger.warning(f"Пользователь {user_id} запрашивает правильный ответ для вопроса {question_id}, на который еще не ответил")
                raise HTTPException(status_code=403, detail="Вы должны сначала ответить на вопрос")

        # Получаем индекс правильного ответа
        correct_index = lobby.get("correct_answers", {}).get(question_id)
        if correct_index is None:
            logger.error(f"Правильный ответ для вопроса {question_id} не найден в лобби {lobby_id}")
            raise HTTPException(status_code=404, detail="Правильный ответ не найден")

        # Получаем дополнительную информацию о вопросе
        question = await db.questions.find_one({"_id": ObjectId(question_id)})
        
        response_data = {
            "correct_index": correct_index,
            "has_explanation": False,
            "has_after_media": False
        }
        
        # Если вопрос найден, добавляем объяснение и информацию о дополнительном медиа
        if question:
            response_data["explanation"] = question.get("explanation")
            response_data["has_explanation"] = bool(question.get("explanation"))
            
            # Проверяем наличие дополнительного медиа-файла
            has_after_media = bool(question.get("after_answer_media_file_id") or question.get("after_answer_media_id"))
            response_data["has_after_media"] = has_after_media
            response_data["has_after_answer_media"] = has_after_media  # Для совместимости
            
            # Определяем тип дополнительного медиа
            after_media_filename = question.get("after_answer_media_filename", "")
            if after_media_filename:
                is_video = after_media_filename.lower().endswith((".mp4", ".webm", ".mov"))
                response_data["after_answer_media_type"] = "video" if is_video else "image"
                
            # Получаем текст правильного варианта ответа
            if "options" in question and isinstance(question["options"], list) and 0 <= correct_index < len(question["options"]):
                response_data["correct_answer_text"] = question["options"][correct_index].get("text", {})
        
        logger.info(f"Успешно возвращен правильный ответ для вопроса {question_id} пользователю {user_id}")
        return success(data=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении правильного ответа: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.post("/lobbies/{lobby_id}/answer", summary="Отправить ответ на вопрос")
async def submit_answer(
    lobby_id: str,
    payload: AnswerSubmit,
    request: Request = None, 
    current_user: dict = Depends(get_current_actor)
):
    """
    Принимает ответ пользователя на вопрос и сохраняет его результат.
    
    Безопасность:
    - Проверяет, что пользователь является участником лобби
    - Проверяет, что лобби активно
    - Проверяет, что вопрос принадлежит лобби
    - Проверяет, что пользователь не ответил ранее на этот вопрос
    - Проверяет, что вопрос является текущим или предыдущим
    - Проверяет, что пользователь ответил на все предыдущие вопросы
    
    После ответа всех участников:
    - Автоматически переходит к следующему вопросу
    - После всех 40 вопросов завершает тест
    """
    user_id = get_user_id(current_user)
    question_id = payload.question_id
    answer_index = payload.answer_index
    
    logger.info(f"Пользователь {user_id} отправляет ответ на вопрос {question_id} в лобби {lobby_id}, индекс ответа: {answer_index}")
    
    try:
        # Получаем информацию о лобби
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.warning(f"Лобби {lobby_id} не найдено")
            raise HTTPException(status_code=404, detail="Лобби не найдено")
            
        # Проверяем, является ли пользователь участником лобби
        if user_id not in lobby["participants"]:
            logger.warning(f"Пользователь {user_id} не является участником лобби {lobby_id}")
            raise HTTPException(status_code=403, detail="Вы не участник данного лобби")
            
        # Проверяем, относится ли вопрос к данному лобби
        if question_id not in lobby.get("question_ids", []):
            logger.warning(f"Вопрос {question_id} не относится к лобби {lobby_id}")
            raise HTTPException(status_code=403, detail="Вопрос не относится к данному лобби")
            
        # Проверяем статус лобби
        if lobby["status"] != "in_progress":
            logger.warning(f"Лобби {lobby_id} не в статусе 'in_progress', текущий статус: {lobby['status']}")
            raise HTTPException(status_code=400, detail="Лобби не активно")
        
        # Проверяем, не отвечал ли пользователь уже на этот вопрос
        user_answers = lobby.get("participants_answers", {}).get(user_id, {})
        if question_id in user_answers:
            logger.warning(f"Пользователь {user_id} пытается повторно ответить на вопрос {question_id}")
            raise HTTPException(status_code=400, detail="Вы уже ответили на этот вопрос")
        
        # Получаем информацию о текущем вопросе и индексе в последовательности
        current_index = lobby.get("current_index", 0)
        question_ids = lobby.get("question_ids", [])
        current_question_id = question_ids[current_index] if current_index < len(question_ids) else None
        
        # Получаем индекс запрашиваемого вопроса
        try:
            question_index = question_ids.index(question_id)
        except ValueError:
            logger.error(f"Вопрос {question_id} не найден в списке вопросов лобби {lobby_id}")
            raise HTTPException(status_code=400, detail="Вопрос не найден в списке вопросов")
        
        # Хост может отвечать на любой вопрос
        is_host = user_id == lobby.get("host_id")
        
        # Пользователь должен отвечать на все вопросы по порядку
        if not is_host:
            # Проверяем, что это текущий или предыдущий вопрос
            if question_index > current_index:
                logger.warning(f"Пользователь {user_id} пытается ответить на вопрос {question_id} раньше времени")
                raise HTTPException(status_code=403, detail="Вы не можете отвечать на этот вопрос, пока не дойдете до него")
            
            # Проверяем, что пользователь ответил на все предыдущие вопросы
            for i in range(question_index):
                prev_question_id = question_ids[i]
                if prev_question_id not in user_answers:
                    logger.warning(f"Пользователь {user_id} пытается ответить на вопрос {question_id}, не ответив на предыдущий вопрос {prev_question_id}")
                    raise HTTPException(status_code=403, detail="Вы должны ответить на все предыдущие вопросы")
            
        # Проверяем правильность ответа
        correct_answer = lobby["correct_answers"].get(question_id)
        if correct_answer is None:
            logger.error(f"Правильный ответ для вопроса {question_id} не найден в лобби {lobby_id}")
            raise HTTPException(status_code=500, detail="Правильный ответ для данного вопроса не найден")
        
        # Проверяем валидность индекса ответа
        question = await db.questions.find_one({"_id": ObjectId(question_id)})
        if question and "options" in question:
            options_count = len(question["options"])
            if answer_index < 0 or answer_index >= options_count:
                logger.warning(f"Пользователь {user_id} отправил недопустимый индекс ответа: {answer_index} (доступно вариантов: {options_count})")
                raise HTTPException(status_code=400, detail=f"Недопустимый индекс ответа. Должен быть от 0 до {options_count-1}")
        
        is_correct = (answer_index == correct_answer)
        logger.info(f"Ответ пользователя {user_id} на вопрос {question_id}: {is_correct} (выбрано: {answer_index}, правильно: {correct_answer})")
        
        # Сохраняем ответ пользователя в коллекцию user_answers
        answer_doc = {
            "user_id": user_id,
            "lobby_id": lobby_id,
            "question_id": question_id,
            "answer_index": answer_index,
            "is_correct": is_correct,
            "timestamp": datetime.utcnow()
        }
        await db.user_answers.insert_one(answer_doc)
        
        # Обновляем информацию в документе лобби
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": {f"participants_answers.{user_id}.{question_id}": is_correct}}
        )
        
        # Отправляем уведомление всем участникам
        try:
            await ws_manager.send_json(lobby_id, {
                "type": "answer_received",
                "data": {
                    "user_id": user_id,
                    "question_id": question_id,
                    "is_correct": is_correct
                }
            })
        except Exception as e:
            logger.error(f"Ошибка при отправке WebSocket уведомления: {str(e)}")

        # Проверяем, все ли пользователи ответили на текущий вопрос
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        current_index = lobby.get("current_index", 0)
        current_question_id = lobby["question_ids"][current_index]
        
        all_answered = True
        for participant_id in lobby["participants"]:
            # Проверяем, ответил ли участник на текущий вопрос
            if current_question_id not in lobby.get("participants_answers", {}).get(participant_id, {}):
                all_answered = False
                break
        
        # Если все участники ответили на текущий вопрос и это был текущий вопрос,
        # переходим к следующему вопросу
        if all_answered and current_question_id == question_id:
            total_questions = len(lobby.get("question_ids", []))
            
            # Если это был последний вопрос (или уже достигли 40 вопросов), завершаем тест
            if current_index >= total_questions - 1 or current_index >= 39:  # 0-based index, 39 = 40 вопросов
                logger.info(f"Все участники ответили на последний вопрос {question_id} в лобби {lobby_id}, завершаем тест")
                
                # Завершаем тест
                await db.lobbies.update_one(
                    {"_id": lobby_id}, 
                    {"$set": {"status": "finished", "finished_at": datetime.utcnow()}}
                )
                
                # Получаем финальные данные для подсчета результатов
                results = {}
                for participant_id, answers in lobby.get("participants_answers", {}).items():
                    correct_count = sum(1 for is_corr in answers.values() if is_corr)
                    results[participant_id] = {"correct": correct_count, "total": total_questions}
                    
                    # Сохраняем запись об истории прохождения
                    history_record = {
                        "user_id": participant_id,
                        "lobby_id": lobby_id,
                        "date": datetime.utcnow(),
                        "score": correct_count,
                        "total": total_questions,
                        "categories": lobby.get("categories", []),
                        "sections": lobby.get("sections", []),
                        "mode": lobby.get("mode", "solo"),
                        "pass_percentage": (correct_count / total_questions * 100) if total_questions > 0 else 0
                    }
                    await db.history.insert_one(history_record)
                
                # Отправляем уведомление о завершении теста
                try:
                    await ws_manager.send_json(lobby_id, {
                        "type": "test_finished",
                        "data": results
                    })
                except Exception as e:
                    logger.error(f"Ошибка при отправке WebSocket уведомления о завершении теста: {str(e)}")

            else:
                # Переходим к следующему вопросу
                new_index = current_index + 1
                logger.info(f"Все участники ответили на вопрос {question_id} в лобби {lobby_id}, переходим к следующему вопросу (индекс {new_index})")
                
                await db.lobbies.update_one({"_id": lobby_id}, {"$set": {"current_index": new_index}})
                next_question_id = lobby["question_ids"][new_index]
                
                # Уведомляем всех о переходе к следующему вопросу
                try:
                    await ws_manager.send_json(lobby_id, {
                        "type": "next_question",
                        "data": {"question_id": next_question_id}
                    })
                except Exception as e:
                    logger.error(f"Ошибка при отправке WebSocket уведомления о следующем вопросе: {str(e)}")

        # Получаем информацию о вопросе для ответа
        if question:
            explanation = question.get("explanation", {})
            
            # Определяем текст правильного варианта ответа
            correct_option_text = None
            options = question.get("options", [])
            if options and 0 <= correct_answer < len(options):
                correct_option_text = options[correct_answer].get("text", {})
        else:
            explanation = {}
            correct_option_text = None

        # Формируем ответ
        response_data = {
            "is_correct": is_correct,
            "correct_index": correct_answer,
            "explanation": explanation,
            "has_after_answer_media": bool(question and (question.get("after_answer_media_file_id") or question.get("after_answer_media_id"))),
            "after_answer_media_type": None
        }
        
        # Если есть дополнительное медиа, определяем его тип
        if question and (question.get("after_answer_media_file_id") or question.get("after_answer_media_id")):
            filename = question.get("after_answer_media_filename", "")
            is_video = filename.lower().endswith((".mp4", ".webm", ".mov"))
            response_data["after_answer_media_type"] = "video" if is_video else "image"

        # В экзаменационном режиме не показываем правильные ответы и объяснения до завершения теста
        if lobby.get("exam_mode", False):
            response_data["correct_index"] = None
            response_data["explanation"] = None
            response_data["has_after_answer_media"] = False
            
        logger.info(f"Ответ пользователя {user_id} на вопрос {question_id} в лобби {lobby_id} успешно обработан")
        return success(data=response_data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обработке ответа пользователя {user_id} на вопрос {question_id} в лобби {lobby_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.post("/lobbies/{lobby_id}/skip", summary="Пропустить текущий вопрос")
async def skip_question(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Хост пропускает текущий вопрос и переходит к следующему.
    Результаты пользователей, которые успели ответить, сохраняются.
    Результаты не ответивших пользователей на этот вопрос не учитываются.
    """
    user_id = get_user_id(current_user)
    
    lobby = await db.lobbies.find_one({"_id": lobby_id})
    if not lobby:
        raise HTTPException(status_code=404, detail="Лобби не найдено")
    if lobby["host_id"] != user_id:
        raise HTTPException(status_code=403, detail="Только хост может пропускать вопросы")
    if lobby["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Тест не запущен")

    current_index = lobby.get("current_index", 0)
    total_questions = len(lobby.get("question_ids", []))
    
    # Если текущий вопрос не последний и не достигнуто 40 вопросов, перейдем к следующему
    if current_index < total_questions - 1 and current_index < 39:  # 0-based index, 39 = 40 вопросов
        new_index = current_index + 1
        await db.lobbies.update_one({"_id": lobby_id}, {"$set": {"current_index": new_index}})
        next_question_id = lobby["question_ids"][new_index]
        
        # Уведомляем всех по WebSocket о переходе к следующему вопросу
        await ws_manager.send_json(lobby_id, {
            "type": "skip_to",
            "data": {"question_id": next_question_id}
        })

        return success(data={"message": "Вопрос пропущен, переход к следующему"})
    else:
        # Если это был последний вопрос или уже ответили на 40 вопросов, завершаем тест
        await db.lobbies.update_one(
            {"_id": lobby_id}, 
            {"$set": {"status": "finished", "finished_at": datetime.utcnow()}}
        )
        
        # Получаем финальные данные для подсчета результатов
        results = {}
        for participant_id, answers in lobby.get("participants_answers", {}).items():
            correct_count = sum(1 for is_corr in answers.values() if is_corr)
            results[participant_id] = {"correct": correct_count, "total": total_questions}
            
            # Сохраняем запись об истории прохождения
            history_record = {
                "user_id": participant_id,
                "lobby_id": lobby_id,
                "date": datetime.utcnow(),
                "score": correct_count,
                "total": total_questions,
                "categories": lobby.get("categories", []),
                "sections": lobby.get("sections", []),
                "mode": lobby.get("mode", "solo"),
                "pass_percentage": (correct_count / total_questions * 100) if total_questions > 0 else 0
            }
            await db.history.insert_one(history_record)
        
        # Отправляем уведомление о завершении теста
        await ws_manager.send_json(lobby_id, {
            "type": "test_finished",
            "data": results
        })

        return success(data={"message": "Тест завершен", "results": results})

@router.post("/lobbies/{lobby_id}/kick", summary="Исключить участника из лобби")
async def kick_participant(
    lobby_id: str,
    target_user_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """
    Исключает участника из лобби. Только хост лобби может исключать участников.
    """
    user_id = get_user_id(current_user)
    print(f"Zapros na isklyuchenie uchastnika {target_user_id} iz lobbi {lobby_id} ot polzovatelya {user_id}")
    
    # Получаем информацию о лобби
    lobby = await db.lobbies.find_one({"_id": lobby_id})
    if not lobby:
        print(f"Lobbi {lobby_id} ne naideno")
        raise HTTPException(status_code=404, detail="Лобби не найдено")
    
    # Проверяем, является ли пользователь хостом лобби
    if lobby["host_id"] != user_id:
        print(f"Polzovatel {user_id} ne yavlyaetsya hostom lobbi {lobby_id}")
        raise HTTPException(status_code=403, detail="Только хост лобби может исключать участников")
    
    # Проверяем, существует ли участник в лобби
    if target_user_id not in lobby["participants"]:
        print(f"Uchastnik {target_user_id} ne naiden v lobbi {lobby_id}")
        raise HTTPException(status_code=404, detail="Участник не найден в лобби")
    
    # Нельзя исключить хоста
    if target_user_id == lobby["host_id"]:
        print(f"Popytka isklyuchit hosta {target_user_id} iz lobbi {lobby_id}")
        raise HTTPException(status_code=400, detail="Нельзя исключить хоста лобби")
    
    try:
        # Удаляем участника из списка участников
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$pull": {"participants": target_user_id}}
        )
        print(f"Uchastnik {target_user_id} isklyuchen iz lobbi {lobby_id}")
        
        # Отправляем WebSocket сообщение об исключении участника
        try:
            print(f"Otpravka WebSocket soobsheniya USER_KICKED:{target_user_id}")
            await ws_manager.send_json(lobby_id, {
                "type": "user_kicked",
                "data": {"user_id": target_user_id}
            })

        except Exception as e:
            print(f"Oshibka pri otpravke WebSocket soobsheniya: {str(e)}")
        
        return success(data={"status": "ok"})
    except Exception as e:
        print(f"Oshibka pri isklyuchenii uchastnika: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при исключении участника")

@router.post("/lobbies/{lobby_id}/finish", summary="Завершить тест")
async def finish_lobby(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Досрочно завершает тест в лобби, фиксируя его результаты.
    - В solo-режиме пользователь может завершить только свой тест
    - В multi-режиме только хост может завершить тест
    - Результаты всех ответивших пользователей сохраняются
    - Предоставляется подробная статистика по результатам теста
    """
    user_id = get_user_id(current_user)
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # В solo-режиме пользователь может завершить свой тест
        # В multi-режиме только хост может завершить тест
        if lobby["mode"] == "multi" and lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Только хост может завершить тест")
        
        if lobby["mode"] == "solo" and lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Вы не можете завершить чужой тест")
        
        if lobby["status"] != "in_progress":
            raise HTTPException(status_code=400, detail="Тест не запущен или уже завершен")
    
        # Устанавливаем статус "finished"
        finished_time = datetime.utcnow()
        duration = (finished_time - lobby.get("created_at", finished_time)).total_seconds()
        
        await db.lobbies.update_one({"_id": lobby_id}, {
            "$set": {
                "status": "finished", 
                "finished_at": finished_time,
                "duration_seconds": duration
            }
        })
        
        # Получаем финальные данные лобби для подсчета результатов
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        results = {}
        detailed_results = {}
        total_questions = len(lobby.get("question_ids", []))
        
        # Получаем детальную информацию по всем вопросам
        questions_data = {}
        for q_id in lobby.get("question_ids", []):
            question = await db.questions.find_one({"_id": ObjectId(q_id)})
            if question:
                questions_data[q_id] = {
                    "text": question.get("question_text", ""),
                    "section": question.get("pdd_section", ""),
                    "category": question.get("categories", []),
                    "correct_answer": chr(ord('A') + lobby["correct_answers"].get(q_id, 0))
                }
        
        for participant_id, answers in lobby.get("participants_answers", {}).items():
            # Считаем количество правильных ответов участника
            correct_count = sum(1 for is_corr in answers.values() if is_corr)
            incorrect_count = sum(1 for is_corr in answers.values() if not is_corr)
            answered_count = len(answers)
            not_answered_count = total_questions - answered_count
            
            # Базовые результаты
            results[participant_id] = {
                "correct": correct_count, 
                "total": total_questions,
                "percentage": round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0
            }
            
            # Детальные результаты с метриками
            detailed_results[participant_id] = {
                "correct_count": correct_count,
                "incorrect_count": incorrect_count,
                "answered_count": answered_count,
                "not_answered_count": not_answered_count,
                "total_questions": total_questions,
                "passing_score": correct_count >= int(total_questions * 0.8),  # 80% правильных для прохождения
                "percentage": round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0,
                "duration_seconds": duration,
                "duration_formatted": f"{int(duration // 60)}:{int(duration % 60):02d}",  # Формат мм:сс
                "answers_by_section": {},
                "detailed_answers": {}
            }
            
            # Группируем ответы по разделам ПДД
            section_stats = {}
            for q_id, is_correct in answers.items():
                if q_id in questions_data:
                    q_section = questions_data[q_id].get("section", "Неизвестный раздел")
                    
                    if q_section not in section_stats:
                        section_stats[q_section] = {"correct": 0, "total": 0}
                    
                    section_stats[q_section]["total"] += 1
                    if is_correct:
                        section_stats[q_section]["correct"] += 1
                    
                    # Детальная информация по каждому вопросу
                    detailed_results[participant_id]["detailed_answers"][q_id] = {
                        "is_correct": is_correct,
                        "question_text": questions_data[q_id].get("text", ""),
                        "section": q_section,
                        "categories": questions_data[q_id].get("category", [])
                    }
            
            # Добавляем процент правильных ответов по каждому разделу
            for section, stats in section_stats.items():
                stats["percentage"] = round((stats["correct"] / stats["total"] * 100), 2) if stats["total"] > 0 else 0
            
            detailed_results[participant_id]["answers_by_section"] = section_stats
            
            # Сохраняем запись об истории прохождения в коллекцию History
            try:
                history_record = {
                    "user_id": participant_id,
                    "lobby_id": lobby_id,
                    "date": datetime.utcnow(),
                    "score": correct_count,
                    "total": total_questions,
                    "categories": lobby.get("categories", []),
                    "sections": lobby.get("sections", []),
                    "mode": lobby.get("mode", "solo"),
                    "pass_percentage": (correct_count / total_questions * 100) if total_questions > 0 else 0,
                    "duration_seconds": duration,
                    "is_passed": correct_count >= int(total_questions * 0.8),  # 80% правильных для прохождения
                    "detailed_results": detailed_results[participant_id]
                }
                await db.history.insert_one(history_record)
            except Exception as e:
                # Логируем ошибку, но не прерываем выполнение для остальных участников
                print(f"Error saving history for user {participant_id}: {str(e)}")
        
        # Оповещаем участников о завершении и сообщаем результаты
        try:
            # Отправляем базовые результаты через WebSocket
            await ws_manager.send_json(lobby_id, {
                "type": "finished",
                "data": results
            })

            # Отправляем детальные результаты через отдельное WebSocket сообщение
            await ws_manager.send_json(lobby_id, {
                "type": "detailed_results",
                "data": detailed_results
            })

        except Exception as e:
            print(f"Error sending WebSocket notification: {str(e)}")
        
        return success(data={
            "status": "finished", 
            "results": results,
            "detailed_results": detailed_results,
            "duration_seconds": duration,
            "duration_formatted": f"{int(duration // 60)}:{int(duration % 60):02d}"
        })
    except HTTPException:
        # Пропускаем HTTP исключения дальше
        raise
    except Exception as e:
        # Логируем неожиданные ошибки
        print(f"Unexpected error finishing lobby {lobby_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при завершении теста")

@router.get("/lobbies/{lobby_id}", summary="Получить информацию о лобби")
async def get_lobby(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """
    Получает информацию о лобби по его ID.
    """
    user_id = get_user_id(current_user)
    logger.info(f"Запрос информации о лобби {lobby_id} от пользователя {user_id}")
    
    try:
        # Получаем информацию о лобби
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.error(f"Лобби {lobby_id} не найдено")
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем, является ли пользователь участником лобби
        if user_id not in lobby["participants"]:
            logger.warning(f"Пользователь {user_id} не является участником лобби {lobby_id}")
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        # Получаем информацию о создателе лобби
        host_user = await db.users.find_one({"_id": ObjectId(lobby["host_id"])})
        host_name = host_user.get("full_name", "Неизвестный пользователь") if host_user else "Неизвестный пользователь"
        
        # Calculate remaining time if lobby is active
        remaining_seconds = 0
        if lobby["status"] == "in_progress" and lobby.get("created_at"):
            lobby_age = (datetime.utcnow() - lobby["created_at"]).total_seconds()
            remaining_seconds = max(0, MAX_LOBBY_LIFETIME - lobby_age)
        
        # Формируем ответ
        response_data = {
            "id": str(lobby["_id"]),
            "host_id": lobby["host_id"],
            "host_name": host_name,
            "is_host": lobby["host_id"] == user_id,
            "current_user_id": user_id,
            "status": lobby["status"],
            "participants_count": len(lobby["participants"]),
            "created_at": lobby["created_at"].isoformat() if isinstance(lobby["created_at"], datetime) else str(lobby["created_at"]),
            "mode": lobby["mode"],
            "categories": lobby["categories"],
            "sections": lobby["sections"],
            "exam_mode": lobby.get("exam_mode", False),
            "question_ids": lobby.get("question_ids", []),
            "remaining_seconds": int(remaining_seconds)
        }
        
        logger.info(f"Возвращена информация о лобби {lobby_id}")
        return success(data=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении информации о лобби {lobby_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.get("/lobbies/{lobby_id}/answered-users", summary="Получить список пользователей, ответивших на текущий вопрос")
async def get_answered_users(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Возвращает список пользователей, которые ответили на текущий вопрос и их результаты.
    Доступно только для хоста лобби.
    """
    user_id = get_user_id(current_user)
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Только хост имеет доступ к этой информации")
        
        if lobby["status"] != "in_progress":
            raise HTTPException(status_code=400, detail="Тест не запущен")
        
        current_index = lobby.get("current_index", 0)
        if current_index >= len(lobby["question_ids"]):
            raise HTTPException(status_code=400, detail="Недопустимый индекс текущего вопроса")
            
        current_question_id = lobby["question_ids"][current_index]
        
        # Собираем информацию о том, кто ответил
        answered_users = []
        not_answered_users = []
        
        for participant_id in lobby["participants"]:
            user_data = {
                "user_id": participant_id,
                "is_host": participant_id == lobby["host_id"]
            }
            
            if current_question_id in lobby.get("participants_answers", {}).get(participant_id, {}):
                is_correct = lobby["participants_answers"][participant_id][current_question_id]
                user_data["is_correct"] = is_correct
                answered_users.append(user_data)
            else:
                not_answered_users.append(user_data)
        
        # Проверяем, все ли ответили
        all_answered = len(not_answered_users) == 0
        
        return success(data={
            "current_question_id": current_question_id,
            "current_index": current_index,
            "total_questions": len(lobby["question_ids"]),
            "answered_users": answered_users,
            "not_answered_users": not_answered_users,
            "all_answered": all_answered
        })
    except HTTPException:
        # Пропускаем HTTP исключения дальше
        raise
    except Exception as e:
        # Логируем неожиданные ошибки
        print(f"Error getting answered users for lobby {lobby_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при получении данных")

@router.get("/lobbies/{lobby_id}/results", summary="Получить подробные результаты теста")
async def get_test_results(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Возвращает подробные результаты теста для завершенного лобби.
    Включает:
    - Общую статистику
    - Результаты по разделам ПДД
    - Детальную информацию по каждому вопросу
    - Сравнение с другими участниками (для multi режима)
    """
    user_id = get_user_id(current_user)
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Пользователь должен быть участником этого лобби
        if user_id not in lobby["participants"]:
            raise HTTPException(status_code=403, detail="Вы не участник данного лобби")
        
        # Тест должен быть завершен
        if lobby["status"] != "finished":
            raise HTTPException(status_code=400, detail="Тест еще не завершен")
        
        # Вычисляем продолжительность теста
        start_time = lobby.get("created_at", datetime.utcnow())
        end_time = lobby.get("finished_at", datetime.utcnow())
        duration = (end_time - start_time).total_seconds()
        
        total_questions = len(lobby.get("question_ids", []))
        
        # Получаем информацию о всех вопросах
        questions_data = {}
        for q_id in lobby.get("question_ids", []):
            question = await db.questions.find_one({"_id": ObjectId(q_id)})
            if question:
                questions_data[q_id] = {
                    "text": question.get("question_text", ""),
                    "section": question.get("pdd_section", ""),
                    "categories": question.get("categories", []),
                    "correct_answer": chr(ord('A') + lobby["correct_answers"].get(q_id, 0))
                }
        
        # Собираем результаты пользователя
        user_answers = lobby.get("participants_answers", {}).get(user_id, {})
        correct_count = sum(1 for is_corr in user_answers.values() if is_corr)
        incorrect_count = sum(1 for is_corr in user_answers.values() if not is_corr)
        answered_count = len(user_answers)
        not_answered_count = total_questions - answered_count
        
        # Детальная статистика пользователя
        user_result = {
            "user_id": user_id,
            "is_host": user_id == lobby["host_id"],
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "answered_count": answered_count,
            "not_answered_count": not_answered_count,
            "total_questions": total_questions,
            "passing_score": correct_count >= int(total_questions * 0.8),  # 80% правильных для прохождения
            "percentage": round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0,
            "duration_seconds": duration,
            "duration_formatted": f"{int(duration // 60)}:{int(duration % 60):02d}",  # Формат мм:сс
            "detailed_answers": []
        }
        
        # Группируем ответы по разделам ПДД
        section_stats = {}
        for q_id, is_correct in user_answers.items():
            if q_id in questions_data:
                q_section = questions_data[q_id].get("section", "Неизвестный раздел")
                
                if q_section not in section_stats:
                    section_stats[q_section] = {"correct": 0, "total": 0, "questions": []}
                
                section_stats[q_section]["total"] += 1
                if is_correct:
                    section_stats[q_section]["correct"] += 1
                
                # Детальная информация по каждому вопросу
                q_data = {
                    "question_id": q_id,
                    "question_text": questions_data[q_id].get("text", ""),
                    "section": q_section,
                    "categories": questions_data[q_id].get("category", []),
                    "is_correct": is_correct,
                    "correct_answer": questions_data[q_id].get("correct_answer", "А")
                }
                
                user_result["detailed_answers"].append(q_data)
                section_stats[q_section]["questions"].append(q_id)
        
        # Добавляем процент правильных ответов по каждому разделу
        sections_result = []
        for section, stats in section_stats.items():
            stats["percentage"] = round((stats["correct"] / stats["total"] * 100), 2) if stats["total"] > 0 else 0
            sections_result.append({
                "section": section,
                "correct": stats["correct"],
                "total": stats["total"],
                "percentage": stats["percentage"],
                "questions": stats["questions"]
            })
        
        user_result["sections"] = sections_result
        
        # Собираем сводную статистику по всем участникам (только основные метрики)
        all_participants = []
        for p_id, p_answers in lobby.get("participants_answers", {}).items():
            p_correct = sum(1 for is_corr in p_answers.values() if is_corr)
            all_participants.append({
                "user_id": p_id,
                "is_host": p_id == lobby["host_id"],
                "is_current_user": p_id == user_id,
                "correct_count": p_correct,
                "total": total_questions,
                "percentage": round((p_correct / total_questions * 100), 2) if total_questions > 0 else 0
            })
        
        # Сортируем участников по количеству правильных ответов
        all_participants.sort(key=lambda x: x["correct_count"], reverse=True)
        
        # Определяем место пользователя среди всех участников
        user_rank = next((idx + 1 for idx, p in enumerate(all_participants) if p["user_id"] == user_id), 0)
        
        # Определяем лучшие и худшие разделы
        if sections_result:
            best_section = max(sections_result, key=lambda x: x["percentage"] if x["total"] > 0 else 0)
            worst_section = min(sections_result, key=lambda x: x["percentage"] if x["total"] > 0 else 100)
            
            user_result["best_section"] = best_section
            user_result["worst_section"] = worst_section
        
        return success(data={
            "user_result": user_result,
            "all_participants": all_participants,
            "user_rank": user_rank,
            "total_participants": len(all_participants),
            "mode": lobby["mode"],
            "categories": lobby.get("categories", []),
            "sections": lobby.get("sections", []),
            "duration_seconds": duration,
            "duration_formatted": f"{int(duration // 60)}:{int(duration % 60):02d}",
            "test_completed": user_result["answered_count"] == total_questions
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting test results for lobby {lobby_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при получении результатов теста")

@router.get("/active-lobby", summary="Получить информацию об активном лобби пользователя")
async def get_user_active_lobby(current_user: dict = Depends(get_current_actor)):
    """
    Проверяет, есть ли у пользователя активное лобби, и возвращает информацию о нем
    """
    user_id = get_user_id(current_user)
    logger.info(f"Проверка активного лобби для пользователя {user_id}")
    
    try:
        # Ищем активное лобби пользователя
        active_lobby = await db.lobbies.find_one({
            "participants": user_id,
            "status": {"$ne": "finished"}
        })
        
        if not active_lobby:
            logger.info(f"У пользователя {user_id} нет активных лобби")
            return success(data={"has_active_lobby": False})
        
        # Проверяем, не истёк ли срок действия лобби (6 часов)
        if active_lobby.get("created_at"):
            lobby_age = (datetime.utcnow() - active_lobby["created_at"]).total_seconds()
            if lobby_age > MAX_LOBBY_LIFETIME:
                # Автоматически завершаем просроченное лобби
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
            
            # Лобби активно и не просрочено
            remaining_seconds = MAX_LOBBY_LIFETIME - lobby_age
            
            # Получаем имя хоста
            host_user = await db.users.find_one({"_id": ObjectId(active_lobby["host_id"])})
            host_name = host_user.get("full_name", "Неизвестный пользователь") if host_user else "Неизвестный пользователь"
            
            # Возвращаем информацию об активном лобби
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
        
        # Если по какой-то причине нет created_at, просто возвращаем базовую информацию
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
    """
    Возвращает статистику по категориям и количеству вопросов в каждой.
    
    Группирует вопросы по категориям и подсчитывает количество уникальных вопросов в каждой группе.
    Также возвращает общее количество вопросов.
    """
    user_id = get_user_id(current_user)
    logger.info(f"Пользователь {user_id} запрашивает статистику по категориям")
    
    try:
        # Агрегация для подсчета вопросов по категориям
        pipeline = [
            # Фильтруем только неудаленные вопросы
            {"$match": {"deleted": False}},
            # Разворачиваем массив категорий
            {"$unwind": "$categories"},
            # Группируем по категориям и считаем количество
            {"$group": {
                "_id": "$categories",
                "count": {"$sum": 1}
            }},
            # Сортируем по названию категории
            {"$sort": {"_id": 1}}
        ]
        
        category_stats = await db.questions.aggregate(pipeline).to_list(None)
        
        # Получаем общее количество вопросов
        total_questions = await db.questions.count_documents({"deleted": False})
        
        # Преобразуем результат в удобный формат
        categories_dict = {}
        for stat in category_stats:
            categories_dict[stat["_id"]] = stat["count"]
        
        logger.info(f"Статистика по категориям: {categories_dict}, общее количество: {total_questions}")
        
        # Определяем группы категорий для подсчета уникальных вопросов
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
        
        # Считаем уникальные вопросы для каждой группы
        grouped_categories = []
        for group in category_groups:
            # Считаем уникальные вопросы, которые содержат хотя бы одну из категорий группы
            unique_questions_count = await db.questions.count_documents({
                "deleted": False,
                "categories": {"$in": group["categories"]}
            })
            
            # Создаем breakdown для каждой категории в группе
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
