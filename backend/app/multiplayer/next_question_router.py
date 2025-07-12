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

class NextQuestionRequest(BaseModel):
    lobby_id: str
    
    @validator('lobby_id')
    def validate_lobby_id(cls, v):
        if not v or len(v) < 3:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Попытка использования слишком короткого lobby_id для перехода к следующему вопросу: длина {len(v) if v else 0}"
            )
            raise ValueError('Invalid lobby ID')
        
        # Проверка на инъекции и другие атаки
        if re.search(r'[<>"\';]', v):
            logger.error(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.INJECTION,
                message=f"Попытка SQL/XSS инъекции в lobby_id: {v[:50]}"
            )
            raise ValueError('Invalid characters in lobby ID')
        
        # Проверка на максимальную длину
        if len(v) > 50:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Слишком длинный lobby_id: длина {len(v)}"
            )
            raise ValueError('Lobby ID too long')
        
        # Проверка на допустимые символы (только буквы, цифры, дефисы и подчеркивания)
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Недопустимые символы в lobby_id: {v[:50]}"
            )
            raise ValueError('Invalid characters in lobby ID')
        
        return v

async def validate_next_question_access(lobby_id: str, user_id: str) -> tuple:
    """
    Централизованная проверка доступа для перехода к следующему вопросу
    Возвращает (lobby, is_host) или выбрасывает HTTPException
    """
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.SECURITY,
        message=f"Проверка доступа для перехода к следующему вопросу: пользователь {user_id}, лобби {lobby_id}"
    )
    
    # Валидация входных параметров
    if not user_id or not lobby_id:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Пустые параметры: user_id={user_id}, lobby_id={lobby_id}"
        )
        raise HTTPException(status_code=400, detail="Неверные параметры запроса")
    
    # Получаем лобби из БД
    lobby = await get_lobby_from_db(lobby_id)
    if not lobby:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ запрещён: лобби {lobby_id} не найдено для пользователя {user_id}"
        )
        raise HTTPException(status_code=404, detail="Лобби не найдено")
    
    # Проверяем, что лобби не истекло
    if lobby.get("created_at"):
        lobby_age = (datetime.utcnow() - lobby["created_at"]).total_seconds()
        if lobby_age > MAX_LOBBY_LIFETIME:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Лобби истекло: лобби {lobby_id} создано {lobby_age:.0f} секунд назад, лимит {MAX_LOBBY_LIFETIME}"
            )
            raise HTTPException(status_code=400, detail="Лобби истекло по времени жизни")
    
    # Проверяем статус лобби
    if lobby["status"] != "in_progress":
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ запрещён по статусу: лобби {lobby_id}, статус {lobby['status']}, пользователь {user_id}"
        )
        raise HTTPException(
            status_code=400, 
            detail=f"Неверный статус лобби. Требуется: in_progress, текущий: {lobby['status']}"
        )
    
    # Проверяем участие пользователя
    participants = lobby.get("participants", [])
    if user_id not in participants:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ запрещён: пользователь {user_id} не является участником лобби {lobby_id}, участники: {len(participants)}"
        )
        raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
    
    is_host = user_id == lobby.get("host_id")
    
    # Проверяем, что только хост может переходить к следующему вопросу
    if not is_host:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Попытка перехода к следующему вопросу не-хостом: пользователь {user_id} пытается перейти к следующему вопросу в лобби {lobby_id}, хост {lobby['host_id']}"
        )
        raise HTTPException(status_code=403, detail="Только хост может переходить к следующему вопросу")
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.SECURITY,
        message=f"Доступ разрешён: пользователь {user_id}, лобби {lobby_id}, хост {is_host}"
    )
    
    return lobby, is_host

async def check_next_question_requirements(lobby: dict) -> None:
    """
    Проверяет требования для перехода к следующему вопросу
    """
    # Проверяем наличие вопросов
    question_ids = lobby.get("question_ids", [])
    if not question_ids:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Нет вопросов в лобби: лобби {lobby['_id']} не содержит вопросов"
        )
        raise HTTPException(status_code=400, detail="В лобби нет вопросов")
    
    # Проверяем, что есть следующий вопрос
    current_index = lobby.get("current_index", 0)
    if current_index >= len(question_ids) - 1:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Нет следующего вопроса: лобби {lobby['_id']}, текущий индекс {current_index}, всего вопросов {len(question_ids)}"
        )
        raise HTTPException(status_code=400, detail="Это последний вопрос в тесте")
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.VALIDATION,
        message=f"Требования для перехода выполнены: лобби {lobby['_id']}, текущий индекс {current_index}, следующий индекс {current_index + 1}, всего вопросов {len(question_ids)}"
    )

@router.post("/lobbies/{lobby_id}/next-question", summary="Перейти к следующему вопросу (только хост)")
@rate_limit_ip("lobby_next_question", max_requests=20, window_seconds=60)
async def next_question(
    lobby_id: str,
    next_data: NextQuestionRequest,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Переходит к следующему вопросу в лобби. Только хост может переходить к следующему вопросу.
    При переходе флаг показа ответов автоматически сбрасывается в false.
    """
    user_id = get_user_id(current_user)
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.QUESTIONS,
        message=f"Попытка перехода к следующему вопросу: пользователь {user_id} пытается перейти к следующему вопросу в лобби {lobby_id}"
    )
    
    try:
        # Проверяем доступ
        lobby, is_host = await validate_next_question_access(lobby_id, user_id)
        
        # Проверяем требования
        await check_next_question_requirements(lobby)
        
        # Получаем текущий индекс и следующий индекс
        current_index = lobby.get("current_index", 0)
        question_ids = lobby.get("question_ids", [])
        next_index = current_index + 1
        
        # Обновляем лобби: переходим к следующему вопросу и сбрасываем флаг показа ответов
        update_data = {
            "current_index": next_index,
            "show_answers": False,  # Сбрасываем флаг показа ответов
            "updated_at": datetime.utcnow()
        }
        
        # Выполняем обновление в базе данных
        result = await db.lobbies.update_one(
            {"_id": lobby["_id"]},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Ошибка обновления лобби: лобби {lobby_id} не обновлено при переходе к следующему вопросу"
            )
            raise HTTPException(status_code=500, detail="Ошибка при переходе к следующему вопросу")
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Успешный переход к следующему вопросу: лобби {lobby_id}, пользователь {user_id}, новый индекс {next_index}, показ ответов сброшен"
        )
        
        return success(data={
            "message": "Переход к следующему вопросу выполнен успешно",
            "current_index": next_index,
            "total_questions": len(question_ids),
            "show_answers": False
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка перехода к следующему вопросу: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при переходе к следующему вопросу")
