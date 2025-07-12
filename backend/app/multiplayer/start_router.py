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
EXAM_TIMER_DURATION = 40 * 60  # 40 минут

class StartLobbyRequest(BaseModel):
    lobby_id: str
    
    @validator('lobby_id')
    def validate_lobby_id(cls, v):
        if not v or len(v) < 3:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Попытка использования слишком короткого lobby_id для старта: длина {len(v) if v else 0}"
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

async def validate_lobby_start_access(lobby_id: str, user_id: str) -> tuple:
    """
    Централизованная проверка доступа для старта лобби
    Возвращает (lobby, is_host, subscription_type) или выбрасывает HTTPException
    """
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.SECURITY,
        message=f"Проверка доступа для старта лобби: пользователь {user_id}, лобби {lobby_id}"
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
    if lobby["status"] != "waiting":
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ запрещён по статусу: лобби {lobby_id}, статус {lobby['status']}, пользователь {user_id}"
        )
        raise HTTPException(
            status_code=400, 
            detail=f"Неверный статус лобби. Требуется: waiting, текущий: {lobby['status']}"
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
    
    # Проверяем, что только хост может стартовать лобби
    if not is_host:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Попытка старта не-хостом: пользователь {user_id} пытается стартовать лобби {lobby_id}, хост {lobby['host_id']}"
        )
        raise HTTPException(status_code=403, detail="Только хост может стартовать лобби")
    
    # Получаем подписку хоста
    host_subscription = await get_user_subscription_from_db(lobby.get("host_id"))
    subscription_type = host_subscription["subscription_type"] if host_subscription else "Demo"
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.SECURITY,
        message=f"Доступ разрешён: пользователь {user_id}, лобби {lobby_id}, хост {is_host}, подписка {subscription_type}"
    )
    
    return lobby, is_host, subscription_type

async def check_lobby_requirements(lobby: dict) -> None:
    """
    Проверяет требования для старта лобби
    """
    # Проверяем минимальное количество участников
    participants_count = len(lobby.get("participants", []))
    if participants_count < 2:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Недостаточно участников для старта: лобби {lobby['_id']} имеет {participants_count} участников, требуется минимум 2"
        )
        raise HTTPException(status_code=400, detail="Необходимо минимум 2 участника для начала теста")
    
    # Проверяем максимальное количество участников
    max_participants = lobby.get("max_participants", 8)
    if participants_count > max_participants:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Превышено максимальное количество участников: лобби {lobby['_id']} имеет {participants_count} участников, максимум {max_participants}"
        )
        raise HTTPException(status_code=400, detail=f"Превышено максимальное количество участников ({participants_count}/{max_participants})")
    
    # Проверяем наличие вопросов
    question_ids = lobby.get("question_ids", [])
    if not question_ids:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Нет вопросов в лобби: лобби {lobby['_id']} не содержит вопросов"
        )
        raise HTTPException(status_code=400, detail="В лобби нет вопросов для теста")
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.VALIDATION,
        message=f"Требования для старта выполнены: лобби {lobby['_id']}, участников {participants_count}/{max_participants}, вопросов {len(question_ids)}"
    )

@router.post("/lobbies/{lobby_id}/start", summary="Начать тест в лобби")
@rate_limit_ip("lobby_start", max_requests=10, window_seconds=300)
async def start_lobby(
    lobby_id: str,
    start_data: StartLobbyRequest,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Начинает тест в лобби. Только создатель лобби может начать тест.
    
    Безопасность:
    - Проверяет, что пользователь является хостом лобби
    - Проверяет, что лобби в статусе "waiting"
    - Проверяет минимальное количество участников (2)
    - Проверяет максимальное количество участников
    - Проверяет наличие вопросов в лобби
    - Проверяет подписку хоста
    - Логирует все действия для аудита
    """
    user_id = get_user_id(current_user)
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.LIFECYCLE,
        message=f"Попытка запуска теста: пользователь {user_id} пытается начать тест в лобби {lobby_id}"
    )
    
    try:
        # Валидация входных данных
        if lobby_id != start_data.lobby_id:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Несоответствие lobby_id: в URL {lobby_id}, в теле запроса {start_data.lobby_id}, пользователь {user_id}"
            )
            raise HTTPException(status_code=400, detail="Несоответствие ID лобби в URL и теле запроса")
        
        # Дополнительная валидация пользователя
        if not current_user or not current_user.get("id"):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Попытка старта без валидного пользователя: {current_user}"
            )
            raise HTTPException(status_code=401, detail="Необходима авторизация")
        
        # Централизованная проверка доступа
        lobby, is_host, subscription_type = await validate_lobby_start_access(lobby_id, user_id)
        
        # Проверяем требования для старта
        await check_lobby_requirements(lobby)
        
        # Проверяем активные сессии всех участников (опционально)
        participants = lobby.get("participants", [])
        active_sessions_warnings = []
        for participant_id in participants:
            if participant_id != user_id:  # Хост уже проверен
                try:
                    await check_active_session(db, participant_id)
                except HTTPException as e:
                    active_sessions_warnings.append(participant_id)
                    logger.warning(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.SECURITY,
                        message=f"Участник {participant_id} имеет активный тест, но это не блокирует старт лобби {lobby_id}"
                    )
        
        # Логируем общую статистику по активным сессиям
        if active_sessions_warnings:
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Старт лобби {lobby_id} с участниками, имеющими активные тесты: {active_sessions_warnings}"
            )
        
        # Обновляем статус лобби
        current_time = datetime.utcnow()
        update_data = {
            "status": "in_progress",
            "started_at": current_time,
            "current_index": 0
        }
        
        # Добавляем таймер экзамена, если включен режим экзамена
        if lobby.get("exam_mode", False):
            update_data["exam_timer_expires_at"] = current_time + timedelta(seconds=EXAM_TIMER_DURATION)
            update_data["exam_timer_started_at"] = current_time
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.EXAM,
                message=f"Таймер экзамена установлен: лобби {lobby_id} получило таймер на {EXAM_TIMER_DURATION} секунд"
            )
        
        # Атомарное обновление с проверкой статуса
        result = await db.lobbies.update_one(
            {
                "_id": lobby_id,
                "status": "waiting"  # Проверяем, что статус все еще waiting
            },
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Race condition при старте лобби: лобби {lobby_id} уже было изменено другим запросом"
            )
            raise HTTPException(status_code=409, detail="Лобби уже было изменено. Попробуйте еще раз.")
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.LIFECYCLE,
            message=f"Тест успешно запущен: лобби {lobby_id} переведено в статус in_progress, участников {len(participants)}"
        )
        
        # Формируем ответ с информацией о первом вопросе
        question_ids = lobby.get("question_ids", [])
        first_question_id = question_ids[0] if question_ids else None
        
        response_data = {
            "message": "Тест успешно начат",
            "lobby_id": lobby_id,
            "status": "in_progress",
            "participants_count": len(participants),
            "max_participants": lobby.get("max_participants", 8),
            "questions_count": len(question_ids),
            "current_question_id": first_question_id,
            "current_index": 0,
            "show_answers": False,  # По умолчанию ответы скрыты
            "exam_mode": lobby.get("exam_mode", False)
        }
        
        # Добавляем информацию о таймере экзамена
        if lobby.get("exam_mode", False):
            response_data["exam_timer_duration"] = EXAM_TIMER_DURATION
            response_data["exam_timer_expires_at"] = update_data["exam_timer_expires_at"].isoformat()
        
        return success(data=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка запуска теста: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при начале теста")

@router.post("/lobbies/{lobby_id}/force-start", summary="Принудительно начать тест (только хост)")
@rate_limit_ip("lobby_force_start", max_requests=5, window_seconds=600)
async def force_start_lobby(
    lobby_id: str,
    start_data: StartLobbyRequest,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Принудительно начинает тест в лобби, даже если не все участники готовы.
    Только хост может использовать этот эндпоинт.
    
    Используется в случаях:
    - Когда некоторые участники не отвечают
    - Когда нужно начать тест с меньшим количеством участников
    - В экстренных ситуациях
    """
    user_id = get_user_id(current_user)
    
    logger.warning(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.LIFECYCLE,
        message=f"Попытка принудительного запуска теста: пользователь {user_id} пытается принудительно начать тест в лобби {lobby_id}"
    )
    
    try:
        # Валидация входных данных
        if lobby_id != start_data.lobby_id:
            raise HTTPException(status_code=400, detail="Несоответствие ID лобби в URL и теле запроса")
        
        # Получаем лобби
        lobby = await get_lobby_from_db(lobby_id)
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем, что лобби не истекло
        if lobby.get("created_at"):
            lobby_age = (datetime.utcnow() - lobby["created_at"]).total_seconds()
            if lobby_age > MAX_LOBBY_LIFETIME:
                logger.warning(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.SECURITY,
                    message=f"Лобби истекло при принудительном старте: лобби {lobby_id} создано {lobby_age:.0f} секунд назад"
                )
                raise HTTPException(status_code=400, detail="Лобби истекло по времени жизни")
        
        # Проверяем, что пользователь является хостом
        if lobby.get("host_id") != user_id:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Попытка принудительного старта не-хостом: пользователь {user_id} пытается принудительно стартовать лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Только хост может принудительно стартовать лобби")
        
        # Проверяем статус лобби
        if lobby["status"] != "waiting":
            raise HTTPException(status_code=400, detail="Лобби не в статусе ожидания")
        
        # Проверяем минимальные требования (хотя бы 1 участник - хост)
        participants = lobby.get("participants", [])
        if len(participants) < 1:
            raise HTTPException(status_code=400, detail="В лобби должен быть хотя бы один участник")
        
        # Проверяем участие хоста в лобби
        if user_id not in participants:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Хост {user_id} не является участником лобби {lobby_id} при принудительном старте"
            )
            raise HTTPException(status_code=403, detail="Хост должен быть участником лобби")
        
        # Проверяем наличие вопросов
        question_ids = lobby.get("question_ids", [])
        if not question_ids:
            raise HTTPException(status_code=400, detail="В лобби нет вопросов для теста")
        
        # Обновляем статус лобби
        current_time = datetime.utcnow()
        update_data = {
            "status": "in_progress",
            "started_at": current_time,
            "current_index": 0,
            "force_started": True,
            "force_started_by": user_id,
            "force_started_at": current_time
        }
        
        # Добавляем таймер экзамена, если включен режим экзамена
        if lobby.get("exam_mode", False):
            update_data["exam_timer_expires_at"] = current_time + timedelta(seconds=EXAM_TIMER_DURATION)
            update_data["exam_timer_started_at"] = current_time
        
        # Атомарное обновление с проверкой статуса
        result = await db.lobbies.update_one(
            {
                "_id": lobby_id,
                "status": "waiting"  # Проверяем, что статус все еще waiting
            },
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Race condition при принудительном старте лобби: лобби {lobby_id} уже было изменено другим запросом"
            )
            raise HTTPException(status_code=409, detail="Лобби уже было изменено. Попробуйте еще раз.")
        
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.LIFECYCLE,
            message=f"Тест принудительно запущен: лобби {lobby_id} принудительно стартовано хостом {user_id}, участников {len(participants)}"
        )
        
        # Формируем ответ
        first_question_id = question_ids[0] if question_ids else None
        
        response_data = {
            "message": "Тест принудительно начат",
            "lobby_id": lobby_id,
            "status": "in_progress",
            "participants_count": len(participants),
            "max_participants": lobby.get("max_participants", 8),
            "questions_count": len(question_ids),
            "current_question_id": first_question_id,
            "current_index": 0,
            "show_answers": False,  # По умолчанию ответы скрыты
            "exam_mode": lobby.get("exam_mode", False),
            "force_started": True
        }
        
        # Добавляем информацию о таймере экзамена
        if lobby.get("exam_mode", False):
            response_data["exam_timer_duration"] = EXAM_TIMER_DURATION
            response_data["exam_timer_expires_at"] = update_data["exam_timer_expires_at"].isoformat()
        
        return success(data=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка принудительного запуска теста: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при принудительном начале теста")

@router.get("/lobbies/{lobby_id}/start-status", summary="Получить статус готовности к старту")
@rate_limit_ip("lobby_start_status", max_requests=30, window_seconds=60)
async def get_start_status(
    lobby_id: str,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Возвращает статус готовности лобби к старту.
    Показывает количество участников, их готовность и другие параметры.
    """
    user_id = get_user_id(current_user)
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Запрос статуса готовности: пользователь {user_id} запрашивает статус готовности лобби {lobby_id}"
    )
    
    try:
        # Получаем лобби
        lobby = await get_lobby_from_db(lobby_id)
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем участие пользователя
        if user_id not in lobby.get("participants", []):
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        # Проверяем статус лобби
        if lobby["status"] != "waiting":
            raise HTTPException(status_code=400, detail="Лобби не в статусе ожидания")
        
        participants = lobby.get("participants", [])
        max_participants = lobby.get("max_participants", 8)
        question_ids = lobby.get("question_ids", [])
        
        # Проверяем готовность к старту
        can_start = (
            len(participants) >= 2 and  # Минимум 2 участника
            len(question_ids) > 0 and   # Есть вопросы
            len(participants) <= max_participants  # Не превышен лимит
        )
        
        # Получаем информацию о хосте
        host_id = lobby.get("host_id")
        is_host = user_id == host_id
        
        # Получаем имена участников с защитой от ошибок
        participants_info = []
        for participant_id in participants:
            try:
                if participant_id.startswith("guest_"):
                    participant_name = f"Гость {participant_id[-8:]}"
                    is_guest = True
                else:
                    try:
                        # Проверяем валидность ObjectId
                        if ObjectId.is_valid(participant_id):
                            user_data = await db.users.find_one({"_id": ObjectId(participant_id)})
                            participant_name = user_data.get("full_name", "Неизвестный пользователь") if user_data else "Неизвестный пользователь"
                        else:
                            participant_name = "Неизвестный пользователь"
                        is_guest = False
                    except Exception as e:
                        logger.warning(
                            section=LogSection.LOBBY,
                            subsection=LogSubsection.LOBBY.DATABASE,
                            message=f"Ошибка получения данных пользователя {participant_id}: {str(e)}"
                        )
                        participant_name = "Неизвестный пользователь"
                        is_guest = False
                
                participants_info.append({
                    "user_id": participant_id,
                    "name": participant_name,
                    "is_host": participant_id == host_id,
                    "is_guest": is_guest,
                    "is_current_user": participant_id == user_id
                })
            except Exception as e:
                logger.error(
                    section=LogSection.LOBBY,
                    subsection=LogSection.LOBBY.ERROR,
                    message=f"Ошибка обработки участника {participant_id}: {str(e)}"
                )
                # Добавляем участника с дефолтными данными
                participants_info.append({
                    "user_id": participant_id,
                    "name": "Неизвестный пользователь",
                    "is_host": participant_id == host_id,
                    "is_guest": False,
                    "is_current_user": participant_id == user_id
                })
        
        response_data = {
            "lobby_id": lobby_id,
            "status": lobby["status"],
            "participants": participants_info,
            "participants_count": len(participants),
            "max_participants": max_participants,
            "questions_count": len(question_ids),
            "can_start": can_start,
            "is_host": is_host,
            "requirements": {
                "min_participants": 2,
                "has_questions": len(question_ids) > 0,
                "within_participant_limit": len(participants) <= max_participants
            },
            "exam_mode": lobby.get("exam_mode", False)
        }
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Статус готовности возвращён: лобби {lobby_id}, участников {len(participants)}, может стартовать {can_start}"
        )
        
        return success(data=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения статуса готовности: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при получении статуса готовности") 