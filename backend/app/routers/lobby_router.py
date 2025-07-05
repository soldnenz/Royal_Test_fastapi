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
from bson.errors import InvalidId
import json
from pydantic import BaseModel, validator
from app.logging import get_logger, LogSection, LogSubsection
import asyncio
from app.core.gridfs_utils import get_media_file
import base64
import re
import random
import string
from collections import defaultdict
from typing import Optional, List, Dict, Any, Union
import time

# Настройка логгера
logger = get_logger(__name__)

def generate_safe_filename(original_filename: str, file_extension: str = None) -> str:
    """
    Генерирует безопасное ASCII имя файла из случайных символов
    """
    # Логируем подозрительные имена файлов
    if original_filename and (len(original_filename) > 255 or '..' in original_filename or '/' in original_filename or '\\' in original_filename):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Подозрительное имя файла: {original_filename[:100]}, длина {len(original_filename)}"
        )
    
    # Генерируем случайную строку из 8 символов (цифры и буквы)
    random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    # Определяем расширение файла
    if not file_extension:
        if '.' in original_filename:
            file_extension = original_filename.split('.')[-1].lower()
            # Проверяем, что расширение содержит только ASCII символы
            try:
                file_extension.encode('ascii')
            except UnicodeEncodeError:
                logger.warning(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.VALIDATION,
                    message=f"Небезопасное расширение файла с non-ASCII символами: {file_extension[:20]}, использовано 'bin'"
                )
                file_extension = 'bin'  # Используем безопасное расширение
        else:
            file_extension = 'bin'
    
    # Ограничиваем длину расширения для безопасности
    if len(file_extension) > 10:
        logger.warning(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.VALIDATION,
            message=f"Слишком длинное расширение файла: {file_extension[:20]}, длина {len(file_extension)}, использовано 'bin'"
        )
        file_extension = 'bin'
    
    return f"{random_name}.{file_extension}"

# Maximum time a lobby can be active (4 hours in seconds)
MAX_LOBBY_LIFETIME = 4 * 60 * 60

# Exam mode timer (40 minutes in seconds)
EXAM_TIMER_DURATION = 40 * 60

# Cache для горячих лобби и пользователей
class LobbyCache:
    def __init__(self):
        self.lobbies: Dict[str, dict] = {}  # Кэш лобби
        self.user_subscriptions: Dict[str, dict] = {}  # Кэш подписок
        self.lobby_access_cache: Dict[str, dict] = {}  # Кэш доступа к лобби
        logger.info(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.INITIALIZATION,
            message="Кэш лобби инициализирован: создан LobbyCache с пустыми хэш-таблицами для лобби, подписок и доступа"
        )
    
    async def get_lobby(self, lobby_id: str, force_refresh: bool = False):
        """Получить лобби с кэшированием"""
        if not force_refresh and lobby_id in self.lobbies:
            cached_lobby = self.lobbies[lobby_id]
            # Проверяем свежесть кэша (30 секунд для активных лобби)
            if (datetime.utcnow() - cached_lobby.get("cached_at", datetime.min)).total_seconds() < 30:
                return cached_lobby["data"]
        
        # Загружаем из MongoDB
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if lobby:
            self.lobbies[lobby_id] = {
                "data": lobby,
                "cached_at": datetime.utcnow()
            }
        return lobby
    
    async def get_user_subscription(self, user_id: str):
        """Получить подписку пользователя с кэшированием"""
        if user_id in self.user_subscriptions:
            cached_sub = self.user_subscriptions[user_id]
            # Кэш подписки на 5 минут
            if (datetime.utcnow() - cached_sub.get("cached_at", datetime.min)).total_seconds() < 300:
                return cached_sub["data"]
        
        # Для гостей подписки нет
        if isinstance(user_id, str) and user_id.startswith("guest_"):
            self.user_subscriptions[user_id] = {
                "data": None,
                "cached_at": datetime.utcnow()
            }
            return None
        
        # Загружаем из MongoDB для обычных пользователей
        subscription = await db.subscriptions.find_one({
            "user_id": ObjectId(user_id),
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        self.user_subscriptions[user_id] = {
            "data": subscription,
            "cached_at": datetime.utcnow()
        }
        return subscription
    
    def invalidate_lobby(self, lobby_id: str):
        """Очистить кэш лобби"""
        if lobby_id in self.lobbies:
            del self.lobbies[lobby_id]
    
    def cleanup_old_cache(self):
        """Очистка старого кэша (вызывается периодически)"""
        current_time = datetime.utcnow()
        # Удаляем лобби старше 5 минут
        old_lobbies = [
            lobby_id for lobby_id, data in self.lobbies.items()
            if (current_time - data.get("cached_at", datetime.min)).total_seconds() > 300
        ]
        for lobby_id in old_lobbies:
            del self.lobbies[lobby_id]
        
        # Удаляем подписки старше 10 минут
        old_subs = [
            user_id for user_id, data in self.user_subscriptions.items()
            if (current_time - data.get("cached_at", datetime.min)).total_seconds() > 600
        ]
        for user_id in old_subs:
            del self.user_subscriptions[user_id]

# Глобальный кэш
lobby_cache = LobbyCache()

# Простой Rate Limiter
class SimpleRateLimiter:
    def __init__(self, max_requests: int = 60, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = defaultdict(list)
        
    def check_rate_limit(self, user_id: str) -> bool:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        user_requests = self.requests[user_id]
        
        # Удаляем старые запросы
        user_requests[:] = [req_time for req_time in user_requests 
                           if now - req_time < timedelta(seconds=self.time_window)]
        
        if len(user_requests) >= self.max_requests:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.RATE_LIMIT,
                message=f"Превышение лимита запросов: пользователь {user_id} заблокирован, {len(user_requests)} запросов за {self.time_window} секунд (лимит {self.max_requests})"
            )
            return False
            
        user_requests.append(now)
        return True

rate_limiter = SimpleRateLimiter()

async def validate_lobby_access(lobby_id: str, user_id: str, required_status: str = None, is_guest: bool = False):
    """
    Централизованная проверка доступа к лобби
    Возвращает (lobby, is_host, subscription_type) или выбрасывает HTTPException
    """
    cache_key = f"{lobby_id}:{user_id}"
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.SECURITY,
        message=f"Проверка доступа к лобби: пользователь {user_id}, лобби {lobby_id}, требуемый статус {required_status or 'любой'}, гость {is_guest}"
    )
    
    # Получаем лобби из кэша
    lobby = await lobby_cache.get_lobby(lobby_id)
    if not lobby:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ запрещён: лобби {lobby_id} не найдено для пользователя {user_id}"
        )
        raise HTTPException(status_code=404, detail="Лобби не найдено")
    
    # Проверяем статус лобби
    if required_status and lobby["status"] != required_status:
        # Попробуем обновить кеш и проверить еще раз
        lobby = await lobby_cache.get_lobby(lobby_id, force_refresh=True)
        if lobby and lobby["status"] != required_status:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Доступ запрещён по статусу: лобби {lobby_id}, требуемый статус {required_status}, текущий {lobby['status']}, пользователь {user_id}"
            )
            raise HTTPException(
                status_code=400, 
                detail=f"Неверный статус лобби. Требуется: {required_status}, текущий: {lobby['status']}"
            )
    
    # Проверяем участие пользователя
    if user_id not in lobby["participants"]:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Доступ запрещён: пользователь {user_id} не является участником лобби {lobby_id}, участники: {len(lobby.get('participants', []))}"
        )
        raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
    
    is_host = user_id == lobby.get("host_id")
    
    # Для гостей получаем тип подписки хоста
    if is_guest:
        host_subscription = await lobby_cache.get_user_subscription(lobby.get("host_id"))
        subscription_type = host_subscription["subscription_type"] if host_subscription else "Demo"
    else:
        # Получаем тип подписки из кэша для обычных пользователей
        subscription = await lobby_cache.get_user_subscription(user_id)
        subscription_type = subscription["subscription_type"] if subscription else "Demo"
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.SECURITY,
        message=f"Доступ разрешён: пользователь {user_id}, лобби {lobby_id}, хост {is_host}, подписка {subscription_type}"
    )
    
    return lobby, is_host, subscription_type

class AnswerSubmit(BaseModel):
    question_id: str
    answer_index: int

class MultiplayerAnswerSubmit(BaseModel):
    question_id: str
    answer_index: int
    question_index: int

class LobbyCreate(BaseModel):
    mode: str = "solo"  # По умолчанию solo
    categories: List[str] = None
    pdd_section_uids: Optional[List[str]] = None
    questions_count: int = 40
    exam_mode: bool = False  # По умолчанию выключен режим экзамена
    max_participants: int = 8  # Максимальное количество участников

class ExamTimerUpdate(BaseModel):
    time_left: int  # Оставшееся время в секундах

class KickParticipantRequest(BaseModel):
    target_user_id: str
    
    @validator('target_user_id')
    def validate_user_id(cls, v):
        if not v or len(v) < 3:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Попытка использования слишком короткого user_id для исключения: длина {len(v) if v else 0}"
            )
            raise ValueError('Invalid user ID')
        # Проверка на инъекции и другие атаки
        if re.search(r'[<>"\';]', v):
            logger.error(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.INJECTION,
                message=f"Попытка SQL/XSS инъекции в target_user_id: {v[:50]}"
            )
            raise ValueError('Invalid characters in user ID')
        return v

router = APIRouter()

def convert_answer_to_index(correct_answer_raw):
    """Convert letter answer (A, B, C, D) to numeric index (0, 1, 2, 3)"""
    if isinstance(correct_answer_raw, str):
        letter_to_index = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        result = letter_to_index.get(correct_answer_raw.upper(), 0)
        if correct_answer_raw.upper() not in letter_to_index:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.VALIDATION,
                message=f"Неизвестный буквенный ответ при конвертации: {correct_answer_raw}, использован индекс 0 по умолчанию"
            )
        return result
    else:
        if correct_answer_raw is None:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.VALIDATION,
                message="Получен None при конвертации ответа, использован индекс 0 по умолчанию"
            )
            return 0
        return correct_answer_raw

def validate_object_id(id_string: str) -> bool:
    """Проверка валидности ObjectId"""
    try:
        ObjectId(id_string)
        return True
    except (InvalidId, TypeError):
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Попытка использования невалидного ObjectId: {id_string[:50] if id_string else 'None'}"
        )
        return False

async def validate_answer_integrity(lobby_id: str, question_id: str, answer_index: int) -> bool:
    """Проверка целостности данных ответа"""
    try:
        # Получаем лобби
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby or question_id not in lobby.get("question_ids", []):
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Нарушение целостности: вопрос {question_id} не принадлежит лобби {lobby_id}"
            )
            return False
        
        # Получаем вопрос напрямую из базы данных
        question = await db.questions.find_one({"_id": ObjectId(question_id)})
        if not question:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Нарушение целостности: вопрос {question_id} не найден в базе данных"
            )
            return False
        
        # Проверяем, что индекс ответа валиден
        options_count = 0
        if "options" in question:
            options_count = len(question["options"])
        elif "answers" in question:
            options_count = len(question["answers"])
        else:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Нарушение целостности: вопрос {question_id} не содержит вариантов ответов"
            )
            return False
            
        if answer_index < 0 or answer_index >= options_count:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Нарушение целостности: недопустимый индекс ответа {answer_index} для вопроса {question_id}, доступно вариантов {options_count}"
            )
            return False
            
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Проверка целостности пройдена: вопрос {question_id}, индекс ответа {answer_index}, доступно вариантов {options_count}"
        )
        return True
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка проверки целостности ответа: лобби {lobby_id}, вопрос {question_id}, ошибка {str(e)}"
        )
        return False

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

async def auto_finish_expired_lobbies():
    """
    Background task to check and finish lobbies that have been active for more than 4 hours
    Also checks exam mode timers and finishes tests when time runs out
    Also performs cache cleanup every 5 minutes
    """
    cleanup_counter = 0
    while True:
        try:
            current_time = datetime.utcnow()
            
            # Find lobbies that are older than 4 hours and still active
            expiration_time = current_time - timedelta(seconds=MAX_LOBBY_LIFETIME)
            expired_lobbies = await db.lobbies.find({
                "status": "in_progress",
                "created_at": {"$lt": expiration_time}
            }).to_list(None)
            
            for lobby in expired_lobbies:
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.LIFECYCLE,
                    message=f"Автозакрытие просроченного лобби: лобби {lobby['_id']} создано {lobby['created_at']}, превышен лимит {MAX_LOBBY_LIFETIME} секунд"
                )
                
                # Set the lobby as finished
                await db.lobbies.update_one(
                    {"_id": lobby["_id"]},
                    {"$set": {
                        "status": "finished",
                        "finished_at": current_time,
                        "auto_finished": True,
                        "finish_reason": "time_limit_exceeded"
                    }}
                )
                
                # Инвалидируем кэш для истекшего лобби
                lobby_cache.invalidate_lobby(lobby["_id"])
                
                # Notify all participants via WebSocket
                try:
                    await ws_manager.send_json_parallel(lobby["_id"], {
                        "type": "test_finished",
                        "data": {"auto_finished": True, "reason": "Time limit exceeded (4 hours)"}
                    })
                except Exception as e:
                    logger.error(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.ERROR,
                        message=f"Ошибка отправки WS уведомления об автозакрытии: лобби {lobby['_id']}, ошибка {str(e)}"
                    )
            
            # Check exam mode timers
            exam_lobbies = await db.lobbies.find({
                "status": "in_progress",
                "exam_mode": True,
                "exam_timer_expires_at": {"$lt": current_time}
            }).to_list(None)
            
            for lobby in exam_lobbies:
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.EXAM,
                    message=f"Автозакрытие экзаменационного лобби: лобби {lobby['_id']} завершён по истечении таймера экзамена"
                )
                
                # Calculate duration
                duration = (current_time - lobby.get("created_at", current_time)).total_seconds()
                
                # Set the lobby as finished
                await db.lobbies.update_one(
                    {"_id": lobby["_id"]},
                    {"$set": {
                        "status": "finished",
                        "finished_at": current_time,
                        "auto_finished": True,
                        "finish_reason": "exam_timer_expired",
                        "duration_seconds": duration
                    }}
                )
                
                # Инвалидируем кэш для истекшего лобби
                lobby_cache.invalidate_lobby(lobby["_id"])
                
                # Save history for all participants
                for participant_id, answers in lobby.get("participants_answers", {}).items():
                    correct_count = sum(1 for is_corr in answers.values() if is_corr)
                    total_questions = len(lobby.get("question_ids", []))
                    
                    history_record = {
                        "user_id": participant_id,
                        "lobby_id": lobby["_id"],
                        "date": current_time,
                        "score": correct_count,
                        "total": total_questions,
                        "categories": lobby.get("categories", []),
                        "sections": lobby.get("sections", []),
                        "mode": lobby.get("mode", "solo"),
                        "pass_percentage": (correct_count / total_questions * 100) if total_questions > 0 else 0,
                        "duration_seconds": duration,
                        "is_passed": correct_count >= int(total_questions * 0.8),
                        "auto_finished": True,
                        "finish_reason": "exam_timer_expired"
                    }
                    await db.history.insert_one(history_record)
                
                # Notify all participants via WebSocket
                try:
                    await ws_manager.send_json_parallel(lobby["_id"], {
                        "type": "test_finished",
                        "data": {
                            "auto_finished": True, 
                            "reason": "Exam timer expired",
                            "duration_seconds": duration
                        }
                    })
                except Exception as e:
                    logger.error(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.ERROR,
                        message=f"Ошибка отправки WS уведомления об истечении таймера экзамена: лобби {lobby['_id']}, ошибка {str(e)}"
                    )
            
            # Очистка кэша каждые 5 минут (300 секунд / 60 = 5 итераций)
            cleanup_counter += 1
            if cleanup_counter >= 5:
                lobby_cache.cleanup_old_cache()
                cleanup_counter = 0
                logger.info(
                    section=LogSection.SYSTEM,
                    subsection=LogSubsection.SYSTEM.MAINTENANCE,
                    message="Очистка кэша выполнена: удалены устаревшие записи лобби и подписок"
                )
            
            # Check every minute
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(
                section=LogSection.SYSTEM,
                subsection=LogSubsection.SYSTEM.ERROR,
                message=f"Ошибка в фоновой задаче автозакрытия лобби: {str(e)}"
            )
            await asyncio.sleep(60)  # Still wait before retrying

# Create a function to start background tasks that will be registered in main.py
async def start_background_tasks():
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.INITIALIZATION,
        message="Запуск фоновых задач: инициализация задачи автозавершения просроченных лобби"
    )
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
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.CREATION,
        message=f"Запрос создания лобби: пользователь {user_id} создаёт {lobby_data.mode}-лобби на {lobby_data.questions_count} вопросов"
    )
    
    try:
        # Используем количество вопросов из запроса
        questions_count = lobby_data.questions_count
        
        # Проверка активных тестов пользователя и получение подписки параллельно
        active_lobby_task = db.lobbies.find_one({
            "participants": user_id,
            "status": {"$ne": "finished"}
        })
        subscription_task = lobby_cache.get_user_subscription(user_id)
        
        # Выполняем оба запроса параллельно
        active_lobby, subscription = await asyncio.gather(active_lobby_task, subscription_task)
        
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
                    logger.info(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.LIFECYCLE,
                        message=f"Автозавершение просроченного лобби: лобби {active_lobby['_id']} пользователя {user_id} закрыто по таймауту {MAX_LOBBY_LIFETIME} секунд"
                    )
                else:
                    # Lobby is still active and not expired
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
                # If created_at is missing for some reason, just report the lobby as active
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
            # Демо-режим или бесплатный доступ
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
        
        # Проверка прав на создание лобби
        if lobby_data.mode == "multi" and subscription_type not in ["Royal", "School"]:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Отказ в мультиплеере: пользователь {user_id} с подпиской {subscription_type} не может создать multi-лобби, требуется Royal или School"
            )
            raise HTTPException(
                status_code=403, 
                detail="Для создания многопользовательского лобби требуется подписка Royal или School"
            )
        
        # Обрабатываем разделы ПДД (доступно для VIP, Royal и School)
        if lobby_data.pdd_section_uids is not None and subscription_type.lower() not in ["vip", "royal", "school"]:
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
        if subscription_type == "Economy":
            allowed_categories = ["A1", "A", "B1", "B", "BE"]
            if lobby_data.categories and not all(cat in allowed_categories for cat in lobby_data.categories):
                logger.warning(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.SECURITY,
                    message=f"Отказ в выборе категорий: пользователь {user_id} с подпиской {subscription_type} пытался выбрать {lobby_data.categories}, разрешены {allowed_categories}"
                )
                raise HTTPException(status_code=403, detail="Ваша подписка не даёт доступа к выбранным категориям")
            
            # Для Economy нельзя выбирать разделы
            lobby_data.pdd_section_uids = None
            
            # Определяем группу (мото или авто)
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
            # Vip может выбирать любые категории и разделы ПДД
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
        
        # Ограничим количество запрашиваемых вопросов количеством доступных
        questions_count = min(questions_count, total_questions)
        
        # Убедимся, что не больше 40 вопросов
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
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.CREATION,
            message=f"ID лобби сгенерирован: создано уникальное лобби {lobby_id}"
        )
        
        # Определяем начальный статус - для solo сразу in_progress, для multi/multiplayer - waiting
        initial_status = "waiting" if lobby_data.mode in ["multi", "multiplayer"] else "in_progress"
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.LIFECYCLE,
            message=f"Статус лобби установлен: лобби {lobby_id} получило статус {initial_status} для режима {lobby_data.mode}"
        )
        
        # Подготавливаем данные лобби
        current_time = datetime.utcnow()
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
            "created_at": current_time,
            "sections": lobby_data.pdd_section_uids or [],
            "categories": lobby_data.categories or [],
            "mode": lobby_data.mode,
            "subscription_type": subscription_type,
            "exam_mode": lobby_data.exam_mode,
            "max_participants": lobby_data.max_participants,  # Максимальное количество участников
            "questions_count": questions_count  # Сохраняем количество вопросов
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
                message=f"Лобби сохранено в БД: лобби {lobby_id} успешно создано с {questions_count} вопросами в режиме {lobby_data.mode}"
            )
            
            # Если solo режим, отправляем WebSocket сообщение о начале теста
            if lobby_data.mode not in ["multi", "multiplayer"]:
                first_question_id = question_ids[0] if question_ids else None
                if first_question_id:
                    try:
                        # Отправляем событие START и ID первого вопроса
                        logger.info(
                            section=LogSection.WEBSOCKET,
                            subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
                            message=f"Отправка WS старта: лобби {lobby_id} solo-режим, отправляется start с вопросом {first_question_id}"
                        )
                        await ws_manager.send_json(lobby_id, {
                            "type": "start",
                            "data": {"question_id": first_question_id}
                        })

                    except Exception as e:
                        logger.error(
                            section=LogSection.WEBSOCKET,
                            subsection=LogSubsection.WEBSOCKET.ERROR,
                            message=f"Ошибка отправки WS сообщения: лобби {lobby_id}, ошибка {str(e)}"
                        )
            
            response_data = {
                "lobby_id": lobby_id, 
                "status": initial_status, 
                "questions_count": questions_count,
                "categories": lobby_data.categories,
                "sections": lobby_data.pdd_section_uids,
                "auto_started": lobby_data.mode not in ["multi", "multiplayer"],
                "exam_mode": lobby_data.exam_mode
            }
            
            # Добавляем информацию о таймере экзамена
            if lobby_data.exam_mode:
                response_data["exam_timer_duration"] = EXAM_TIMER_DURATION
                response_data["exam_timer_expires_at"] = lobby_doc["exam_timer_expires_at"].isoformat()
            
            return success(data=response_data)
        except Exception as e:
            # Логируем ошибку
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.DATABASE,
                message=f"Ошибка сохранения лобби: лобби {lobby_id}, ошибка {str(e)}"
            )
            raise HTTPException(status_code=500, detail=f"Ошибка при создании лобби: {str(e)}")
    except HTTPException:
        # Пропускаем HTTP исключения дальше
        raise
    except Exception as e:
        # Логируем и обрабатываем неожиданные ошибки
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Критическая ошибка создания лобби: пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.post("/lobbies/{lobby_id}/join", summary="Присоединиться к лобби")
async def join_lobby(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Присоединение к существующему лобби.
    Проверяет, что лобби существует, не заполнено и пользователь не в черном списке.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Попытка присоединения к лобби: пользователь {user_id} пытается присоединиться к лобби {lobby_id}"
    )
    
    try:
        # Получаем информацию о лобби
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Лобби не найдено: пользователь {user_id} пытается присоединиться к несуществующему лобби {lobby_id}"
            )
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем, что пользователь не в черном списке
        blacklisted_users = lobby.get("blacklisted_users", [])
        if user_id in blacklisted_users:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Заблокированный пользователь: пользователь {user_id} в чёрном списке лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вы были исключены из этого лобби и не можете присоединиться снова")
        
        # Проверяем статус лобби
        if lobby["status"] == "finished":
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Попытка присоединения к завершённому лобби: пользователь {user_id}, лобби {lobby_id} статус finished"
            )
            raise HTTPException(status_code=400, detail="Лобби уже завершено")
        
        # Если лобби уже запущено, перенаправляем на страницу теста
        if lobby["status"] == "in_progress":
            if user_id in lobby.get("participants", []):
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.ACCESS,
                    message=f"Переподключение к активному тесту: пользователь {user_id} переподключается к запущенному лобби {lobby_id}"
                )
                return success(data={
                    "message": "Перенаправление на активный тест",
                    "redirect": f"/multiplayer/test/{lobby_id}",
                    "lobby_status": "in_progress"
                })
            else:
                raise HTTPException(status_code=400, detail="Тест уже начался, присоединение невозможно")
        
        # Проверяем, что пользователь еще не участник
        if user_id in lobby.get("participants", []):
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Пользователь уже участник: пользователь {user_id} уже участвует в лобби {lobby_id}"
            )
            return success(data={
                "message": "Вы уже участник этого лобби",
                "lobby_id": lobby_id,
                "already_member": True
            })
        
        # Проверяем максимальное количество участников
        current_participants = len(lobby.get("participants", []))
        max_participants = lobby.get("max_participants", 8)
        
        if current_participants >= max_participants:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Лобби переполнено: лобби {lobby_id} заполнено {current_participants}/{max_participants}, отказ пользователю {user_id}"
            )
            raise HTTPException(status_code=400, detail=f"Лобби заполнено ({current_participants}/{max_participants})")
        
        # Получаем информацию о пользователе для WebSocket уведомления
        user_name = "Unknown User"
        is_guest = user_id.startswith("guest_")
        
        if is_guest:
            user_name = f"Гость {user_id[-8:]}"
        else:
            # Получаем имя пользователя из базы данных
            try:
                user_data = await db.users.find_one({"_id": ObjectId(user_id)})
                if user_data:
                    user_name = user_data.get("full_name", "Unknown User")
            except Exception as e:
                logger.warning(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.DATABASE,
                    message=f"Не удалось получить данные пользователя: пользователь {user_id}, ошибка {str(e)}"
                )
        
        # Добавляем пользователя к участникам лобби
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$addToSet": {"participants": user_id}}
        )
        
        # Инвалидируем кэш лобби
        lobby_cache.invalidate_lobby(lobby_id)
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Успешное присоединение: пользователь {user_id} ({user_name}) присоединился к лобби {lobby_id}, участников {current_participants + 1}/{max_participants}"
        )
        
        # Отправляем WebSocket уведомление о присоединении пользователя
        try:
            await ws_manager.send_json_parallel(lobby_id, {
                "type": "user_joined",
                "data": {
                    "user_id": user_id,
                    "user_name": user_name,
                    "is_host": False,
                    "is_guest": is_guest
                }
            })
        except Exception as e:
            logger.error(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.ERROR,
                message=f"Ошибка отправки WS уведомления о присоединении: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
            )
        
        return success(data={
            "message": "Успешно присоединились к лобби",
            "lobby_id": lobby_id,
            "user_name": user_name,
            "participants_count": current_participants + 1,
            "max_participants": max_participants
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка присоединения к лобби: пользователь {user_id}, лобби {lobby_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при присоединении к лобби")

@router.post("/lobbies/{lobby_id}/start", summary="Начать тест")
async def start_test(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Начинает тест в лобби. Только создатель лобби может начать тест.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.LIFECYCLE,
        message=f"Попытка запуска теста: пользователь {user_id} пытается начать тест в лобби {lobby_id}"
    )
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Лобби не найдено для запуска: пользователь {user_id} пытается запустить несуществующее лобби {lobby_id}"
            )
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if lobby["host_id"] != user_id:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Нет прав на запуск: пользователь {user_id} пытается запустить чужое лобби {lobby_id}, хост {lobby['host_id']}"
            )
            raise HTTPException(status_code=403, detail="Только создатель лобби может начать тест")
        
        if lobby["status"] != "waiting":
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.LIFECYCLE,
                message=f"Неверный статус для запуска: лобби {lobby_id} имеет статус {lobby['status']}, ожидается waiting"
            )
            raise HTTPException(status_code=400, detail="Тест уже начат или завершен")
        
        if len(lobby["participants"]) < 2:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.VALIDATION,
                message=f"Недостаточно участников: лобби {lobby_id} имеет {len(lobby['participants'])} участников, требуется минимум 2"
            )
            raise HTTPException(status_code=400, detail="Необходимо минимум 2 участника для начала теста")
        
        # Обновляем статус лобби
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": {"status": "in_progress"}}
        )
        
        # Инвалидируем кэш лобби после изменения статуса
        lobby_cache.invalidate_lobby(lobby_id)
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.LIFECYCLE,
            message=f"Тест успешно запущен: лобби {lobby_id} переведено в статус in_progress, участников {len(lobby['participants'])}"
        )
        
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
            logger.error(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.ERROR,
                message=f"Ошибка отправки WS уведомления о запуске теста: лобби {lobby_id}, ошибка {str(e)}"
            )
        
        return success(data={"message": "Тест успешно начат"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка запуска теста: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при начале теста")

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
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Запрос вопроса: пользователь {user_id} запрашивает вопрос {question_id} в лобби {lobby_id}"
    )
    
    try:
        # Используем централизованную валидацию с кэшированием
        lobby, is_host, subscription_type = await validate_lobby_access(lobby_id, user_id, "in_progress")
        
        # Проверяем, что запрашиваемый вопрос входит в список вопросов лобби
        if question_id not in lobby["question_ids"]:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Нарушение безопасности: пользователь {user_id} пытается получить вопрос {question_id}, не принадлежащий лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Запрашиваемый вопрос не является частью этого теста")

        # Проверяем, является ли этот вопрос текущим или уже отвеченным
        current_index = lobby.get("current_index", 0)
        
        if current_index >= len(lobby["question_ids"]):
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.VALIDATION,
                message=f"Некорректный индекс вопроса: лобби {lobby_id} имеет индекс {current_index} при {len(lobby['question_ids'])} вопросах"
            )
            raise HTTPException(status_code=500, detail="Некорректный индекс текущего вопроса")
            
        current_question_id = lobby["question_ids"][current_index]
        user_answers = lobby.get("participants_answers", {}).get(user_id, {})
        question_index = lobby["question_ids"].index(question_id)
        
        # Проверка доступа к вопросу (упрощенная для мультиплеера)
        if not is_host:
            # В мультиплеере разрешаем доступ к текущему и предыдущим вопросам
            # Запрещаем только доступ к будущим вопросам
            if question_index > current_index:
                logger.warning(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.SECURITY,
                    message=f"Попытка доступа к будущему вопросу: пользователь {user_id} пытается получить вопрос {question_id} (индекс {question_index}), текущий индекс {current_index}"
                )
                raise HTTPException(status_code=403, detail="Доступ к этому вопросу пока не разрешен")

        # Запрашиваем вопрос из коллекции вопросов
        question = await db.questions.find_one({"_id": ObjectId(question_id)})
        if not question:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Вопрос не найден в БД: вопрос {question_id} не найден в коллекции questions"
            )
            raise HTTPException(status_code=404, detail="Вопрос не найден")
        
        # Проверяем, отвечал ли уже пользователь на этот вопрос
        has_answered = question_id in user_answers
        
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
            "media_file_id": str(question.get("media_file_id")) if question.get("media_file_id") else None,
            "has_after_answer_media": question_data.get("has_after_answer_media", False) and has_answered,
            "after_answer_media_type": question_data.get("after_answer_media_type", "image") if has_answered else None,
            "after_answer_media_file_id": str(question.get("after_answer_media_file_id") or question.get("after_answer_media_id")) if (question.get("after_answer_media_file_id") or question.get("after_answer_media_id")) and has_answered else None
        }
        
        # Если пользователь уже ответил и это не экзаменационный режим, добавляем объяснение
        if has_answered and not lobby.get("exam_mode", False):
            question_out["explanation"] = question.get("explanation", {})
        else:
            question_out["explanation"] = None  # Объяснение будет доступно только после ответа
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Вопрос успешно возвращён: пользователь {user_id} получил вопрос {question_id} в лобби {lobby_id}, уже отвечал: {has_answered}"
        )
        return success(data=question_out)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения вопроса: лобби {lobby_id}, вопрос {question_id}, пользователь {user_id}, ошибка {str(e)}"
        )
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
    Возвращает индекс правильного ответа на вопрос.
    Доступно только участникам лобби после того, как они ответили на вопрос.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Запрос правильного ответа: пользователь {user_id}, вопрос {question_id}, лобби {lobby_id}"
    )
    
    try:
        # Проверяем доступ к лобби
        await validate_lobby_access(lobby_id, user_id)
        
        # Получаем информацию о лобби
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем, что вопрос принадлежит лобби
        if question_id not in lobby.get("question_ids", []):
            raise HTTPException(status_code=404, detail="Вопрос не найден в данном лобби")
        
        # Получаем правильный ответ из лобби
        correct_answers = lobby.get("correct_answers", {})
        if question_id not in correct_answers:
            logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Правильный ответ не найден: вопрос {question_id} отсутствует в лобби {lobby_id}"
        )
            raise HTTPException(status_code=404, detail="Правильный ответ не найден")
        
        correct_answer_index = correct_answers[question_id]
        
        # Проверяем, ответил ли пользователь на этот вопрос (или является хостом)
        is_host = user_id == lobby.get("host_id")
        user_answers = lobby.get("participants_answers", {}).get(user_id, {})
        has_answered = question_id in user_answers
        
        # В экзаменационном режиме правильные ответы показываются только после завершения теста
        if lobby.get("exam_mode", False) and lobby.get("status") != "finished":
            if not is_host:
                raise HTTPException(status_code=403, detail="В экзаменационном режиме правильные ответы доступны только после завершения теста")
        
        # Обычные участники могут видеть правильный ответ только после того, как ответили на вопрос
        elif not is_host and not has_answered:
            raise HTTPException(status_code=403, detail="Вы должны сначала ответить на вопрос")
        
        # Получаем дополнительную информацию о вопросе из questions_data или напрямую из базы
        questions_data = lobby.get("questions_data", {})
        question_data = questions_data.get(question_id, {})
        explanation = question_data.get("explanation", "")
        
        # Если объяснения нет в лобби, получаем его из базы данных  
        question = None
        if not explanation:
            question = await db.questions.find_one({"_id": ObjectId(question_id)})
            if question:
                explanation = question.get("explanation", {})
                logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Получено объяснение из БД: вопрос {question_id}, тип {type(explanation)}, содержимое {str(explanation)[:100] if explanation else 'пусто'}"
        )
        
        # Проверяем наличие медиа после ответа
        has_after_media = bool(
            question_data.get("after_answer_media_file_id") or 
            question_data.get("after_answer_media_id")
        )
        
        # Если не нашли в данных лобби, проверяем в базе данных
        if not has_after_media and not question:
            question = await db.questions.find_one({"_id": ObjectId(question_id)})
        
        if question and not has_after_media:
            has_after_media = bool(
                question.get("after_answer_media_file_id") or 
                question.get("after_answer_media_id")
            )
        
        return success(data={
            "question_id": question_id,
            "correct_answer_index": correct_answer_index,
            "explanation": explanation,
            "has_after_answer_media": has_after_media
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения правильного ответа: лобби {lobby_id}, вопрос {question_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при получении правильного ответа")

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
    
    # Rate limiting
    if not rate_limiter.check_rate_limit(user_id):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    question_id = payload.question_id
    answer_index = payload.answer_index
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Получен ответ на вопрос: пользователь {user_id} отвечает на вопрос {question_id} в лобби {lobby_id}, ответ {answer_index}"
    )
    
    # Валидация входных данных
    if not validate_object_id(question_id):
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Некорректный формат ID вопроса: пользователь {user_id} передал неверный ID {question_id}"
        )
        raise HTTPException(status_code=400, detail="Invalid question ID format")
    
    if not isinstance(answer_index, int) or answer_index < 0:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Некорректный индекс ответа: пользователь {user_id} передал {answer_index} типа {type(answer_index)}"
        )
        raise HTTPException(status_code=400, detail="Invalid answer index")
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.VALIDATION,
        message=f"Валидация входных данных пройдена: пользователь {user_id}, вопрос {question_id}, ответ {answer_index}"
    )
    
    # Проверка целостности данных
    if not await validate_answer_integrity(lobby_id, question_id, answer_index):
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Нарушение целостности ответа: пользователь {user_id}, лобби {lobby_id}, вопрос {question_id}, ответ {answer_index} не прошёл проверку"
        )
        raise HTTPException(status_code=400, detail="Invalid answer data")
    
    try:
        # Получаем информацию о лобби
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Лобби не найдено: пользователь {user_id} пытается ответить в несуществующее лобби {lobby_id}"
            )
            raise HTTPException(status_code=404, detail="Лобби не найдено")
            
        # Проверяем, является ли пользователь участником лобби
        if user_id not in lobby["participants"]:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Нет доступа к лобби: пользователь {user_id} не является участником лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вы не участник данного лобби")
            
        # Проверяем, относится ли вопрос к данному лобби
        if question_id not in lobby.get("question_ids", []):
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Вопрос не принадлежит лобби: пользователь {user_id} пытается ответить на вопрос {question_id}, не принадлежащий лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вопрос не относится к данному лобби")
            
        # Проверяем статус лобби
        if lobby["status"] != "in_progress":
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.LIFECYCLE,
                message=f"Неверный статус лобби: лобби {lobby_id} имеет статус {lobby['status']}, ожидается in_progress для ответа"
            )
            raise HTTPException(status_code=400, detail="Лобби не активно")
        
        # Проверяем, не отвечал ли пользователь уже на этот вопрос
        user_answers = lobby.get("participants_answers", {}).get(user_id, {})
        if question_id in user_answers:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Попытка повторного ответа: пользователь {user_id} уже отвечал на вопрос {question_id} в лобби {lobby_id}"
            )
            raise HTTPException(status_code=400, detail="Вы уже ответили на этот вопрос")
        
        # Получаем информацию о текущем вопросе и индексе в последовательности
        current_index = lobby.get("current_index", 0)
        question_ids = lobby.get("question_ids", [])
        current_question_id = question_ids[current_index] if current_index < len(question_ids) else None
        
        # Получаем индекс запрашиваемого вопроса
        try:
            question_index = question_ids.index(question_id)
        except ValueError:
            logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Вопрос не в лобби: вопрос {question_id} отсутствует в списке вопросов лобби {lobby_id}"
        )
            raise HTTPException(status_code=400, detail="Вопрос не найден в списке вопросов")
        
        # Хост может отвечать на любой вопрос
        is_host = user_id == lobby.get("host_id")
        
        # В мультиплеерном режиме участники могут отвечать на текущий и предыдущие вопросы
        if not is_host:
            # Проверяем, что это не вопрос из будущего
            if question_index > current_index:
                logger.warning(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.SECURITY,
                    message=f"Попытка ответить раньше времени: пользователь {user_id} пытается ответить на вопрос {question_id} (индекс {question_index}), текущий индекс {current_index}"
                )
                raise HTTPException(status_code=403, detail="Вы не можете отвечать на этот вопрос, пока не дойдете до него")
            
            # В мультиплеере разрешаем отвечать на любые предыдущие вопросы без ограничений
            # Это позволяет участникам догонять, если они пропустили вопросы
        
        # Проверяем правильность ответа
        correct_answer = lobby["correct_answers"].get(question_id)
        if correct_answer is None:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Правильный ответ не найден: для вопроса {question_id} в лобби {lobby_id} отсутствует правильный ответ"
            )
            raise HTTPException(status_code=500, detail="Правильный ответ для данного вопроса не найден")
        
        # Проверяем валидность индекса ответа
        question = await db.questions.find_one({"_id": ObjectId(question_id)})
        if question and "options" in question:
            options_count = len(question["options"])
            if answer_index < 0 or answer_index >= options_count:
                logger.warning(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.VALIDATION,
                    message=f"Недопустимый индекс ответа: пользователь {user_id} отправил индекс {answer_index}, доступно вариантов {options_count}"
                )
                raise HTTPException(status_code=400, detail=f"Недопустимый индекс ответа. Должен быть от 0 до {options_count-1}")
        
        is_correct = (answer_index == correct_answer)
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Ответ обработан: пользователь {user_id} ответил на вопрос {question_id} - {'правильно' if is_correct else 'неправильно'} (ответ {answer_index}, правильный {correct_answer})"
        )
        
        # Получаем информацию о вопросе для ответа (нужно получить до формирования response_data)
        question = await db.questions.find_one({"_id": ObjectId(question_id)})
        explanation = question.get("explanation", {}) if question else {}
        
        # Сохраняем ответ пользователя в коллекцию user_answers
        answer_doc = {
            "user_id": user_id,
            "lobby_id": lobby_id,
            "question_id": question_id,
            "answer_index": answer_index,
            "is_correct": is_correct,
            "timestamp": datetime.utcnow()
        }
        
        # Batch операции для оптимизации производительности
        try:
            # Выполняем обе операции записи параллельно
            insert_task = db.user_answers.insert_one(answer_doc)
            update_task = db.lobbies.update_one(
                {"_id": lobby_id},
                {"$set": {
                    f"participants_answers.{user_id}.{question_id}": is_correct,
                    f"participants_raw_answers.{user_id}.{question_id}": answer_index
                }}
            )
            
            # Ждем завершения обеих операций
            await asyncio.gather(insert_task, update_task)
            
            # Инвалидируем кэш лобби после изменения
            lobby_cache.invalidate_lobby(lobby_id)
            
        except Exception as e:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.DATABASE,
                message=f"Ошибка сохранения ответа в БД: лобби {lobby_id}, пользователь {user_id}, вопрос {question_id}, ошибка {str(e)}"
            )
            raise HTTPException(status_code=500, detail="Ошибка при сохранении ответа")

        # Формируем ответ для пользователя
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

        # WebSocket уведомления отправляем в фоне для не блокирования ответа
        async def send_ws_notifications():
            try:
                # Получаем информацию о лобби для определения хоста
                current_lobby = await db.lobbies.find_one({"_id": lobby_id})
                host_id = current_lobby.get("host_id") if current_lobby else None
                
                # Отправляем информацию о том, что участник ответил
                # Хосту отправляем с деталями ответа, остальным - без
                participants = current_lobby.get("participants", []) if current_lobby else []
                
                for participant_id in participants:
                    if participant_id == host_id:
                        # Хосту отправляем полную информацию
                        await ws_manager.send_to_user(lobby_id, participant_id, {
                            "type": "answer_received",
                            "data": {
                                "user_id": user_id,
                                "question_id": question_id,
                                "answer_index": answer_index,  # Только хост видит индекс ответа
                                "is_correct": is_correct
                            }
                        })
                    else:
                        # Обычным участникам отправляем без деталей ответа
                        await ws_manager.send_to_user(lobby_id, participant_id, {
                            "type": "answer_received",
                            "data": {
                                "user_id": user_id,
                                "question_id": question_id,
                                "is_correct": is_correct  # Без answer_index
                            }
                        })
                
                # Дополнительно отправляем уведомление о том, что участник ответил (всем)
                await ws_manager.send_json_parallel(lobby_id, {
                    "type": "participant_answered",
                    "data": {
                        "user_id": user_id,
                        "question_id": question_id,
                        "answered": True
                    }
                })
            except Exception as e:
                logger.error(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.ERROR,
                    message=f"Ошибка отправки WS уведомления об ответе: лобби {lobby_id}, пользователь {user_id}, вопрос {question_id}, ошибка {str(e)}"
                )

        # Запускаем WebSocket уведомления в фоне
        asyncio.create_task(send_ws_notifications())
        
        # Проверка завершения вопроса в фоне (не блокирует ответ пользователю)
        async def check_question_completion():
            try:
                # Получаем свежие данные лобби
                updated_lobby = await db.lobbies.find_one({"_id": lobby_id})
                if not updated_lobby:
                    return
                    
                current_index = updated_lobby.get("current_index", 0)
                question_ids = updated_lobby.get("question_ids", [])
                
                if current_index >= len(question_ids):
                    return
                    
                current_question_id = question_ids[current_index]
                participants = updated_lobby.get("participants", [])
                participants_answers = updated_lobby.get("participants_answers", {})
                
                # Проверяем, все ли участники ответили на текущий вопрос
                # В мультиплеере не требуем ответов от всех - переход управляется хостом
                answered_count = sum(
                    1 for participant_id in participants
                    if current_question_id in participants_answers.get(participant_id, {})
                )
                
                # Автоматический переход только если ответили больше половины участников
                # или если прошло достаточно времени (можно добавить таймер позже)
                min_answers_for_auto_advance = max(1, len(participants) // 2)  # Минимум половина
                should_auto_advance = answered_count >= min_answers_for_auto_advance
                
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.LIFECYCLE,
                    message=f"Проверка завершения вопроса: вопрос {current_question_id}, ответили {answered_count}/{len(participants)} участников, автопереход {should_auto_advance}"
                )
                
                # В мультиплеере переход к следующему вопросу управляется только хостом
                # Автоматический переход отключен для лучшего контроля
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.LIFECYCLE,
                    message=f"Ожидание действий хоста: вопрос {current_question_id}, ответили {answered_count}/{len(participants)} участников, переход контролирует хост"
                )
                
                # Уведомляем хоста о статусе ответов
                await ws_manager.send_json_parallel(lobby_id, {
                    "type": "question_status",
                    "data": {
                        "question_id": current_question_id,
                        "answered_count": answered_count,
                        "total_participants": len(participants),
                        "can_advance": answered_count > 0  # Хост может перейти если хотя бы кто-то ответил
                    }
                })
                

                        
            except Exception as e:
                logger.error(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.ERROR,
                    message=f"Ошибка проверки завершения вопроса: лобби {lobby_id}, вопрос {current_question_id}, ошибка {str(e)}"
                )

        # Запускаем проверку завершения вопроса в фоне
        asyncio.create_task(check_question_completion())

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

        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Ответ успешно обработан: пользователь {user_id} ответил на вопрос {question_id} в лобби {lobby_id}, результат {'верно' if is_correct else 'неверно'}"
        )
        return success(data=response_data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Критическая ошибка обработки ответа: пользователь {user_id}, лобби {lobby_id}, вопрос {question_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")



@router.post("/lobbies/{lobby_id}/skip", summary="Пропустить текущий вопрос")
async def skip_question(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Хост пропускает текущий вопрос и переходит к следующему.
    Результаты пользователей, которые успели ответить, сохраняются.
    Результаты не ответивших пользователей на этот вопрос не учитываются.
    """
    user_id = get_user_id(current_user)
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.LIFECYCLE,
        message=f"Запрос пропуска вопроса: хост {user_id} пропускает текущий вопрос в лобби {lobby_id}"
    )
    
    lobby = await db.lobbies.find_one({"_id": lobby_id})
    if not lobby:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Попытка пропуска в несуществующем лобби: пользователь {user_id}, лобби {lobby_id}"
        )
        raise HTTPException(status_code=404, detail="Лобби не найдено")
    if lobby["host_id"] != user_id:
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Попытка пропуска не-хостом: пользователь {user_id} не является хостом лобби {lobby_id}"
        )
        raise HTTPException(status_code=403, detail="Только хост может пропускать вопросы")
    if lobby["status"] != "in_progress":
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.SECURITY,
            message=f"Попытка пропуска в неактивном лобби: лобби {lobby_id} имеет статус {lobby['status']}"
        )
        raise HTTPException(status_code=400, detail="Тест не запущен")

    current_index = lobby.get("current_index", 0)
    total_questions = len(lobby.get("question_ids", []))
    
    # Если текущий вопрос не последний и не достигнуто 40 вопросов, перейдем к следующему
    if current_index < total_questions - 1 and current_index < 39:  # 0-based index, 39 = 40 вопросов
        new_index = current_index + 1
        await db.lobbies.update_one({"_id": lobby_id}, {"$set": {"current_index": new_index}})
        next_question_id = lobby["question_ids"][new_index]
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.LIFECYCLE,
            message=f"Вопрос пропущен: лобби {lobby_id}, переход с индекса {current_index} на {new_index}, следующий вопрос {next_question_id}"
        )
        
        # Уведомляем всех по WebSocket о переходе к следующему вопросу
        await ws_manager.send_json(lobby_id, {
            "type": "skip_to",
            "data": {"question_id": next_question_id}
        })

        return success(data={"message": "Вопрос пропущен, переход к следующему"})
    else:
        # Если это был последний вопрос или уже ответили на 40 вопросов, завершаем тест
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.LIFECYCLE,
            message=f"Тест завершён пропуском: лобби {lobby_id}, индекс {current_index}, всего вопросов {total_questions}"
        )
        
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

@router.post("/lobbies/{lobby_id}/next-question", summary="Перейти к следующему вопросу (мультиплеер)")
async def next_question_multiplayer(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """
    Переходит к следующему вопросу в мультиплеерном режиме.
    Только хост может управлять переходом между вопросами.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.LIFECYCLE,
        message=f"Запрос перехода к следующему вопросу: хост {user_id} пытается перейти к следующему вопросу в лобби {lobby_id}"
    )
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Только хост может управлять вопросами")
        
        if lobby["status"] != "in_progress":
            raise HTTPException(status_code=400, detail="Тест не запущен")
        
        current_index = lobby.get("current_index", 0)
        total_questions = len(lobby.get("question_ids", []))
        
        if current_index >= total_questions - 1:
            # Завершаем тест
            await db.lobbies.update_one(
                {"_id": lobby_id}, 
                {"$set": {"status": "finished", "finished_at": datetime.utcnow()}}
            )
            
            # Отправляем уведомление о завершении теста
            await ws_manager.send_json(lobby_id, {
                "type": "test_finished",
                "data": {"message": "Тест завершен"}
            })
            
            return success(data={"message": "Тест завершен"})
        
        # Переходим к следующему вопросу
        new_index = current_index + 1
        await db.lobbies.update_one(
            {"_id": lobby_id}, 
            {"$set": {"current_index": new_index}}
        )
        
        # Инвалидируем кэш лобби, чтобы участники получили обновленный current_index
        lobby_cache.invalidate_lobby(lobby_id)
        
        next_question_id = lobby["question_ids"][new_index]
        
        # Отправляем WebSocket уведомление о переходе к следующему вопросу
        await ws_manager.send_json_parallel(lobby_id, {
            "type": "next_question",
            "data": {
                "question_id": next_question_id,
                "question_index": new_index
            }
        })
        
        return success(data={"message": "Переход к следующему вопросу", "question_index": new_index})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка перехода к следующему вопросу: лобби {lobby_id}, хост {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при переходе к следующему вопросу")

@router.post("/lobbies/{lobby_id}/kick", summary="Исключить участника из лобби")
async def kick_participant(
    lobby_id: str,
    request: KickParticipantRequest,
    current_user: dict = Depends(get_current_actor)
):
    """
    Исключает участника из лобби и добавляет в черный список.
    Только хост может исключать участников.
    """
    user_id = get_user_id(current_user)
    target_user_id = request.target_user_id
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.SECURITY,
        message=f"Запрос исключения участника: хост {user_id} исключает участника {target_user_id} из лобби {lobby_id}"
    )
    
    try:
        # Получаем информацию о лобби
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем, что пользователь является хостом
        if lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Только хост может исключать участников")
        
        # Проверяем, что исключаемый пользователь действительно участник лобби
        if target_user_id not in lobby.get("participants", []):
            raise HTTPException(status_code=400, detail="Пользователь не является участником лобби")
        
        # Хост не может исключить самого себя
        if target_user_id == user_id:
            raise HTTPException(status_code=400, detail="Хост не может исключить самого себя")
        
        # Получаем информацию об исключаемом пользователе
        kicked_user_name = "Участник"
        try:
            if target_user_id.startswith("guest_"):
                kicked_user_name = f"Гость {target_user_id[-8:]}"
            else:
                user_response = await db.users.find_one({"_id": ObjectId(target_user_id)})
                if user_response:
                    kicked_user_name = user_response.get("full_name", "Участник")
        except Exception as e:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.DATABASE,
                message=f"Не удалось получить имя исключаемого пользователя: пользователь {target_user_id}, ошибка {str(e)}"
            )
        
        # Убираем участника из лобби и добавляем в черный список
        update_result = await db.lobbies.update_one(
            {"_id": lobby_id},
            {
                "$pull": {"participants": target_user_id},
                "$addToSet": {"blacklisted_users": target_user_id},  # Добавляем в черный список
                "$unset": {f"participants_answers.{target_user_id}": ""}  # Удаляем ответы
            }
        )
        
        if update_result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Не удалось исключить участника")
        
        # Инвалидируем кэш лобби
        lobby_cache.invalidate_lobby(lobby_id)
        
        # Отправляем WebSocket уведомления
        try:
            # Уведомляем исключенного пользователя
            await ws_manager.send_json_to_user(target_user_id, {
                "type": "user_kicked",
                "data": {
                    "lobby_id": lobby_id,
                    "message": "Вы были исключены из лобби хостом",
                    "kicked_by": user_id,
                    "redirect": True
                }
            })
            
            # Уведомляем всех остальных участников
            await ws_manager.send_json_parallel(lobby_id, {
                "type": "participant_kicked",
                "data": {
                    "user_id": target_user_id,
                    "user_name": kicked_user_name,
                    "kicked_by": user_id
                }
            })
            
        except Exception as e:
            logger.error(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.ERROR,
                message=f"Ошибка отправки WS уведомления об исключении: лобби {lobby_id}, исключён {target_user_id}, ошибка {str(e)}"
            )
        
        return success(data={
            "message": f"Участник {kicked_user_name} исключен из лобби",
            "kicked_user_id": target_user_id,
            "kicked_user_name": kicked_user_name
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка исключения участника: лобби {lobby_id}, хост {user_id}, исключаемый {target_user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при исключении участника")

@router.post("/lobbies/{lobby_id}/close", summary="Закрыть лобби")
async def close_lobby(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Закрывает лобби (удаляет его).
    Только хост может закрыть лобби.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.LIFECYCLE,
        message=f"Запрос закрытия лобби: пользователь {user_id} пытается закрыть лобби {lobby_id}"
    )
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Только хост может закрыть лобби
        if lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Только хост может закрыть лобби")
        
        # Нельзя закрыть уже завершенное лобби
        if lobby["status"] == "finished":
            raise HTTPException(status_code=400, detail="Лобби уже завершено")
        
        # Сначала оповещаем всех участников о закрытии лобби
        try:
            await ws_manager.broadcast_to_lobby(lobby_id, {
                "type": "lobby_closed",
                "data": {"message": "Лобби было закрыто хостом", "redirect": True}
            })
            logger.info(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
                message=f"Отправлено WS уведомление о закрытии: лобби {lobby_id} закрывается хостом {user_id}"
            )
        except Exception as e:
            logger.error(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.ERROR,
                message=f"Ошибка отправки WS уведомления о закрытии: лобби {lobby_id}, ошибка {str(e)}"
            )
        
        # Ждем немного, чтобы сообщение дошло до клиентов
        await asyncio.sleep(1)
        
        # Помечаем лобби как закрытое вместо удаления
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {
                "$set": {
                    "status": "closed",
                    "closed_at": datetime.utcnow(),
                    "closed_by": user_id,
                    "participants": []  # Очищаем список участников
                }
            }
        )
        
        # Инвалидируем кэш
        lobby_cache.invalidate_lobby(lobby_id)
        
        # Закрываем все WebSocket соединения для этого лобби
        try:
            if lobby_id in ws_manager.connections:
                connections_to_close = list(ws_manager.connections[lobby_id])
                for conn in connections_to_close:
                    try:
                        await conn["websocket"].close(code=1000, reason="Lobby closed")
                    except Exception as e:
                        logger.error(
                            section=LogSection.WEBSOCKET,
                            subsection=LogSubsection.WEBSOCKET.ERROR,
                            message=f"Ошибка закрытия WS соединения: пользователь {conn['user_id']}, ошибка {str(e)}"
                        )
                # Очищаем список соединений
                del ws_manager.connections[lobby_id]
        except Exception as e:
            logger.error(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.ERROR,
                message=f"Ошибка закрытия WS соединений: лобби {lobby_id}, ошибка {str(e)}"
            )
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.LIFECYCLE,
            message=f"Лобби успешно закрыто: лобби {lobby_id} закрыто пользователем {user_id}"
        )
        return success(data={"message": "Лобби успешно закрыто"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка закрытия лобби: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при закрытии лобби")

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
        if lobby["mode"] in ["multi", "multiplayer"] and lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Только хост может завершить тест")
        
        if lobby["mode"] not in ["multi", "multiplayer"] and lobby["host_id"] != user_id:
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
                "duration_seconds": duration,
                "finish_reason": "manual"
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
                    "detailed_results": detailed_results[participant_id],
                    "exam_mode": lobby.get("exam_mode", False),
                    "finish_reason": "manual"
                }
                await db.history.insert_one(history_record)
            except Exception as e:
                # Логируем ошибку, но не прерываем выполнение для остальных участников
                logger.error(
                    section=LogSection.DATABASE,
                    subsection=LogSubsection.DATABASE.ERROR,
                    message=f"Ошибка сохранения истории: пользователь {participant_id}, лобби {lobby_id}, ошибка {str(e)}"
                )
        
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
            logger.error(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.ERROR,
                message=f"Ошибка отправки WS уведомления о завершении: лобби {lobby_id}, ошибка {str(e)}"
            )
        
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
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Неожиданная ошибка завершения лобби: лобби {lobby_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при завершении теста")

@router.get("/lobbies/{lobby_id}/public", summary="Получить публичную информацию о лобби")
async def get_lobby_public_info(lobby_id: str):
    """
    Получает публичную информацию о лобби для страницы присоединения.
    Не требует аутентификации.
    """
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Получаем информацию о хосте
        host = await db.users.find_one({"_id": ObjectId(lobby["host_id"])})
        if not host:
            raise HTTPException(status_code=404, detail="Хост лобби не найден")
        
        # Получаем подписку хоста
        host_subscription = await db.subscriptions.find_one({
            "user_id": ObjectId(lobby["host_id"]),
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        host_subscription_type = host_subscription.get("subscription_type", "Demo") if host_subscription else "Demo"
        
        # Calculate remaining time if lobby is active
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
            "host_name": host.get("full_name", "Unknown"),
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

@router.get("/lobbies/{lobby_id}", summary="Получить информацию о лобби")
async def get_lobby(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor),
    t: str = Query(None, description="Timestamp for cache busting"),
    retry: str = Query(None, description="Retry flag for cache refresh")
):
    """
    Получает информацию о лобби по его ID.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Запрос информации о лобби: пользователь {user_id} запрашивает данные лобби {lobby_id}"
    )
    
    try:
        # Принудительно обновляем кеш если есть параметры cache-busting
        force_refresh = bool(t or retry)
        
        # Получаем лобби из кэша
        lobby = await lobby_cache.get_lobby(lobby_id, force_refresh=force_refresh)
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        is_host = user_id == lobby.get("host_id")
        
        # Получаем тип подписки хоста
        host_subscription = await lobby_cache.get_user_subscription(lobby["host_id"])
        host_subscription_type = host_subscription["subscription_type"] if host_subscription else "Demo"
        
        # Calculate remaining time if lobby is active
        remaining_seconds = 0
        if lobby["status"] in ["waiting", "in_progress"] and lobby.get("created_at"):
            lobby_age = (datetime.utcnow() - lobby["created_at"]).total_seconds()
            remaining_seconds = max(0, MAX_LOBBY_LIFETIME - lobby_age)
            
            # Логирование для отладки
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.LIFECYCLE,
                message=f"Расчёт времени лобби: лобби {lobby_id}, создано {lobby['created_at']}, возраст {lobby_age:.2f}с, осталось {remaining_seconds:.2f}с"
            )
        
        # Получаем имя хоста (можно кэшировать, но для этого нужен отдельный кэш пользователей)
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
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Информация о лобби возвращена: лобби {lobby_id}, пользователь {user_id}"
        )
        return success(data=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения информации о лобби: лобби {lobby_id}, ошибка {str(e)}"
        )
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
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения списка ответивших пользователей: лобби {lobby_id}, ошибка {str(e)}"
        )
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
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения результатов теста: лобби {lobby_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при получении результатов теста")

@router.get("/active-lobby", summary="Получить информацию об активном лобби пользователя")
async def get_user_active_lobby(current_user: dict = Depends(get_current_actor)):
    """
    Проверяет, есть ли у пользователя активное лобби, и возвращает информацию о нем
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Проверка активного лобби: пользователь {user_id} запрашивает информацию о текущем активном лобби"
    )
    
    try:
        # Ищем активное лобби пользователя (исключаем закрытые и завершенные)
        active_lobby = await db.lobbies.find_one({
            "participants": user_id,
            "status": {"$nin": ["finished", "closed"]}
        })
        
        if not active_lobby:
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Нет активных лобби: пользователь {user_id} не участвует в активных лобби"
            )
            return success(data={"has_active_lobby": False})
        
        # Проверяем, не истёк ли срок действия лобби (4 часа)
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
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.LIFECYCLE,
                    message=f"Автозавершение просроченного лобби: лобби {active_lobby['_id']} завершено автоматически по истечении времени жизни"
                )
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
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка проверки активного лобби: пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при проверке активного лобби")

@router.get("/categories/stats", summary="Получить статистику по категориям и количеству вопросов")
async def get_categories_stats(current_user: dict = Depends(get_current_actor)):
    """
    Возвращает статистику по категориям и количеству вопросов в каждой.
    
    Группирует вопросы по категориям и подсчитывает количество уникальных вопросов в каждой группе.
    Также возвращает общее количество вопросов.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.API,
        subsection=LogSubsection.API.REQUEST,
        message=f"Запрос статистики категорий: пользователь {user_id} запрашивает статистику по категориям вопросов"
    )
    
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
        
        logger.info(
            section=LogSection.API,
            subsection=LogSubsection.API.RESPONSE,
            message=f"Статистика категорий: найдено {len(categories_dict)} категорий, общее количество вопросов {total_questions}"
        )
        
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
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Ошибка получения статистики категорий: пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@router.get("/lobbies/{lobby_id}/online-users", summary="Получить список онлайн пользователей в лобби")
async def get_online_users(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """
    Получить список пользователей, которые в данный момент онлайн в лобби
    """
    try:
        user_id = get_user_id(current_user)
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Запрос онлайн пользователей: пользователь {user_id} запрашивает список онлайн участников лобби {lobby_id}"
        )
        
        # Проверяем доступ к лобби
        lobby, is_host, subscription_type = await validate_lobby_access(
            lobby_id, user_id, is_guest=current_user.get("is_guest", False)
        )
        
        # Получаем список онлайн пользователей из WebSocket менеджера
        online_user_ids = ws_manager.get_online_users(lobby_id)
        
        # Получаем информацию о пользователях
        online_users = []
        for online_user_id in online_user_ids:
            try:
                user_info = await ws_manager.get_user_info(online_user_id)
                online_users.append({
                    "user_id": online_user_id,
                    "name": user_info.get("full_name", "Unknown"),
                    "is_host": online_user_id == lobby.get("host_id"),
                    "is_guest": user_info.get("is_guest", False)
                })
            except Exception as e:
                logger.error(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.ERROR,
                    message=f"Ошибка получения информации о пользователе: пользователь {online_user_id}, ошибка {str(e)}"
                )
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Список онлайн пользователей: возвращено {len(online_users)} онлайн участников для лобби {lobby_id}"
        )
        
        return success(data={
            "lobby_id": lobby_id,
            "online_users": online_users,
            "total_online": len(online_users),
            "total_participants": len(lobby.get("participants", []))
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения онлайн пользователей: лобби {lobby_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.post("/lobbies/{lobby_id}/leave", summary="Выйти из лобби")
async def leave_lobby(lobby_id: str, current_user: dict = Depends(get_current_actor)):
    """
    Выход пользователя из лобби.
    Если выходит хост, лобби закрывается.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.LIFECYCLE,
        message=f"Выход из лобби: пользователь {user_id} покидает лобби {lobby_id}"
    )
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if user_id not in lobby["participants"]:
            raise HTTPException(status_code=400, detail="Вы не участник этого лобби")
        
        # Если выходит хост, закрываем лобби
        if lobby["host_id"] == user_id:
            # Уведомляем всех участников о закрытии лобби
            await ws_manager.broadcast_to_lobby(lobby_id, {
                "type": "lobby_closed",
                "data": {"message": "Хост покинул лобби", "redirect": True}
            })
            
            # Помечаем лобби как закрытое
            await db.lobbies.update_one(
                {"_id": lobby_id},
                {
                    "$set": {
                        "status": "closed",
                        "closed_at": datetime.utcnow(),
                        "closed_by": user_id,
                        "participants": []
                    }
                }
            )
        else:
            # Обычный участник выходит
            await db.lobbies.update_one(
                {"_id": lobby_id},
                {"$pull": {"participants": user_id}}
            )
            
            # Уведомляем остальных участников
            await ws_manager.broadcast_to_lobby(lobby_id, {
                "type": "participant_left",
                "data": {"user_id": user_id}
            })
        
        # Инвалидируем кэш
        lobby_cache.invalidate_lobby(lobby_id)
        
        return success(data={"message": "Вы покинули лобби"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка выхода из лобби: пользователь {user_id}, лобби {lobby_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при выходе из лобби")

class ShowCorrectAnswerRequest(BaseModel):
    question_id: str
    question_index: int

@router.post("/lobbies/{lobby_id}/show-correct-answer", summary="Показать правильный ответ")
async def show_correct_answer(
    lobby_id: str,
    request_data: ShowCorrectAnswerRequest = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Показывает правильный ответ на текущий вопрос всем участникам.
    Только хост может управлять показом правильных ответов.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Показ правильного ответа: хост {user_id} показывает правильный ответ в лобби {lobby_id}"
    )
    
    try:
        # Инвалидируем кэш для получения актуального состояния лобби
        lobby_cache.invalidate_lobby(lobby_id)
        
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Только хост может показывать правильные ответы")
        
        if lobby["status"] != "in_progress":
            raise HTTPException(status_code=400, detail="Тест не запущен")
        
        # Используем данные из запроса, если переданы, иначе берем из базы
        if request_data and request_data.question_id:
            current_question_id = request_data.question_id
            current_index = request_data.question_index
            logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Использование вопроса из запроса: вопрос {current_question_id}, индекс {current_index}"
        )
        else:
            current_index = lobby.get("current_index", 0)
            question_ids = lobby.get("question_ids", [])
            
            if current_index >= len(question_ids):
                raise HTTPException(status_code=400, detail="Нет текущего вопроса")
            
            current_question_id = question_ids[current_index]
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.QUESTIONS,
                message=f"Использование вопроса из состояния лобби: вопрос {current_question_id}, индекс {current_index}"
            )
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Отладка показа ответа: лобби {lobby_id}, индекс {current_index}, вопрос {current_question_id}"
        )
        
        # Получаем правильный ответ из лобби (уже преобразован в индекс)
        correct_answers = lobby.get("correct_answers", {})
        correct_answer_index = correct_answers.get(str(current_question_id), 0)
        
        # Получаем данные вопроса из базы данных для объяснения и медиа
        question = await db.questions.find_one({"_id": ObjectId(current_question_id)})
        explanation = question.get("explanation", "") if question else ""
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Вопрос найден: вопрос {current_question_id}, индекс правильного ответа {correct_answer_index}"
        )
        
        # Проверяем, есть ли медиа после ответа
        has_after_media = bool(
            question.get("has_after_media", False) or 
            question.get("has_after_answer_media", False) or
            question.get("after_answer_media_file_id") or
            question.get("after_answer_media_id")
        )
        
        # Определяем тип медиа после ответа
        after_answer_media_type = ""
        if has_after_media:
            filename = question.get("after_answer_media_filename", "")
            if filename:
                is_video = filename.lower().endswith((".mp4", ".webm", ".mov", ".avi"))
                after_answer_media_type = "video" if is_video else "image"
            else:
                after_answer_media_type = "image"  # Default
        
        # Получаем после-ответный media_file_id если есть
        after_answer_media_file_id = None
        if has_after_media:
            after_answer_media_file_id = question.get("after_answer_media_file_id") or question.get("after_answer_media_id")
        
        # Отправляем WebSocket уведомление всем участникам
        from app.websocket.lobby_ws import ws_manager
        
        websocket_data = {
            "type": "show_correct_answer",
            "data": {
                "question_id": str(current_question_id),
                "correct_answer_index": correct_answer_index,
                "explanation": explanation,
                "has_after_media": has_after_media,
                "after_answer_media_type": after_answer_media_type,
                "after_answer_media_file_id": str(after_answer_media_file_id) if after_answer_media_file_id else None,
                "question_index": current_index  # Добавляем индекс для дополнительной проверки
            }
        }
        
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
            message=f"Отправка WS сообщения show_correct_answer: вопрос {current_question_id}, индекс {current_index}, данные отправлены"
        )
        
        await ws_manager.send_json_parallel(lobby_id, websocket_data)
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Правильный ответ показан: лобби {lobby_id}, вопрос {current_question_id}, ответ {correct_answer_index}"
        )
        
        return success(data={
            "message": "Правильный ответ показан всем участникам",
            "question_id": str(current_question_id),
            "correct_answer_index": correct_answer_index,
            "explanation": explanation
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка показа правильного ответа: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при показе правильного ответа")

@router.post("/lobbies/{lobby_id}/toggle-participant-answers", summary="Переключить видимость ответов участников")
async def toggle_participant_answers(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """
    Переключает видимость ответов участников для хоста.
    Только хост может управлять видимостью ответов.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Переключение видимости ответов: хост {user_id} изменяет видимость ответов участников в лобби {lobby_id}"
    )
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Только хост может управлять видимостью ответов")
        
        if lobby["status"] != "in_progress":
            raise HTTPException(status_code=400, detail="Тест не запущен")
        
        # Переключаем состояние видимости ответов
        current_visibility = lobby.get("show_participant_answers", False)
        new_visibility = not current_visibility
        
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": {"show_participant_answers": new_visibility}}
        )
        
        # Отправляем WebSocket уведомление всем участникам
        await ws_manager.broadcast_to_lobby(lobby_id, {
            "type": "toggle_participant_answers",
            "data": {
                "show_answers": new_visibility
            }
        })
        
        return success(data={
            "message": f"Видимость ответов {'включена' if new_visibility else 'выключена'}",
            "show_answers": new_visibility
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка переключения видимости ответов: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при переключении видимости ответов")

@router.post("/lobbies/{lobby_id}/sync-state", summary="Синхронизировать состояние лобби")
async def sync_lobby_state(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """
    Синхронизирует состояние лобби для всех участников.
    Может вызываться хостом для принудительной синхронизации.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Синхронизация состояния: пользователь {user_id} запрашивает синхронизацию лобби {lobby_id}"
    )
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if user_id not in lobby.get("participants", []):
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        current_index = lobby.get("current_index", 0)
        question_ids = lobby.get("question_ids", [])
        current_question_id = question_ids[current_index] if current_index < len(question_ids) else None
        
        # Получаем информацию о показанных правильных ответах для текущего вопроса
        shown_correct_answers = lobby.get("shown_correct_answers", {})
        current_question_correct_shown = False
        correct_answer_index = None
        explanation = ""
        
        if current_question_id:
            current_question_correct_shown = shown_correct_answers.get(str(current_question_id), False)
            
            # Если правильный ответ уже был показан, получаем его индекс и объяснение
            if current_question_correct_shown:
                try:
                    # Получаем правильный ответ из лобби
                    correct_answers = lobby.get("correct_answers", {})
                    correct_answer_index = correct_answers.get(str(current_question_id), 0)
                    
                    # Получаем объяснение из базы данных
                    question = await db.questions.find_one({"_id": ObjectId(current_question_id)})
                    if question:
                        explanation = question.get("explanation", "")
                except Exception as e:
                    logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ERROR,
                message=f"Ошибка получения правильного ответа: вопрос {current_question_id}, ошибка {str(e)}"
            )
        
        sync_data = {
            "current_question_index": current_index,
            "current_question_id": str(current_question_id) if current_question_id else None,
            "lobby_status": lobby.get("status"),
            "participants": lobby.get("participants", []),
            "show_participant_answers": lobby.get("show_participant_answers", False),
            "show_correct_answer": current_question_correct_shown,
            "forced_sync": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Добавляем correct_answer_index и explanation если правильный ответ был показан
        if correct_answer_index is not None:
            sync_data["correct_answer_index"] = correct_answer_index
            sync_data["explanation"] = explanation
        
        # Отправляем синхронизацию через WebSocket всем участникам
        from app.websocket.lobby_ws import ws_manager
        await ws_manager.send_json_parallel(lobby_id, {
            "type": "sync_response",
            "data": sync_data
        })
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Синхронизация завершена: состояние лобби {lobby_id} синхронизировано для всех участников"
        )
        
        return success(data={
            "message": "Состояние лобби синхронизировано",
            "current_index": current_index,
            "current_question_id": str(current_question_id) if current_question_id else None
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка синхронизации состояния: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при синхронизации состояния лобби")

@router.get("/debug/question/{question_id}/media-info", summary="Отладка: информация о медиа вопроса")
async def debug_question_media_info(
    question_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """
    Отладочный эндпоинт для проверки информации о медиа файлах вопроса
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.DEBUG,
        message=f"Отладка медиа: пользователь {user_id} запрашивает отладочную информацию для вопроса {question_id}"
    )
    
    try:
        # Найти вопрос
        question = await db.questions.find_one({"_id": ObjectId(question_id)})
        if not question:
            return {"error": "Question not found", "question_id": question_id}
        
        result = {
            "question_id": question_id,
            "question_text": question.get("question_text", {}),
            "has_media": question.get("has_media", False),
            "media_file_id": question.get("media_file_id"),
            "media_filename": question.get("media_filename"),
            "media_type": question.get("media_type"),
            "has_after_answer_media": question.get("has_after_answer_media", False),
            "after_answer_media_file_id": question.get("after_answer_media_file_id"),
            "after_answer_media_id": question.get("after_answer_media_id"),
            "after_answer_media_filename": question.get("after_answer_media_filename"),
        }
        
        # Проверить существование основного медиа файла
        if question.get("media_file_id"):
            try:
                media_file_info = await db.fs.files.find_one({"_id": ObjectId(question["media_file_id"])})
                result["media_file_exists"] = media_file_info is not None
                if media_file_info:
                    result["media_file_info"] = {
                        "filename": media_file_info.get("filename"),
                        "length": media_file_info.get("length"),
                        "contentType": media_file_info.get("contentType"),
                        "uploadDate": str(media_file_info.get("uploadDate"))
                    }
            except Exception as e:
                result["media_file_error"] = str(e)
        
        # Проверить существование дополнительного медиа файла
        after_media_id = question.get("after_answer_media_file_id") or question.get("after_answer_media_id")
        if after_media_id:
            try:
                after_media_file_info = await db.fs.files.find_one({"_id": ObjectId(after_media_id)})
                result["after_media_file_exists"] = after_media_file_info is not None
                if after_media_file_info:
                    result["after_media_file_info"] = {
                        "filename": after_media_file_info.get("filename"),
                        "length": after_media_file_info.get("length"),
                        "contentType": after_media_file_info.get("contentType"),
                        "uploadDate": str(after_media_file_info.get("uploadDate"))
                    }
            except Exception as e:
                result["after_media_file_error"] = str(e)
        
        # Найти лобби с этим вопросом для пользователя
        user_lobbies = await db.lobbies.find({
            "participants": user_id,
            "question_ids": question_id
        }).to_list(None)
        
        result["user_lobbies"] = []
        for lobby in user_lobbies:
            lobby_info = {
                "lobby_id": lobby["_id"],
                "status": lobby.get("status"),
                "current_index": lobby.get("current_index", 0),
                "is_host": user_id == lobby.get("host_id"),
                "user_answers": list(lobby.get("participants_answers", {}).get(user_id, {}).keys())
            }
            result["user_lobbies"].append(lobby_info)
        
        return result
        
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.ERROR,
            message=f"Ошибка отладки медиа: вопрос {question_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        return {"error": str(e), "question_id": question_id}

@router.post("/lobbies/{lobby_id}/finish-test", summary="Завершить тест (хост)")
async def finish_test(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """
    Завершает тест досрочно. Только хост может завершить тест.
    Подсчитывает результаты всех участников и сохраняет их в историю.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.LIFECYCLE,
        message=f"Завершение теста хостом: пользователь {user_id} завершает тест в лобби {lobby_id}"
    )
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if lobby["host_id"] != user_id:
            raise HTTPException(status_code=403, detail="Только хост может завершить тест")
        
        if lobby["status"] != "in_progress":
            raise HTTPException(status_code=400, detail="Тест не запущен или уже завершен")
        
        # Завершаем тест
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {
                "$set": {
                    "status": "finished",
                    "finished_at": datetime.utcnow()
                }
            }
        )
        
        # Подсчитываем результаты
        results = {}
        participants_answers = lobby.get("participants_answers", {})
        total_questions = len(lobby.get("question_ids", []))
        
        for participant_id in lobby.get("participants", []):
            participant_answers = participants_answers.get(participant_id, {})
            correct_count = sum(1 for is_correct in participant_answers.values() if is_correct)
            
            results[participant_id] = {
                "correct": correct_count,
                "total": len(participant_answers),
                "percentage": round((correct_count / len(participant_answers) * 100) if len(participant_answers) > 0 else 0, 1)
            }
            
            # Сохраняем в историю
            history_record = {
                "user_id": participant_id,
                "lobby_id": lobby_id,
                "date": datetime.utcnow(),
                "score": correct_count,
                "total": len(participant_answers),
                "categories": lobby.get("categories", []),
                "sections": lobby.get("sections", []),
                "mode": lobby.get("mode", "multiplayer"),
                "pass_percentage": (correct_count / len(participant_answers) * 100) if len(participant_answers) > 0 else 0
            }
            await db.history.insert_one(history_record)
        
        # Инвалидируем кэш
        lobby_cache.invalidate_lobby(lobby_id)
        
        # Отправляем WebSocket уведомление о завершении теста
        await ws_manager.broadcast_to_lobby(lobby_id, {
            "type": "test_finished",
            "data": {
                "results": results,
                "message": "Тест завершен хостом"
            }
        })
        
        return success(data={
            "message": "Тест завершен",
            "results": results
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка завершения теста: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при завершении теста")

