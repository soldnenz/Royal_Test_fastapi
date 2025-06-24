from fastapi import APIRouter, HTTPException, Depends, Query
from app.db.database import db
from app.core.security import get_current_actor
from app.core.response import success

from datetime import datetime, timedelta
from typing import Dict, Any
import json
import time
import logging
from bson import ObjectId

# Настройка логгера
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Solo Lobby"])

def serialize_datetime(obj):
    """Convert datetime objects to ISO format strings for JSON serialization"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    else:
        return obj

# Rate limiting для безопасности
user_rate_limits = {}

def check_rate_limit(user_id: str, endpoint: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """Check if user is within rate limits for specific endpoint"""
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

def log_security_event(event_type: str, user_id: str, lobby_id: str, details: dict = None):
    """Log security events for monitoring"""
    logger.info(f"[SECURITY] {event_type} - User: {user_id}, Lobby: {lobby_id}, Details: {details}")

def validate_question_access(lobby: dict, user_id: str, question_id: str, user_answers: dict, current_index: int = None) -> tuple[bool, str]:
    """Validate if user can access a specific question"""
    try:
        question_ids = lobby.get('question_ids', [])
        if not question_ids:
            return False, "No questions in lobby"
        
        # Find question index
        question_index = None
        for i, qid in enumerate(question_ids):
            if str(qid) == str(question_id):
                question_index = i
                break
        
        if question_index is None:
            return False, "Question not found in lobby"
        
        # In exam mode, enforce sequential access
        if lobby.get('exam_mode', False):
            # Must answer questions in order
            for i in range(question_index):
                prev_question_id = str(question_ids[i])
                if prev_question_id not in user_answers:
                    return False, f"Must answer question {i+1} before accessing question {question_index+1}"
        
        return True, "Access granted"
        
    except Exception as e:
        logger.error(f"Error validating question access: {e}")
        return False, "Validation error"

# Secure endpoints for solo testing
@router.get("/{lobby_id}/secure")
async def get_secure_lobby(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """Secure lobby information endpoint with access controls"""
    try:
        user_id = str(current_user.get('id'))
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_lobby", max_requests=30, window_seconds=60):
            log_security_event("RATE_LIMIT_EXCEEDED", user_id, lobby_id, {"endpoint": "secure_lobby"})
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Get lobby
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Validate user access
        if user_id not in lobby.get('participants', []):
            log_security_event("UNAUTHORIZED_LOBBY_ACCESS", user_id, lobby_id)
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get user answers
        user_answers_doc = await db.user_answers.find_one({
            "lobby_id": lobby_id,
            "user_id": user_id
        })
        
        user_answers = user_answers_doc.get('answers', {}) if user_answers_doc else {}
        
        log_security_event("SECURE_LOBBY_ACCESS", user_id, lobby_id)
        
        # Serialize lobby data to handle datetime objects
        serialized_lobby = serialize_datetime(lobby)
        
        # Return secure lobby data
        return success(
            data={
                **serialized_lobby,
                "user_answers": user_answers,
                "is_host": str(lobby.get('host_id')) == user_id,
                "current_index": lobby.get('current_index', 0)
            },
            message="Secure lobby data retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_secure_lobby: {e}")
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
        logger.info(f"[SECURE_QUESTION] User {user_id} requesting question {question_id} in lobby {lobby_id}, index: {current_index}")
        
        # Rate limiting
        if not check_rate_limit(user_id, "secure_question", max_requests=50, window_seconds=60):
            log_security_event("RATE_LIMIT_EXCEEDED", user_id, lobby_id, {"endpoint": "secure_question"})
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
            log_security_event("QUESTION_ACCESS_DENIED", user_id, lobby_id, {"question_id": question_id, "reason": reason})
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
        
        # Debug: Log the raw question from database
        logger.info(f"[SECURE_QUESTION] Raw question from DB: answers={question.get('answers', 'NO_ANSWERS')}, keys={list(question.keys())}")
        
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
        
        log_security_event("SECURE_QUESTION_ACCESS", user_id, lobby_id, {"question_id": question_id})
        
        logger.info(f"[SECURE_QUESTION] Returning question data: answers={len(question_data.get('answers', []))}, has_media={question_data.get('has_media')}")
        
        return success(
            data=question_data,
            message="Secure question retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_secure_question: {e}")
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
            log_security_event("RATE_LIMIT_EXCEEDED", user_id, lobby_id, {"endpoint": "secure_answer"})
            raise HTTPException(status_code=429, detail="Too many requests")
        
        question_id = answer_data.get('question_id')
        answer_index = answer_data.get('answer_index')
        
        if question_id is None or answer_index is None:
            raise HTTPException(status_code=400, detail="Missing question_id or answer_index")
        
        # Get lobby
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Debug: Log lobby status
        logger.info(f"[SECURE_ANSWER] Lobby {lobby_id} status: {lobby.get('status', 'NO_STATUS')}, all keys: {list(lobby.keys())}")
        
        # Validate lobby status - for solo tests, allow more flexible status checking
        lobby_status = lobby.get('status')
        if lobby_status not in ['active', 'in_progress', 'started']:
            logger.warning(f"[SECURE_ANSWER] Rejecting answer for lobby {lobby_id} with status: {lobby_status}")
            raise HTTPException(status_code=400, detail=f"Lobby is not active (status: {lobby_status})")
        
        # Check if exam time expired
        if lobby.get('exam_mode') and lobby.get('exam_timer'):
            time_left = lobby['exam_timer'].get('time_left', 0)
            if time_left <= 0:
                log_security_event("ANSWER_AFTER_EXAM_EXPIRED", user_id, lobby_id, {"question_id": question_id})
                raise HTTPException(status_code=400, detail="Exam time has expired")
        
        # Save answer in both places like the old code
        # 1. Save in user_answers collection
        await db.user_answers.update_one(
            {
                "lobby_id": lobby_id,
                "user_id": user_id
            },
            {
                "$set": {
                    f"answers.{question_id}": answer_index,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        # 2. Save in lobby's participants_raw_answers
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {
                "$set": {
                    f"participants_raw_answers.{user_id}.{question_id}": answer_index
                }
            }
        )
        
        log_security_event("SECURE_ANSWER_SUBMITTED", user_id, lobby_id, {
            "question_id": question_id,
            "answer_index": answer_index
        })
        
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
        logger.error(f"Error in submit_secure_answer: {e}")
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
            log_security_event("RATE_LIMIT_EXCEEDED", user_id, lobby_id, {"endpoint": "secure_correct_answer"})
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Security: Block in exam mode
        if exam_mode:
            log_security_event("CORRECT_ANSWER_BLOCKED_EXAM_MODE", user_id, lobby_id, {"question_id": question_id})
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
        
        logger.info(f"[SECURE_CORRECT_ANSWER] Question {question_id}: URL={has_answered_in_url}, DB={has_answered_in_db}, user_answers_dict={user_answers_dict}, saved_answers={user_saved_answers}")
        
        if not (has_answered_in_url or has_answered_in_db):
            log_security_event("CORRECT_ANSWER_WITHOUT_USER_ANSWER", user_id, lobby_id, {"question_id": question_id})
            raise HTTPException(status_code=403, detail="Must answer question first")
        
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
        
        correct_index = question.get('correct_answer', 0)
        
        # Get user's answer (prefer saved data from DB, fallback to URL params)
        user_answer = user_saved_answers.get(question_id)
        if user_answer is None:
            user_answer = user_answers_dict.get(question_id)
        
        is_correct = user_answer == correct_index
        
        logger.info(f"[SECURE_CORRECT_ANSWER] Question {question_id}: user_answer={user_answer}, correct_index={correct_index}, is_correct={is_correct}")
        
        # Determine after-media access
        after_media_access_granted = True  # Allow after-answer media access
        
        # Prepare response data
        response_data = {
            "correct_answer_index": correct_index,
            "explanation": question.get('explanation'),
            "has_after_answer_media": question.get('has_after_answer_media', False),
            "after_media_access_granted": after_media_access_granted,
            "user_is_correct": is_correct
        }
        
        logger.info(f"[SECURE_CORRECT_ANSWER] Returning response data: {response_data}")
        
        log_security_event("SECURE_CORRECT_ANSWER_ACCESS", user_id, lobby_id, {
            "question_id": question_id,
            "is_correct": is_correct
        })
        
        return success(
            data=response_data,
            message="Secure correct answer retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_secure_correct_answer: {e}")
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
            log_security_event("RATE_LIMIT_EXCEEDED", user_id, lobby_id, {"endpoint": "secure_after_media"})
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Parse user answers
        try:
            user_answers_dict = json.loads(user_answers)
        except:
            user_answers_dict = {}
        
        # Check if user has answered this question
        access_granted = question_id in user_answers_dict
        
        if not access_granted:
            log_security_event("AFTER_MEDIA_ACCESS_DENIED", user_id, lobby_id, {"question_id": question_id})
        
        return success(
            data={"access_granted": access_granted},
            message="After-answer media access checked"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in check_secure_after_media_access: {e}")
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
            log_security_event("RATE_LIMIT_EXCEEDED", user_id, lobby_id, {"endpoint": "secure_exam_timer"})
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Get lobby
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Check if exam mode
        if not lobby.get('exam_mode', False):
            raise HTTPException(status_code=400, detail="Not in exam mode")
        
        # Get timer info
        exam_timer = lobby.get('exam_timer', {})
        time_left = exam_timer.get('time_left', 0)
        
        # Auto-close if time expired
        if time_left <= 0:
            await db.lobbies.update_one(
                {"_id": lobby_id},
                {"$set": {"status": "finished", "finished_at": datetime.utcnow()}}
            )
            log_security_event("EXAM_AUTO_CLOSED", user_id, lobby_id, {"time_left": time_left})
        
        return success(
            data={"time_left": max(0, time_left)},
            message="Secure exam timer retrieved"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_secure_exam_timer: {e}")
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
            log_security_event("RATE_LIMIT_EXCEEDED", user_id, lobby_id, {"endpoint": "secure_timer_update"})
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Update timer
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": {"exam_timer.time_left": time_left, "exam_timer.updated_at": datetime.utcnow()}}
        )
        
        log_security_event("EXAM_TIMER_SYNC", user_id, lobby_id, {"time_left": time_left})
        
        return success(data={}, message="Timer synchronized")
        
    except Exception as e:
        logger.error(f"Error in update_secure_exam_timer: {e}")
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
        
        log_security_event("EXAM_AUTO_CLOSED_MANUAL", user_id, lobby_id)
        
        return success(data={}, message="Exam auto-closed due to time expiration")
        
    except Exception as e:
        logger.error(f"Error in auto_close_expired_exam: {e}")
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
            log_security_event("RATE_LIMIT_EXCEEDED", user_id, lobby_id, {"endpoint": "secure_finish"})
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Update lobby status
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": {"status": "finished", "finished_at": datetime.utcnow()}}
        )
        
        log_security_event("SECURE_TEST_FINISHED", user_id, lobby_id, {
            "final_answers": len(finish_data.get('final_answers', {})),
            "exam_mode": finish_data.get('exam_mode', False)
        })
        
        return success(data={}, message="Test finished securely")
        
    except Exception as e:
        logger.error(f"Error in finish_secure_test: {e}")
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
            log_security_event("RATE_LIMIT_EXCEEDED", user_id, lobby_id, {"endpoint": "secure_results"})
            raise HTTPException(status_code=429, detail="Too many requests")
        
        # Get lobby data
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Get user answers
        user_answers_doc = await db.user_answers.find_one({
            "lobby_id": lobby_id,
            "user_id": user_id
        })
        
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
        
        if not user_answers_doc:
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
        
        user_answers = user_answers_doc.get('answers', {})
        answered_count = len(user_answers)
        
        # Detailed answer analysis
        detailed_answers = []
        correct_count = 0
        category_stats = {}
        
        for i, question_id in enumerate(question_ids):
            question_id_str = str(question_id)
            
            # Get question details
            question = await db.questions.find_one({"_id": question_id})
            if not question:
                try:
                    question = await db.questions.find_one({"_id": ObjectId(question_id)})
                except:
                    pass
            
            if question:
                correct_answer_index = question.get('correct_answer', 0)
                user_answer = user_answers.get(question_id_str)
                is_answered = user_answer is not None
                is_correct = is_answered and user_answer == correct_answer_index
                
                if is_correct:
                    correct_count += 1
                
                # Category analysis
                question_categories = question.get('categories', [])
                for cat in question_categories:
                    if cat not in category_stats:
                        category_stats[cat] = {"total": 0, "correct": 0}
                    category_stats[cat]["total"] += 1
                    if is_correct:
                        category_stats[cat]["correct"] += 1
                
                # Question details
                question_detail = {
                    "question_number": i + 1,
                    "question_id": question_id_str,
                    "question_text": question.get('question_text', {}),
                    "options": [opt.get('text', {}) for opt in question.get('options', [])],
                    "correct_answer_index": correct_answer_index,
                    "user_answer_index": user_answer,
                    "is_answered": is_answered,
                    "is_correct": is_correct,
                    "categories": question_categories,
                    "explanation": question.get('explanation', {}),
                    "has_media": question.get('has_media', False),
                    "has_after_answer_media": question.get('has_after_answer_media', False)
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
        
        log_security_event("SECURE_RESULTS_RETRIEVED", user_id, lobby_id, {
            "answered": answered_count,
            "correct": correct_count,
            "percentage": percentage
        })
        
        return success(
            data=result_data,
            message="Enhanced test results retrieved successfully"
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_secure_test_results: {e}")
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
            log_security_event("RATE_LIMIT_EXCEEDED", user_id, lobby_id, {"endpoint": "report_question"})
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
        
        log_security_event("QUESTION_REPORTED", user_id, lobby_id, {
            "question_id": question_id,
            "report_type": report_type
        })
        
        return success(
            data={"report_submitted": True},
            message="Report submitted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in report_question: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 