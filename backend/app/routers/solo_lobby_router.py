from fastapi import APIRouter, HTTPException, Depends, Query
from app.db.database import db
from app.core.security import get_current_actor
from app.core.response import success

from datetime import datetime, timedelta
from typing import Dict, Any
import json
import time
from bson import ObjectId
from app.logging import get_logger, LogSection, LogSubsection

# Настройка логгера
logger = get_logger(__name__)

router = APIRouter(tags=["Solo Lobby"])

def serialize_datetime(obj):
    """Преобразует объекты datetime в строки ISO формата для JSON сериализации"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    else:
        return obj

def convert_answer_to_index(correct_answer_raw):
    """Преобразует буквенный ответ (A, B, C, D) в числовой индекс (0, 1, 2, 3)"""
    if isinstance(correct_answer_raw, str):
        letter_to_index = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        return letter_to_index.get(correct_answer_raw.upper(), 0)
    else:
        return correct_answer_raw if correct_answer_raw is not None else 0

# Rate limiting для безопасности
user_rate_limits = {}

def check_rate_limit(user_id: str, endpoint: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """Проверяет, находится ли пользователь в пределах лимита запросов для конкретной конечной точки"""
    current_time = time.time()
    key = f"{user_id}:{endpoint}"
    
    if key not in user_rate_limits:
        user_rate_limits[key] = []
    
    # Remove old requests outside the window
    user_rate_limits[key] = [req_time for req_time in user_rate_limits[key] 
                            if current_time - req_time < window_seconds]
    
    # Check if within limits
    if len(user_rate_limits[key]) >= max_requests:
        return False
    
    # Add current request
    user_rate_limits[key].append(current_time)
    return True



def validate_question_access(lobby: dict, user_id: str, question_id: str, user_answers: dict, current_index: int = None) -> tuple[bool, str]:
    """Проверяет, может ли пользователь получить доступ к определенному вопросу"""
    try:
        question_ids = lobby.get('question_ids', [])
        if not question_ids:
            return False, "В лобби нет вопросов"
        
        # Find question index
        question_index = None
        for i, qid in enumerate(question_ids):
            if str(qid) == str(question_id):
                question_index = i
                break
        
        if question_index is None:
            return False, "Вопрос не найден в лобби"
        
        # In exam mode, enforce sequential access
        if lobby.get('exam_mode', False):
            # Must answer questions in order
            for i in range(question_index):
                prev_question_id = str(question_ids[i])
                if prev_question_id not in user_answers:
                    return False, f"Необходимо ответить на вопрос {i+1} перед доступом к вопросу {question_index+1}"
        
        return True, "Доступ предоставлен"
        
    except Exception as e:
        return False, "Ошибка валидации"

# Secure endpoints for solo testing
@router.get("/{lobby_id}/secure")
async def get_secure_lobby(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """Защищенная конечная точка информации о лобби с контролем доступа"""
    try:
        user_id = str(current_user.get('id'))
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_lobby", max_requests=30, window_seconds=60):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Превышен лимит запросов: пользователь {user_id} слишком часто запрашивает доступ к лобби {lobby_id} (эндпоинт secure_lobby)"
            )
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Get lobby
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Validate user access
        if user_id not in lobby.get('participants', []):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Неавторизованная попытка доступа к лобби {lobby_id}: пользователь {user_id} не является участником лобби"
            )
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get user answers from lobby
        user_answers = lobby.get("participants_raw_answers", {}).get(user_id, {})
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Предоставлен безопасный доступ к лобби {lobby_id} пользователю {user_id} с {len(user_answers)} сохранёнными ответами"
        )
        
        # Serialize lobby data to handle datetime objects
        serialized_lobby = serialize_datetime(lobby)
        
        # Add exam timer info if in exam mode
        if lobby.get('exam_mode', False):
            current_time = datetime.utcnow()
            expires_at = lobby.get("exam_timer_expires_at")
            
            if expires_at:
                # Calculate remaining time from expiration date
                time_left = max(0, int((expires_at - current_time).total_seconds()))
                serialized_lobby["exam_timer"] = {
                    "time_left": time_left,
                    "expires_at": expires_at.isoformat() if hasattr(expires_at, 'isoformat') else str(expires_at),
                    "duration": lobby.get("exam_timer_duration", 40 * 60)
                }
            else:
                # If no expiration date, assume full time
                duration = lobby.get("exam_timer_duration", 40 * 60)
                serialized_lobby["exam_timer"] = {
                    "time_left": duration,
                    "duration": duration
                }
        
        # Return secure lobby data
        return success(
            data={
                **serialized_lobby,
                "user_answers": user_answers,
                "is_host": str(lobby.get('host_id')) == user_id,
                "current_index": lobby.get('current_index', 0)
            },
            message="Данные защищенного лобби успешно получены"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Критическая ошибка при получении безопасного доступа к лобби {lobby_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{lobby_id}/questions/{question_id}/secure")
async def get_secure_question(
    lobby_id: str,
    question_id: str,
    current_index: int = Query(None),
    user_answers: str = Query("{}"),
    current_user: dict = Depends(get_current_actor)
):
    """Secure question endpoint with access validation"""
    try:
        user_id = str(current_user.get('id'))
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Пользователь {user_id} запрашивает безопасный доступ к вопросу {question_id} в лобби {lobby_id} на позиции {current_index}"
        )
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_question", max_requests=50, window_seconds=60):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Превышен лимит запросов: пользователь {user_id} слишком часто запрашивает вопросы в лобби {lobby_id} (эндпоинт secure_question)"
            )
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Parse user answers
        try:
            user_answers_dict = json.loads(user_answers)
        except:
            user_answers_dict = {}
        
        # Get lobby and validate access
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Validate question access
        can_access, reason = validate_question_access(lobby, user_id, question_id, user_answers_dict, current_index)
        if not can_access:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Отказано в доступе к вопросу {question_id} для пользователя {user_id} в лобби {lobby_id}: {reason}"
            )
            raise HTTPException(status_code=403, detail=reason)
        
        # Get question - try both string and ObjectId
        question = await db.questions.find_one({"_id": question_id})
        if not question:
            try:
                # Try as ObjectId if string search failed
                question = await db.questions.find_one({"_id": ObjectId(question_id)})
            except:
                pass
        
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        

        
        # Prepare question data
        question_data = {
            "_id": str(question["_id"]),
            "question_text": question.get("question_text", {}),
            "answers": [option["text"] for option in question.get("options", [])],
            "has_media": question.get("has_media", False),
            "media_filename": question.get("media_filename"),
            "has_after_answer_media": question.get("has_after_answer_media", False),
            "after_answer_media_filename": question.get("after_answer_media_filename")
        }
        
        # Security: Control media access
        if question_data["has_media"]:
            question_data["media_access_granted"] = True  # Allow media access for questions
        
        # Security: Control answer access
        question_data["answer_access_granted"] = not lobby.get('exam_mode', False)
        
        # Security: In exam mode, remove sensitive data
        if lobby.get('exam_mode', False):
            question_data.pop('correct_answer_index', None)
            question_data.pop('explanation', None)
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Предоставлен безопасный доступ к вопросу {question_id} пользователю {user_id} в лобби {lobby_id}, медиа: {question_data.get('has_media', False)}, режим экзамена: {lobby.get('exam_mode', False)}"
        )
        
        return success(
            data=question_data,
            message="Secure question retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Критическая ошибка при получении безопасного вопроса {question_id} в лобби {lobby_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{lobby_id}/secure/answer")
async def submit_secure_answer(
    lobby_id: str,
    answer_data: dict,
    current_user: dict = Depends(get_current_actor)
):
    """Secure answer submission with validation"""
    try:
        user_id = str(current_user.get('id'))
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_answer", max_requests=20, window_seconds=60):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Превышен лимит запросов: пользователь {user_id} слишком часто отправляет ответы в лобби {lobby_id} (эндпоинт secure_answer)"
            )
            raise HTTPException(status_code=429, detail="Too many requests")
        
        question_id = answer_data.get('question_id')
        answer_index = answer_data.get('answer_index')
        
        if question_id is None or answer_index is None:
            raise HTTPException(status_code=400, detail="Missing question_id or answer_index")
        
        # Get lobby
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        

        
        # Validate lobby status - for solo tests, allow more flexible status checking
        lobby_status = lobby.get('status')
        if lobby_status not in ['active', 'in_progress', 'started']:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Отклонён ответ пользователя {user_id} на вопрос {question_id}: лобби {lobby_id} имеет недопустимый статус '{lobby_status}'"
            )
            raise HTTPException(status_code=400, detail=f"Lobby is not active (status: {lobby_status})")
        
        # Check if exam time expired
        if lobby.get('exam_mode') and lobby.get('exam_timer'):
            time_left = lobby['exam_timer'].get('time_left', 0)
            if time_left <= 0:
                logger.warning(
                    section=LogSection.SECURITY,
                    subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                    message=f"Попытка отправки ответа после истечения времени экзамена: пользователь {user_id} пытался ответить на вопрос {question_id} в лобби {lobby_id}"
                )
                raise HTTPException(status_code=400, detail="Exam time has expired")
        
        # Save answer in lobby's participants_raw_answers
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {
                "$set": {
                    f"participants_raw_answers.{user_id}.{question_id}": answer_index
                }
            }
        )
        
        logger.info(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.AUDIT,
            message=f"Безопасно отправлен ответ: пользователь {user_id} отправил ответ {answer_index} на вопрос {question_id} в лобби {lobby_id}"
        )
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.QUESTIONS,
            message=f"Пользователь {user_id} успешно отправил ответ {answer_index} на вопрос {question_id} в лобби {lobby_id}"
        )
        
        # Determine if answer access should be granted
        answer_access_granted = not lobby.get('exam_mode', False)
        
        return success(
            data={
                "answer_submitted": True,
                "answer_access_granted": answer_access_granted
            },
            message="Secure answer submitted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Критическая ошибка при отправке ответа пользователя {user_id} в лобби {lobby_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{lobby_id}/secure/correct-answer")
async def get_secure_correct_answer(
    lobby_id: str,
    question_id: str = Query(...),
    user_answers: str = Query("{}"),
    exam_mode: bool = Query(False),
    current_user: dict = Depends(get_current_actor)
):
    """Secure correct answer endpoint with access validation"""
    try:
        user_id = str(current_user.get('id'))
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_correct_answer", max_requests=30, window_seconds=60):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Превышен лимит запросов: пользователь {user_id} слишком часто запрашивает правильные ответы в лобби {lobby_id} (эндпоинт secure_correct_answer)"
            )
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Security: Block in exam mode
        if exam_mode:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Заблокирован запрос правильного ответа в экзаменационном режиме: пользователь {user_id} попытался получить правильный ответ на вопрос {question_id} в лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Correct answers not available in exam mode")
        
        # Parse user answers from URL parameter
        try:
            user_answers_dict = json.loads(user_answers)
        except:
            user_answers_dict = {}
        
        # Get lobby to check saved answers
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Check if user has answered this question (check both URL params and saved data)
        participants_raw_answers = lobby.get("participants_raw_answers", {})
        user_saved_answers = participants_raw_answers.get(user_id, {})
        
        has_answered_in_url = question_id in user_answers_dict
        has_answered_in_db = question_id in user_saved_answers
        

        
        if not (has_answered_in_url or has_answered_in_db):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Попытка получения правильного ответа без предварительного ответа: пользователь {user_id} запросил правильный ответ на вопрос {question_id} в лобби {lobby_id} не ответив на него"
            )
            raise HTTPException(status_code=403, detail="Must answer question first")
        
        # Get correct answer from lobby (already converted to index)
        correct_answers = lobby.get("correct_answers", {})
        correct_index = correct_answers.get(question_id, 0)
        
        # Get question for explanation and media info
        question = await db.questions.find_one({"_id": question_id})
        if not question:
            try:
                # Try as ObjectId if string search failed
                question = await db.questions.find_one({"_id": ObjectId(question_id)})
            except:
                pass
        
        # Get user's answer (prefer saved data from DB, fallback to URL params)
        user_answer = user_saved_answers.get(question_id)
        if user_answer is None:
            user_answer = user_answers_dict.get(question_id)
        
        is_correct = user_answer == correct_index
        

        
        # Determine after-media access
        after_media_access_granted = True  # Allow after-answer media access
        
        # Prepare response data
        response_data = {
            "correct_answer_index": correct_index,
            "explanation": question.get('explanation') if question else {},
            "has_after_answer_media": question.get('has_after_answer_media', False) if question else False,
            "after_media_access_granted": after_media_access_granted,
            "user_is_correct": is_correct
        }
        

        
        logger.info(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.AUDIT,
            message=f"Предоставлен доступ к правильному ответу: пользователь {user_id} получил правильный ответ на вопрос {question_id} в лобби {lobby_id}, его ответ был {'правильным' if is_correct else 'неправильным'}"
        )
        
        return success(
            data=response_data,
            message="Secure correct answer retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Критическая ошибка при получении правильного ответа для вопроса {question_id} в лобби {lobby_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{lobby_id}/secure/after-answer-media-access")
async def check_secure_after_media_access(
    lobby_id: str,
    question_id: str = Query(...),
    user_answers: str = Query("{}"),
    current_user: dict = Depends(get_current_actor)
):
    """Check access to after-answer media"""
    try:
        user_id = str(current_user.get('id'))
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_after_media", max_requests=25, window_seconds=60):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Превышен лимит запросов: пользователь {user_id} слишком часто проверяет доступ к дополнительному медиа в лобби {lobby_id} (эндпоинт secure_after_media)"
            )
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Parse user answers
        try:
            user_answers_dict = json.loads(user_answers)
        except:
            user_answers_dict = {}
        
        # Check if user has answered this question (check both URL params and saved data)
        # Get lobby to check saved answers
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Check saved answers in lobby
        participants_raw_answers = lobby.get("participants_raw_answers", {})
        user_saved_answers = participants_raw_answers.get(user_id, {})
        
        access_granted = (question_id in user_answers_dict or question_id in user_saved_answers)
        
        if not access_granted:
            logger.info(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Отказано в доступе к дополнительному медиа: пользователь {user_id} запросил доступ к дополнительному медиа для вопроса {question_id} в лобби {lobby_id} не ответив на вопрос"
            )
        else:
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Предоставлен доступ к дополнительному медиа: пользователь {user_id} получил доступ к дополнительному медиа для вопроса {question_id} в лобби {lobby_id}"
            )
        
        return success(
            data={"access_granted": access_granted},
            message="After-answer media access checked"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка при проверке доступа к дополнительному медиа для вопроса {question_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{lobby_id}/secure/exam-timer")
async def get_secure_exam_timer(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """Secure exam timer endpoint"""
    try:
        user_id = str(current_user.get('id'))
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_exam_timer", max_requests=20, window_seconds=60):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Превышен лимит запросов: пользователь {user_id} слишком часто запрашивает экзаменационный таймер в лобби {lobby_id} (эндпоинт secure_exam_timer)"
            )
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Get lobby
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Check if exam mode
        if not lobby.get('exam_mode', False):
            raise HTTPException(status_code=400, detail="Not in exam mode")
        
        # Get timer info from expires_at field
        current_time = datetime.utcnow()
        expires_at = lobby.get("exam_timer_expires_at")
        
        if expires_at:
            # Calculate remaining time from expiration date
            time_left = max(0, int((expires_at - current_time).total_seconds()))
        else:
            # If no expiration date set, initialize it now
            duration = lobby.get("exam_timer_duration", 40 * 60)  # 40 minutes default
            expires_at = current_time + timedelta(seconds=duration)
            time_left = duration
            
            # Update lobby with timer info
            await db.lobbies.update_one(
                {"_id": lobby_id},
                {"$set": {
                    "exam_timer_expires_at": expires_at,
                    "exam_timer_started_at": current_time,
                    "exam_timer_duration": duration
                }}
            )
        
        # Auto-close if time expired
        if time_left <= 0:
            await db.lobbies.update_one(
                {"_id": lobby_id},
                {"$set": {"status": "finished", "finished_at": datetime.utcnow()}}
            )
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.EXAM_TIMER,
                message=f"Автоматически закрыт экзамен из-за истечения времени: лобби {lobby_id} закрыто для пользователя {user_id}, оставшееся время: {time_left} секунд"
            )
        
        return success(
            data={"time_left": time_left},
            message="Secure exam timer retrieved"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка при получении экзаменационного таймера для лобби {lobby_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{lobby_id}/secure/exam-timer")
async def update_secure_exam_timer(
    lobby_id: str,
    timer_data: dict,
    current_user: dict = Depends(get_current_actor)
):
    """Update secure exam timer"""
    try:
        user_id = str(current_user.get('id'))
        time_left = timer_data.get('time_left', 0)
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_timer_update", max_requests=10, window_seconds=60):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Превышен лимит запросов: пользователь {user_id} слишком часто обновляет экзаменационный таймер в лобби {lobby_id} (эндпоинт secure_timer_update)"
            )
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Update timer
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": {"exam_timer.time_left": time_left, "exam_timer.updated_at": datetime.utcnow()}}
        )
        

        
        return success(data={}, message="Timer synchronized")
        
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка при обновлении экзаменационного таймера для лобби {lobby_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{lobby_id}/secure/auto-close-exam")
async def auto_close_expired_exam(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """Auto-close expired exam lobby"""
    try:
        user_id = str(current_user.get('id'))
        
        # Close lobby
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": {"status": "finished", "finished_at": datetime.utcnow()}}
        )
        
        logger.warning(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.EXAM_TIMER,
            message=f"Вручную инициировано автоматическое закрытие экзамена: пользователь {user_id} закрыл экзамен в лобби {lobby_id} из-за истечения времени"
        )
        
        return success(data={}, message="Exam auto-closed due to time expiration")
        
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка при автоматическом закрытии истёкшего экзамена в лобби {lobby_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{lobby_id}/secure/finish")
async def finish_secure_test(
    lobby_id: str,
    finish_data: dict,
    current_user: dict = Depends(get_current_actor)
):
    """Secure test finish endpoint"""
    try:
        user_id = str(current_user.get('id'))
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_finish", max_requests=5, window_seconds=60):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Превышен лимит запросов: пользователь {user_id} слишком часто пытается завершить тест в лобби {lobby_id} (эндпоинт secure_finish)"
            )
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Update lobby status
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": {"status": "finished", "finished_at": datetime.utcnow()}}
        )
        
        final_answers_count = len(finish_data.get('final_answers', {}))
        exam_mode = finish_data.get('exam_mode', False)
        mode_text = "экзаменационном" if exam_mode else "тренировочном"
        
        logger.info(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.AUDIT,
            message=f"Безопасно завершён тест: пользователь {user_id} завершил тест в {mode_text} режиме в лобби {lobby_id} с {final_answers_count} финальными ответами"
        )
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.FINISH_TEST,
            message=f"Пользователь {user_id} завершил тест в лобби {lobby_id} с {len(finish_data.get('final_answers', {}))} ответами"
        )
        
        return success(data={}, message="Test finished securely")
        
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка при завершении безопасного теста в лобби {lobby_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{lobby_id}/secure/results")
async def get_secure_test_results(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """Enhanced secure test results endpoint with detailed analytics"""
    try:
        user_id = str(current_user.get('id'))
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_results", max_requests=10, window_seconds=60):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Превышен лимит запросов: пользователь {user_id} слишком часто запрашивает результаты теста в лобби {lobby_id} (эндпоинт secure_results)"
            )
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Get lobby data
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Get user answers from lobby
        user_answers = lobby.get("participants_raw_answers", {}).get(user_id, {})
        
        # Get user profile for additional info
        user_profile = await db.users.find_one({"_id": user_id})
        if not user_profile:
            user_profile = await db.guests.find_one({"_id": user_id})
        
        # Basic lobby info
        lobby_info = {
            "lobby_id": lobby_id,
            "test_type": "exam" if lobby.get('exam_mode', False) else "practice",
            "categories": lobby.get('categories', []),
            "sections": lobby.get('sections', []),
            "created_at": lobby.get('created_at'),
            "finished_at": lobby.get('finished_at'),
            "exam_mode": lobby.get('exam_mode', False),
            "max_time_minutes": 40 if lobby.get('exam_mode', False) else None
        }
        
        # Calculate timing
        start_time = lobby.get('created_at')
        end_time = lobby.get('finished_at', datetime.utcnow())
        duration_seconds = 0
        if start_time and end_time:
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            duration_seconds = int((end_time - start_time).total_seconds())
        
        question_ids = lobby.get('question_ids', [])
        total_questions = len(question_ids)
        
        if not user_answers:
            # No answers - early exit or didn't start
            return success(
                data={
                    "lobby_info": serialize_datetime(lobby_info),
                    "user_info": {
                        "user_id": user_id,
                        "full_name": user_profile.get('full_name', '') if user_profile else '',
                        "username": user_profile.get('username', '') if user_profile else '',
                        "email": user_profile.get('email', '') if user_profile else ''
                    },
                    "test_results": {
                        "answered_count": 0,
                        "correct_count": 0,
                        "incorrect_count": 0,
                        "unanswered_count": total_questions,
                        "total_questions": total_questions,
                        "percentage": 0,
                        "passed": False,
                        "duration_seconds": duration_seconds,
                        "average_time_per_question": 0,
                        "completion_rate": 0
                    },
                    "detailed_answers": [],
                    "performance_analytics": {
                        "skill_level": "not_determined",
                        "accuracy_rating": "low",
                        "speed_rating": "not_determined",
                        "areas_for_improvement": ["test_not_started"],
                        "strengths": [],
                        "recommendations": ["complete_test_for_results"]
                    }
                },
                message="No answers found - test not started or completed"
            )
        
        answered_count = len(user_answers)
        
        # Detailed answer analysis
        detailed_answers = []
        correct_count = 0
        category_stats = {}
        
        # Get correct answers from lobby (already converted to indices)
        correct_answers = lobby.get("correct_answers", {})
        
        for i, question_id in enumerate(question_ids):
            question_id_str = str(question_id)
            
            # Get correct answer from lobby
            correct_answer_index = correct_answers.get(question_id_str, 0)
            
            # Get question details for additional info
            question = await db.questions.find_one({"_id": question_id})
            if not question:
                try:
                    question = await db.questions.find_one({"_id": ObjectId(question_id)})
                except:
                    pass
            
            user_answer = user_answers.get(question_id_str)
            is_answered = user_answer is not None
            is_correct = is_answered and user_answer == correct_answer_index
            
            if is_correct:
                correct_count += 1
            
            # Category analysis (only if question found)
            if question:
                question_categories = question.get('categories', [])
                for cat in question_categories:
                    if cat not in category_stats:
                        category_stats[cat] = {"total": 0, "correct": 0}
                    category_stats[cat]["total"] += 1
                    if is_correct:
                        category_stats[cat]["correct"] += 1
            else:
                question_categories = []
            
            # Question details
            question_detail = {
                "question_number": i + 1,
                "question_id": question_id_str,
                "question_text": question.get('question_text', {}) if question else {},
                "options": [opt.get('text', {}) for opt in question.get('options', [])] if question else [],
                "correct_answer_index": correct_answer_index,
                "user_answer_index": user_answer,
                "is_answered": is_answered,
                "is_correct": is_correct,
                "categories": question_categories,
                "explanation": question.get('explanation', {}) if question else {},
                "has_media": question.get('has_media', False) if question else False,
                "has_after_answer_media": question.get('has_after_answer_media', False) if question else False
            }
            detailed_answers.append(question_detail)
        
        # Calculate metrics
        incorrect_count = answered_count - correct_count
        unanswered_count = total_questions - answered_count
        percentage = round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0
        completion_rate = round((answered_count / total_questions * 100), 2) if total_questions > 0 else 0
        passed = percentage >= 70
        average_time_per_question = round(duration_seconds / answered_count) if answered_count > 0 else 0
        
        # Performance analytics
        def get_skill_level(percentage):
            if percentage >= 95: return "excellent"
            elif percentage >= 85: return "very_good"
            elif percentage >= 75: return "good"
            elif percentage >= 65: return "satisfactory"
            elif percentage >= 50: return "needs_improvement"
            else: return "poor"
        
        def get_speed_rating(avg_time):
            if avg_time == 0: return "not_determined"
            elif avg_time <= 30: return "very_fast"
            elif avg_time <= 60: return "fast"
            elif avg_time <= 90: return "normal"
            elif avg_time <= 120: return "slow"
            else: return "very_slow"
        
        def get_accuracy_rating(percentage):
            if percentage >= 80: return "high"
            elif percentage >= 60: return "medium"
            else: return "low"
        
        # Areas for improvement and strengths
        areas_for_improvement = []
        strengths = []
        recommendations = []
        
        if unanswered_count > 0:
            areas_for_improvement.append({
                "type": "unanswered_questions",
                "count": unanswered_count,
                "total": total_questions
            })
            recommendations.append("answer_all_questions")
        
        if incorrect_count > 0:
            areas_for_improvement.append({
                "type": "incorrect_answers",
                "count": incorrect_count,
                "total": total_questions
            })
        
        if correct_count > 0:
            strengths.append({
                "type": "correct_answers",
                "count": correct_count,
                "total": total_questions
            })
        
        if percentage >= 70:
            strengths.append({
                "type": "test_passed",
                "percentage": percentage
            })
            recommendations.append("excellent_work")
        else:
            recommendations.append("additional_study_needed")
            
        # Add time-based recommendations
        if average_time_per_question > 0:
            if average_time_per_question <= 30:
                strengths.append({
                    "type": "fast_completion",
                    "avg_time": average_time_per_question
                })
            elif average_time_per_question > 120:
                areas_for_improvement.append({
                    "type": "slow_completion",
                    "avg_time": average_time_per_question
                })
                recommendations.append("practice_time_management")
        
        # Category performance
        category_performance = []
        for cat, stats in category_stats.items():
            cat_percentage = round((stats["correct"] / stats["total"] * 100), 2) if stats["total"] > 0 else 0
            category_performance.append({
                "category": cat,
                "correct": stats["correct"],
                "total": stats["total"],
                "percentage": cat_percentage
            })
        
        result_data = {
            "lobby_info": serialize_datetime(lobby_info),
            "user_info": {
                "user_id": user_id,
                "full_name": user_profile.get('full_name', '') if user_profile else '',
                "username": user_profile.get('username', '') if user_profile else '',
                "email": user_profile.get('email', '') if user_profile else ''
            },
            "test_results": {
                "answered_count": answered_count,
                "correct_count": correct_count,
                "incorrect_count": incorrect_count,
                "unanswered_count": unanswered_count,
                "total_questions": total_questions,
                "percentage": percentage,
                "passed": passed,
                "duration_seconds": duration_seconds,
                "average_time_per_question": average_time_per_question,
                "completion_rate": completion_rate
            },
            "detailed_answers": detailed_answers,
            "category_performance": category_performance,
            "performance_analytics": {
                "skill_level": get_skill_level(percentage),
                "accuracy_rating": get_accuracy_rating(percentage),
                "speed_rating": get_speed_rating(average_time_per_question),
                "areas_for_improvement": areas_for_improvement,
                "strengths": strengths,
                "recommendations": recommendations,
                "completion_status": "completed" if completion_rate == 100 else "partial",
                "pass_status": "passed" if passed else "failed"
            }
        }
        
        logger.info(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.AUDIT,
            message=f"Получены результаты теста: пользователь {user_id} запросил результаты из лобби {lobby_id} с {answered_count} ответами, {correct_count} правильными ({percentage}%)"
        )
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.RESULTS,
            message=f"Пользователь {user_id} получил результаты теста из лобби {lobby_id}: {correct_count}/{total_questions} правильных ответов ({percentage}%)"
        )
        
        return success(
            data=result_data,
            message="Enhanced test results retrieved successfully"
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка при получении результатов теста для лобби {lobby_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{lobby_id}/report")
async def report_question(
    lobby_id: str,
    report_data: dict,
    current_user: dict = Depends(get_current_actor)
):
    """Report a question for review"""
    try:
        user_id = str(current_user.get('id'))
        
        # Rate limiting
        if not check_rate_limit(user_id, "report_question", max_requests=5, window_seconds=300):  # 5 reports per 5 minutes
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.SUSPICIOUS_ACTIVITY,
                message=f"Превышен лимит запросов: пользователь {user_id} слишком часто отправляет жалобы на вопросы в лобби {lobby_id} (эндпоинт report_question)"
            )
            raise HTTPException(status_code=429, detail="Too many reports. Please wait.")
        
        question_id = report_data.get('question_id')
        report_type = report_data.get('report_type')
        description = report_data.get('description')
        
        if not all([question_id, report_type, description]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Save report
        report_doc = {
            "lobby_id": lobby_id,
            "question_id": question_id,
            "user_id": user_id,
            "report_type": report_type,
            "description": description,
            "created_at": datetime.utcnow(),
            "status": "pending"
        }
        
        await db.question_reports.insert_one(report_doc)
        
        logger.info(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.AUDIT,
            message=f"Отправлена жалоба на вопрос: пользователь {user_id} пожаловался на вопрос {question_id} в лобби {lobby_id}, тип жалобы: {report_type}, описание: {description[:100]}..."
        )
        
        return success(
            data={"report_submitted": True},
            message="Report submitted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка при отправке жалобы на вопрос от пользователя {user_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error") 