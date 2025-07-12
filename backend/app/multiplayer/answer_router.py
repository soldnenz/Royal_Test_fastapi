from fastapi import APIRouter, HTTPException, Depends, Request
from app.db.database import db
from datetime import datetime, timedelta
from app.core.security import get_current_actor
from app.core.response import success
from bson import ObjectId
from pydantic import BaseModel, validator
from app.logging import get_logger, LogSection, LogSubsection
import asyncio
from typing import Optional, List
from app.rate_limit import rate_limit_ip
from app.multiplayer.lobby_utils import get_user_id, get_lobby_from_db, get_user_subscription_from_db
from app.multiplayer.lobby_validator import check_active_session, validate_user_subscription
import re

logger = get_logger(__name__)
router = APIRouter()

# Константы
MAX_LOBBY_LIFETIME = 4 * 60 * 60  # 4 часа

class AnswerRequest(BaseModel):
    question_id: str
    answer_index: int  # Индекс выбранного ответа (0, 1, 2, 3, ...)
    
    @validator('question_id')
    def validate_question_id(cls, v):
        if not v:
            raise ValueError('Question ID is required')
        return v
    
    @validator('answer_index')
    def validate_answer_index(cls, v):
        if v < 0:
            raise ValueError('Answer index must be non-negative')
        return v

@router.post("/lobbies/{lobby_id}/answer", summary="Ответить на текущий вопрос")
@rate_limit_ip("lobby_answer", max_requests=30, window_seconds=60)
async def submit_answer(
    lobby_id: str,
    answer_data: AnswerRequest,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Отправляет ответ на текущий вопрос лобби.
    Проверяет, что вопрос является текущим и пользователь участвует в лобби.
    Сохраняет ответ в participants_answers и participants_raw_answers.
    """
    user_id = get_user_id(current_user)
    question_id = answer_data.question_id
    answer_index = answer_data.answer_index
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ANSWERS,
        message=f"Попытка ответа: пользователь {user_id} отвечает на вопрос {question_id} в лобби {lobby_id}, ответ: {answer_index}"
    )
    
    try:
        # Получаем лобби
        lobby = await get_lobby_from_db(lobby_id)
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем участие пользователя
        if user_id not in lobby.get("participants", []):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Попытка ответа не-участником: пользователь {user_id} пытается ответить в лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        # Проверяем статус лобби
        if lobby["status"] != "in_progress":
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ANSWERS,
                message=f"Попытка ответа в неактивном лобби: лобби {lobby_id}, статус {lobby['status']}"
            )
            raise HTTPException(status_code=400, detail="Лобби не в статусе выполнения теста")
        
        # Получаем текущий индекс и ID вопроса
        current_index = lobby.get("current_index", 0)
        question_ids = lobby.get("question_ids", [])
        
        if not question_ids:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ANSWERS,
                message=f"Нет вопросов в лобби {lobby_id}"
            )
            raise HTTPException(status_code=400, detail="В лобби нет вопросов")
        
        if current_index >= len(question_ids):
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ANSWERS,
                message=f"Текущий индекс {current_index} превышает количество вопросов {len(question_ids)} в лобби {lobby_id}"
            )
            raise HTTPException(status_code=400, detail="Тест завершен")
        
        current_question_id = question_ids[current_index]
        
        # Проверяем, что отвечают на текущий вопрос
        if question_id != current_question_id:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ANSWERS,
                message=f"Попытка ответа на неправильный вопрос: пользователь {user_id} отвечает на {question_id}, текущий {current_question_id} в лобби {lobby_id}"
            )
            raise HTTPException(status_code=400, detail="Можно отвечать только на текущий вопрос")
        
        # Получаем вопрос из базы данных для проверки правильности
        question = await db.questions.find_one({"_id": current_question_id})
        if not question:
            # Пробуем как ObjectId
            try:
                question = await db.questions.find_one({"_id": ObjectId(current_question_id)})
            except:
                pass
        
        if not question:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ANSWERS,
                message=f"Вопрос {current_question_id} не найден в базе данных"
            )
            raise HTTPException(status_code=404, detail="Вопрос не найден")
        
        # Проверяем валидность индекса ответа
        options = question.get("options", [])
        if answer_index >= len(options):
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ANSWERS,
                message=f"Неверный индекс ответа: пользователь {user_id} выбрал {answer_index}, доступно {len(options)} в лобби {lobby_id}"
            )
            raise HTTPException(status_code=400, detail="Неверный индекс ответа")
        
        # Проверяем правильность ответа
        correct_answer_index = question.get("correct_answer_index", 0)
        is_correct = answer_index == correct_answer_index
        
        # Получаем текущие ответы участников
        participants_answers = lobby.get("participants_answers", {})
        participants_raw_answers = lobby.get("participants_raw_answers", {})
        
        # Инициализируем структуры для текущего вопроса, если их нет
        if current_question_id not in participants_answers:
            participants_answers[current_question_id] = {}
        if current_question_id not in participants_raw_answers:
            participants_raw_answers[current_question_id] = {}
        
        # Проверяем, не отвечал ли пользователь уже на этот вопрос
        if user_id in participants_answers[current_question_id]:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ANSWERS,
                message=f"Попытка повторного ответа: пользователь {user_id} уже отвечал на вопрос {current_question_id} в лобби {lobby_id}"
            )
            raise HTTPException(status_code=400, detail="Вы уже отвечали на этот вопрос")
        
        # Сохраняем ответ пользователя
        participants_answers[current_question_id][user_id] = is_correct
        participants_raw_answers[current_question_id][user_id] = answer_index
        
        # Обновляем лобби с новыми ответами
        update_data = {
            "participants_answers": participants_answers,
            "participants_raw_answers": participants_raw_answers
        }
        
        result = await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ANSWERS,
                message=f"Не удалось сохранить ответ в лобби {lobby_id}"
            )
            raise HTTPException(status_code=500, detail="Не удалось сохранить ответ")
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ANSWERS,
            message=f"Ответ сохранен: пользователь {user_id} ответил на вопрос {current_question_id} в лобби {lobby_id}, ответ: {answer_index}, правильный: {is_correct}"
        )
        
        return success(data={
            "lobby_id": lobby_id,
            "question_id": current_question_id,
            "answer_index": answer_index,
            "message": "Ответ успешно сохранен"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка сохранения ответа: лобби {lobby_id}, пользователь {user_id}, вопрос {question_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при сохранении ответа")


@router.get("/lobbies/{lobby_id}/current-answers", summary="Получить ответы на текущий вопрос")
@rate_limit_ip("lobby_current_answers", max_requests=30, window_seconds=60)
async def get_current_question_answers(
    lobby_id: str,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Возвращает ответы всех участников на текущий вопрос лобби.
    """
    user_id = get_user_id(current_user)
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ANSWERS,
        message=f"Запрос ответов на текущий вопрос: пользователь {user_id} запрашивает ответы в лобби {lobby_id}"
    )
    
    try:
        # Получаем лобби
        lobby = await get_lobby_from_db(lobby_id)
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем участие пользователя
        if user_id not in lobby.get("participants", []):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Попытка получения ответов не-участником: пользователь {user_id} пытается получить ответы лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        # Проверяем статус лобби
        if lobby["status"] != "in_progress":
            raise HTTPException(status_code=400, detail="Лобби не в статусе выполнения теста")
        
        # Получаем текущий вопрос
        current_index = lobby.get("current_index", 0)
        question_ids = lobby.get("question_ids", [])
        
        if current_index >= len(question_ids):
            raise HTTPException(status_code=400, detail="Тест завершен")
        
        current_question_id = question_ids[current_index]
        
        # Получаем ответы на текущий вопрос
        participants_answers = lobby.get("participants_answers", {}).get(current_question_id, {})
        participants_raw_answers = lobby.get("participants_raw_answers", {}).get(current_question_id, {})
        
        # Получаем информацию о вопросе
        question = await db.questions.find_one({"_id": current_question_id})
        if not question:
            try:
                question = await db.questions.find_one({"_id": ObjectId(current_question_id)})
            except:
                pass
        
        if not question:
            raise HTTPException(status_code=404, detail="Текущий вопрос не найден")
        
        # Проверяем флаг показа ответов в лобби
        show_answers = lobby.get("show_answers", False)
        
        # Если флаг показа ответов выключен, возвращаем ошибку
        if not show_answers:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ANSWERS,
                message=f"Попытка получения ответов при выключенном флаге: пользователь {user_id} пытается получить ответы в лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Хост еще не разрешил показывать ответы")
        
        # Получаем ответ пользователя на текущий вопрос
        user_answer_index = participants_raw_answers.get(user_id, None)
        
        # Подготавливаем данные ответов
        answers_data = {
            "question_id": current_question_id,
            "lobby_id": lobby_id,
            "current_index": current_index,
            "participants_answers": participants_answers,
            "participants_raw_answers": participants_raw_answers,
            "total_participants": len(lobby.get("participants", [])),
            "answered_participants": len(participants_answers),
            "show_answers": show_answers,
            "correct_answer_index": question.get("correct_answer_index", 0),
            "explanation": question.get("explanation", ""),
            "user_answer_index": user_answer_index,  # null если пользователь не отвечал
            "user_is_correct": participants_answers.get(user_id, None)  # null если пользователь не отвечал
        }
        
        # Добавляем статистику ответов
        correct_count = sum(1 for is_correct in participants_answers.values() if is_correct)
        answers_data["correct_answers"] = correct_count
        answers_data["incorrect_answers"] = len(participants_answers) - correct_count
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ANSWERS,
            message=f"Предоставлены ответы на текущий вопрос {current_question_id} в лобби {lobby_id}, участников ответило: {len(participants_answers)}, показать ответы: {show_answers}"
        )
        
        return success(data=answers_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения ответов на текущий вопрос: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при получении ответов") 