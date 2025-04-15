# app/routers/lobby.py (фрагмент)
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from app.db.database import db  # предположим, db - это подключение к Mongo (AsyncIOMotorDatabase)
from app.utils.id_generator import generate_unique_lobby_id
from datetime import datetime
from app.core.security import get_current_actor
from app.core.response import success
from app.websocket.lobby_ws import ws_manager
from bson import ObjectId
import json
from pydantic import BaseModel
import logging

# Настройка логгера
logger = logging.getLogger(__name__)

class AnswerSubmit(BaseModel):
    question_id: str
    answer_index: int

class LobbyCreate(BaseModel):
    mode: str = "solo"  # По умолчанию solo
    categories: list[str] = None
    pdd_section_uids: list[str] | None = None
    questions_count: int = 40

router = APIRouter()

def get_user_id(current_user):
    """
    Извлекает ID пользователя из объекта, возвращаемого get_current_actor
    """
    return str(current_user["id"])

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
    
    # Принудительно установим количество вопросов в 40
    questions_count = 40
    
    # Проверка активных тестов пользователя
    active_lobby = await db.lobbies.find_one({
        "participants": user_id,
        "status": {"$ne": "finished"}
    })
    if active_lobby:
        logger.warning(f"Пользователь {user_id} уже имеет активный тест: {active_lobby['_id']}")
        raise HTTPException(
            status_code=400, 
            detail="У вас уже есть активный тест. Завершите его перед началом нового."
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
    
    # Обрабатываем разделы ПДД (доступно для School и Royal)
    if lobby_data.pdd_section_uids is not None and subscription_type not in ["School"]:
        logger.warning(f"Отказ в выборе разделов ПДД пользователю {user_id} с подпиской {subscription_type}")
        raise HTTPException(
            status_code=403,
            detail="Выбор разделов ПДД доступен только для подписки School"
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
        # Vip может выбирать любые категории
        lobby_data.pdd_section_uids = None  # но не может выбирать разделы
        logger.info(f"VIP подписка, разделы ПДД отключены")
        
    # Построение фильтра для запроса вопросов
    query = {"deleted": False}
    
    if lobby_data.categories:
        query["categories"] = {"$in": lobby_data.categories}
        
    if lobby_data.pdd_section_uids and subscription_type in ["Royal", "School"]:
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
    for q in questions:
        correct_label = q["correct_label"]
        correct_index = ord(correct_label) - ord('A')
        correct_answers_map[str(q["_id"])] = correct_index

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
        "participants": [user_id],
        "participants_answers": {user_id: {}},
        "current_index": 0,
        "created_at": datetime.utcnow(),
        "sections": lobby_data.pdd_section_uids or [],
        "categories": lobby_data.categories or [],
        "mode": lobby_data.mode,
        "subscription_type": subscription_type
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
            "auto_started": lobby_data.mode == "solo"
        })
    except Exception as e:
        # Логируем ошибку
        logger.error(f"Ошибка при создании лобби: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при создании лобби")


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
    - Запрашиваемый вопрос должен быть частью теста этого лобби
    """
    user_id = get_user_id(current_user)
    
    # Получаем данные о лобби
    lobby = await db.lobbies.find_one({"_id": lobby_id})
    if not lobby:
        raise HTTPException(status_code=404, detail="Лобби не найдено")
    
    # Проверяем, что пользователь участник лобби
    if user_id not in lobby["participants"]:
        raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
    
    # Проверяем статус лобби - должен быть "in_progress"
    if lobby["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Тест не активен. Статус лобби должен быть 'in_progress'")
    
    # Проверяем, что запрашиваемый вопрос входит в список вопросов лобби
    if question_id not in lobby["question_ids"]:
        raise HTTPException(status_code=403, detail="Запрашиваемый вопрос не является частью этого теста")

    # Запрашиваем вопрос из коллекции вопросов
    question = await db.questions.find_one({"_id": ObjectId(question_id)})
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    
    # Проверяем, отвечал ли уже пользователь на этот вопрос
    answer = await db.answers.find_one({"lobby_id": lobby_id, "user_id": user_id, "question_id": question_id})
    
    # Очищаем данные, не нужные клиенту
    question_out = {
        "id": str(question["_id"]),
        "text": question["question_text"],
        "options": question.get("options", []) if isinstance(question.get("options", []), list) else [],
        "media_file_id": str(question["media_file_id"]) if question.get("media_file_id") else None,
        "media_base64": question.get("media_base64"),  # Включаем base64 данные изображения, если они есть
        "media_filename": question.get("media_filename")
    }
    
    # Если пользователь уже ответил, добавляем объяснение
    if answer:
        question_out["explanation"] = question.get("explanation", "данный вопрос без объяснения")
    else:
        question_out["explanation"] = None  # Объяснение будет доступно только после ответа
    
    return success(data=question_out)

def get_user_id(current_user):
    return str(current_user["id"])

@router.get("/lobbies/{lobby_id}/correct-answer", summary="Получить индекс правильного ответа на вопрос (только хост)")
async def get_correct_answer(
    lobby_id: str,
    question_id: str = Query(..., description="ID вопроса"),
    current_user: dict = Depends(get_current_actor)
):
    user_id = get_user_id(current_user)

    lobby = await db.lobbies.find_one({"_id": lobby_id})
    if not lobby:
        raise HTTPException(status_code=404, detail="Лобби не найдено")

    if lobby["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Тест неактивен")

    if user_id not in lobby["participants"]:
        raise HTTPException(status_code=403, detail="Вы не участник этого лобби")

    if user_id != lobby["host_id"]:
        raise HTTPException(status_code=403, detail="Только хост может получить правильный ответ")

    if question_id not in lobby.get("question_ids", []):
        raise HTTPException(status_code=403, detail="Вопрос не относится к этому лобби")

    correct_index = lobby.get("correct_answers", {}).get(question_id)
    if correct_index is None:
        raise HTTPException(status_code=404, detail="Правильный ответ не найден")

    return success(data={"correct_index": correct_index})


@router.post("/lobbies/{lobby_id}/answer", summary="Отправить ответ на вопрос")
async def submit_answer(
    lobby_id: str,
    payload: AnswerSubmit,
    request: Request = None, 
    current_user: dict = Depends(get_current_actor)
):
    """
    Принимает ответ пользователя на вопрос и сохраняет его результат.
    Если все пользователи ответили на текущий вопрос, автоматически переходит к следующему.
    После ответа на все 40 вопросов, автоматически завершает тест.
    """
    user_id = get_user_id(current_user)
    question_id = payload.question_id
    answer_index = payload.answer_index
    # Проверки такие же, как и для получения вопроса
    lobby = await db.lobbies.find_one({"_id": lobby_id})
    if not lobby:
        raise HTTPException(status_code=404, detail="Лобби не найдено")
    if user_id not in lobby["participants"]:
        raise HTTPException(status_code=403, detail="Вы не участник данного лобби")
    if question_id not in lobby["question_ids"]:
        raise HTTPException(status_code=403, detail="Вопрос не относится к данному лобби")
    if lobby["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Лобби не активно")
    
    # Проверяем правильность ответа
    correct_answer = lobby["correct_answers"].get(question_id)
    if correct_answer is None:
        raise HTTPException(status_code=500, detail="Правильный ответ для данного вопроса не найден")
    
    is_correct = (answer_index == correct_answer)
    
    # Сохраняем ответ пользователя в коллекцию user_answers
    answer_doc = {
        "user_id": user_id,
        "lobby_id": lobby_id,
        "question_id": question_id,
        "answer": answer_index,
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
    await ws_manager.send_json(lobby_id, {
        "type": "answer_received",
        "data": {
            "user_id": user_id,
            "question_id": question_id,
            "is_correct": is_correct
        }
    })

    # Проверяем, все ли пользователи ответили на текущий вопрос
    lobby = await db.lobbies.find_one({"_id": lobby_id})
    current_index = lobby.get("current_index", 0)
    current_question_id = lobby["question_ids"][current_index]
    
    # Если это не тот вопрос, на который отвечаем сейчас (может быть запаздывающий ответ), не обрабатываем логику перехода
    if current_question_id != question_id:
        return success(data={"is_correct": is_correct})
    
    all_answered = True
    for participant_id in lobby["participants"]:
        # Проверяем, ответил ли участник на текущий вопрос
        if current_question_id not in lobby.get("participants_answers", {}).get(participant_id, {}):
            all_answered = False
            break
    
    # Если все участники ответили, переходим к следующему вопросу
    if all_answered:
        total_questions = len(lobby.get("question_ids", []))
        
        # Если это был последний вопрос (или уже достигли 40 вопросов), завершаем тест
        if current_index >= total_questions - 1 or current_index >= 39:  # 0-based index, 39 = 40 вопросов
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
            await ws_manager.send_json(lobby_id, {
                "type": "test_finished",
                "data": results
            })

        else:
            # Переходим к следующему вопросу
            new_index = current_index + 1
            await db.lobbies.update_one({"_id": lobby_id}, {"$set": {"current_index": new_index}})
            next_question_id = lobby["question_ids"][new_index]
            
            # Уведомляем всех о переходе к следующему вопросу
            await ws_manager.send_json(lobby_id, {
                "type": "next_question",
                "data": {"question_id": next_question_id}
            })

    question = await db.questions.find_one({"_id": ObjectId(question_id)})
    explanation = question.get("explanation", "N/A") if question else "N/A"
    correct_option_text = question["options"][correct_answer] if question and "options" in question and len(
        question["options"]) > correct_answer else "N/A"

    return success(data={
        "is_correct": is_correct,
        "correct_answer": correct_option_text,
        "explanation": explanation
    })


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
            "sections": lobby["sections"]
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
                    "categories": questions_data[q_id].get("categories", []),
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
