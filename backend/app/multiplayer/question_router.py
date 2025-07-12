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

class ToggleAnswersRequest(BaseModel):
    show_answers: bool

@router.get("/lobbies/{lobby_id}/current-question", summary="Получить текущий вопрос лобби")
@rate_limit_ip("lobby_current_question", max_requests=60, window_seconds=60)
async def get_current_question(
    lobby_id: str,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Возвращает текущий вопрос лобби.
    Получает ID текущего вопроса из лобби и возвращает полную информацию о вопросе.
    """
    user_id = get_user_id(current_user)
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.QUESTIONS,
        message=f"Запрос текущего вопроса: пользователь {user_id} запрашивает текущий вопрос лобби {lobby_id}"
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
                message=f"Попытка доступа к вопросу не-участником: пользователь {user_id} пытается получить вопрос лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        # Проверяем статус лобби
        if lobby["status"] != "in_progress":
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Попытка получить вопрос в неактивном лобби: лобби {lobby_id}, статус {lobby['status']}"
            )
            raise HTTPException(status_code=400, detail="Лобби не в статусе выполнения теста")
        
        # Получаем текущий индекс и ID вопроса
        current_index = lobby.get("current_index", 0)
        question_ids = lobby.get("question_ids", [])
        
        if not question_ids:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Нет вопросов в лобби {lobby_id}"
            )
            raise HTTPException(status_code=400, detail="В лобби нет вопросов")
        
        if current_index >= len(question_ids):
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Текущий индекс {current_index} превышает количество вопросов {len(question_ids)} в лобби {lobby_id}"
            )
            raise HTTPException(status_code=400, detail="Тест завершен")
        
        current_question_id = question_ids[current_index]
        
        # Получаем вопрос из базы данных
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
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Вопрос {current_question_id} не найден в базе данных"
            )
            raise HTTPException(status_code=404, detail="Вопрос не найден")
        
        # Проверяем, нужно ли показывать ответы
        show_answers = lobby.get("show_answers", False)
        
        # Получаем ответ пользователя на текущий вопрос
        participants_raw_answers = lobby.get("participants_raw_answers", {})
        user_answer_index = participants_raw_answers.get(current_question_id, {}).get(user_id, None)
        
        # Проверяем наличие дополнительного медиа
        has_after_answer_media = question.get("has_after_answer_media", False)
        after_answer_media_file_id = question.get("after_answer_media_file_id")
        after_answer_media_id = question.get("after_answer_media_id")
        
        # Если есть ID файла, но флаг не установлен, устанавливаем его
        if (after_answer_media_file_id or after_answer_media_id) and not has_after_answer_media:
            has_after_answer_media = True
        
        # Подготавливаем данные вопроса
        question_data = {
            "_id": str(question["_id"]),
            "question_text": question.get("question_text", {}),
            "answers": [option["text"] for option in question.get("options", [])],
            "has_media": question.get("has_media", False),
            "media_filename": question.get("media_filename"),
            "has_after_answer_media": has_after_answer_media,
            "after_answer_media_filename": question.get("after_answer_media_filename"),
            "after_answer_media_file_id": after_answer_media_file_id,
            "after_answer_media_id": after_answer_media_id,
            "current_index": current_index,
            "total_questions": len(question_ids),
            "lobby_id": lobby_id,
            "show_answers": show_answers,  # Флаг показа ответов из лобби
            "user_answer_index": user_answer_index  # Индекс ответа пользователя (null если не отвечал)
        }
        
        # Если ответы должны быть показаны, добавляем правильный ответ
        if show_answers:
            question_data["correct_answer_index"] = question.get("correct_answer_index")
        
        # В режиме экзамена убираем чувствительные данные
        if lobby.get("exam_mode", False):
            question_data.pop("correct_answer_index", None)
            question_data["exam_mode"] = True
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Предоставлен текущий вопрос {current_question_id} пользователю {user_id} в лобби {lobby_id}, индекс {current_index}, показывать ответы: {show_answers}, has_after_answer_media: {question.get('has_after_answer_media', False)}"
        )
        
        return success(data=question_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения текущего вопроса: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при получении текущего вопроса")

@router.post("/lobbies/{lobby_id}/toggle-answers", summary="Переключить показ ответов (только хост)")
@rate_limit_ip("lobby_toggle_answers", max_requests=10, window_seconds=60)
async def toggle_answers(
    lobby_id: str,
    toggle_data: ToggleAnswersRequest,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Устанавливает показ ответов в лобби.
    Только хост может управлять показом ответов.
    """
    user_id = get_user_id(current_user)
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.QUESTIONS,
        message=f"Попытка установки показа ответов: пользователь {user_id} пытается установить показ ответов {toggle_data.show_answers} в лобби {lobby_id}"
    )
    
    try:
        # Получаем лобби
        lobby = await get_lobby_from_db(lobby_id)
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем, что пользователь является хостом
        if lobby.get("host_id") != user_id:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Попытка установки ответов не-хостом: пользователь {user_id} пытается установить ответы в лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Только хост может управлять показом ответов")
        
        # Проверяем статус лобби
        if lobby["status"] != "in_progress":
            raise HTTPException(status_code=400, detail="Лобби не в статусе выполнения теста")
        
        # Проверяем текущее состояние флага показа ответов
        current_show_answers = lobby.get("show_answers", False)
        
        # Если пытаются установить то же состояние, возвращаем ошибку
        if current_show_answers == toggle_data.show_answers:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Попытка установки того же состояния ответов: лобби {lobby_id}, хост {user_id}, текущее: {current_show_answers}, запрашиваемое: {toggle_data.show_answers}"
            )
            raise HTTPException(status_code=400, detail=f"Показ ответов уже {'включен' if current_show_answers else 'выключен'}")
        
        # Устанавливаем флаг показа ответов
        new_show_answers = toggle_data.show_answers
        
        # Обновляем лобби
        result = await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": {"show_answers": new_show_answers}}
        )
        
        if result.modified_count == 0:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Не удалось обновить показ ответов в лобби {lobby_id}"
            )
            raise HTTPException(status_code=500, detail="Не удалось обновить показ ответов")
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Показ ответов установлен: лобби {lobby_id}, хост {user_id}, новое состояние: {new_show_answers}"
        )
        
        return success(data={
            "lobby_id": lobby_id,
            "show_answers": new_show_answers,
            "message": f"Показ ответов {'включен' if new_show_answers else 'выключен'}"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка установки ответов: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при установке ответов")

@router.get("/lobbies/{lobby_id}/question/{question_id}", summary="Получить конкретный вопрос лобби")
@rate_limit_ip("lobby_specific_question", max_requests=60, window_seconds=60)
async def get_specific_question(
    lobby_id: str,
    question_id: str,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Возвращает конкретный вопрос лобби по ID.
    Проверяет, что вопрос принадлежит лобби.
    """
    user_id = get_user_id(current_user)
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.QUESTIONS,
        message=f"Запрос конкретного вопроса: пользователь {user_id} запрашивает вопрос {question_id} в лобби {lobby_id}"
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
                message=f"Попытка доступа к вопросу не-участником: пользователь {user_id} пытается получить вопрос {question_id} в лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        # Проверяем, что вопрос принадлежит лобби
        question_ids = lobby.get("question_ids", [])
        if question_id not in question_ids:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Попытка доступа к чужому вопросу: пользователь {user_id} пытается получить вопрос {question_id} в лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вопрос не принадлежит этому лобби")
        
        # Получаем вопрос из базы данных
        question = await db.questions.find_one({"_id": question_id})
        if not question:
            # Пробуем как ObjectId
            try:
                question = await db.questions.find_one({"_id": ObjectId(question_id)})
            except:
                pass
        
        if not question:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Вопрос {question_id} не найден в базе данных"
            )
            raise HTTPException(status_code=404, detail="Вопрос не найден")
        
        # Проверяем, нужно ли показывать ответы
        show_answers = lobby.get("show_answers", False)
        
        # Получаем ответ пользователя на этот вопрос
        participants_raw_answers = lobby.get("participants_raw_answers", {})
        user_answer_index = participants_raw_answers.get(question_id, {}).get(user_id, None)
        
        # Проверяем наличие дополнительного медиа
        has_after_answer_media = question.get("has_after_answer_media", False)
        after_answer_media_file_id = question.get("after_answer_media_file_id")
        after_answer_media_id = question.get("after_answer_media_id")
        
        # Если есть ID файла, но флаг не установлен, устанавливаем его
        if (after_answer_media_file_id or after_answer_media_id) and not has_after_answer_media:
            has_after_answer_media = True
        
        # Подготавливаем данные вопроса
        question_data = {
            "_id": str(question["_id"]),
            "question_text": question.get("question_text", {}),
            "answers": [option["text"] for option in question.get("options", [])],
            "has_media": question.get("has_media", False),
            "media_filename": question.get("media_filename"),
            "has_after_answer_media": has_after_answer_media,
            "after_answer_media_filename": question.get("after_answer_media_filename"),
            "after_answer_media_file_id": after_answer_media_file_id,
            "after_answer_media_id": after_answer_media_id,
            "lobby_id": lobby_id,
            "show_answers": show_answers,  # Флаг показа ответов из лобби
            "user_answer_index": user_answer_index  # Индекс ответа пользователя (null если не отвечал)
        }
        
        # Если ответы должны быть показаны, добавляем правильный ответ
        if show_answers:
            question_data["correct_answer_index"] = question.get("correct_answer_index")
        
        # В режиме экзамена убираем чувствительные данные
        if lobby.get("exam_mode", False):
            question_data.pop("correct_answer_index", None)
            question_data["exam_mode"] = True
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Предоставлен конкретный вопрос {question_id} пользователю {user_id} в лобби {lobby_id}, показывать ответы: {show_answers}, has_after_answer_media: {question.get('has_after_answer_media', False)}"
        )
        
        return success(data=question_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения конкретного вопроса: лобби {lobby_id}, вопрос {question_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при получении вопроса") 