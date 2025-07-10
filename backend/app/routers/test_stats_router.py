from fastapi import APIRouter, HTTPException, Depends, Request, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
from app.db.database import db
from app.core.security import get_current_actor
from app.core.response import success
from app.admin.permissions import get_current_admin_user
from app.logging import get_logger, LogSection, LogSubsection
from app.rate_limit import rate_limit_ip

router = APIRouter()
logger = get_logger(__name__)

def serialize_datetime(obj):
    """Сериализация datetime объектов для JSON"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    return obj

def convert_answer_to_index(correct_answer_raw):
    """Convert letter answer (A, B, C, D) to numeric index (0, 1, 2, 3)"""
    if isinstance(correct_answer_raw, str):
        letter_to_index = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        return letter_to_index.get(correct_answer_raw.upper(), 0)
    else:
        return correct_answer_raw if correct_answer_raw is not None else 0

@router.get("/user/{user_id}/simple-stats")
@rate_limit_ip("user_stats_simple", max_requests=120, window_seconds=30)
async def get_user_simple_stats(
    user_id: str,
    request: Request,
    current_user = Depends(get_current_actor)
):
    """Получить простую статистику пользователя: завершенные тесты и средний балл"""
    try:
        # Проверяем доступ
        current_user_id = str(current_user.get('id'))
        user_role = current_user.get('role', 'user')
        
        if user_role != 'admin' and current_user_id != user_id:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                message=f"Попытка доступа к статистике пользователя {user_id} от пользователя {current_user_id} (роль: {user_role})"
            )
            raise HTTPException(status_code=403, detail="Нет доступа к статистике другого пользователя")

        # Получаем пользователя
        try:
            user_oid = ObjectId(user_id)
        except:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Неверный формат ID пользователя: {user_id}"
            )
            raise HTTPException(status_code=400, detail="Неверный ID пользователя")
            
        user = await db.users.find_one({"_id": user_oid})
        if not user:
            user = await db.guests.find_one({"_id": user_oid})
        if not user:
            logger.warning(
                section=LogSection.USER,
                subsection=LogSubsection.USER.PROFILE,
                message=f"Пользователь {user_id} не найден при запросе статистики"
            )
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Получаем все завершенные лобби пользователя
        user_lobbies = await db.lobbies.find({
            "host_id": user_id,
            "status": "finished",  # Только завершенные тесты
            "participants": user_id  # Пользователь должен быть участником
        }).sort("created_at", -1).to_list(None)
        
        # Подсчитываем статистику используя оба поля ответов
        completed_tests = 0
        total_score = 0
        questions_processed = 0

        for lobby in user_lobbies:
            # Получаем ответы из обоих полей
            user_raw_answers = lobby.get("participants_raw_answers", {}).get(user_id, {})
            user_answers = lobby.get("participants_answers", {}).get(user_id, {})
            
            if user_raw_answers and user_answers:
                completed_tests += 1
                
                # Получаем вопросы лобби
                question_ids = lobby.get("question_ids", [])
                total_questions = len(question_ids)
                questions_processed += total_questions
                
                # Подсчитываем правильные ответы используя participants_answers
                correct_count = sum(1 for is_correct in user_answers.values() if is_correct)
                
                # Подсчитываем процент
                percentage = round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0
                total_score += percentage

        # Средний балл за все тесты
        average_score = round(total_score / completed_tests, 2) if completed_tests > 0 else 0

        result_data = {
            "completed_tests": completed_tests,  # Завершено тестов в общем у юзера (цифры)
            "average_score": average_score       # Средний балл в общем за все тесты (процент)
        }

        logger.info(
            section=LogSection.USER,
            subsection=LogSubsection.USER.PROFILE,
            message=f"Простая статистика для пользователя {user_id}: {completed_tests} завершённых тестов, средний балл {average_score}%"
        )
        
        return success(
            data=result_data,
            message="Простая статистика получена успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Критическая ошибка при получении простой статистики пользователя {user_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")

@router.get("/user/{user_id}/recent-tests")
@rate_limit_ip("user_recent_tests", max_requests=120, window_seconds=30)
async def get_user_recent_tests(
    user_id: str,
    request: Request,
    current_user = Depends(get_current_actor)
):
    """Получить недавние тесты пользователя за неделю"""
    try:
        # Проверяем доступ
        current_user_id = str(current_user.get('id'))
        user_role = current_user.get('role', 'user')
        
        if user_role != 'admin' and current_user_id != user_id:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                message=f"Попытка доступа к недавним тестам пользователя {user_id} от пользователя {current_user_id} (роль: {user_role})"
            )
            raise HTTPException(status_code=403, detail="Нет доступа к статистике другого пользователя")

        # Получаем все завершенные лобби пользователя за последнюю неделю
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        recent_lobbies = await db.lobbies.find({
            "host_id": user_id,
            "status": "finished",  # Только завершенные тесты
            "participants": user_id,  # Пользователь должен быть участником
            "created_at": {"$gte": start_date, "$lte": end_date}
        }).sort("created_at", -1).to_list(None)

        recent_tests = []
        
        for lobby in recent_lobbies:
            # Получаем ответы из обоих полей
            user_raw_answers = lobby.get("participants_raw_answers", {}).get(user_id, {})
            user_answers = lobby.get("participants_answers", {}).get(user_id, {})
            
            if user_raw_answers and user_answers:
                lobby_id = lobby["_id"]
                total_questions = len(lobby.get("question_ids", []))
                answered_count = len(user_raw_answers)
                correct_count = sum(1 for is_correct in user_answers.values() if is_correct)
                
                # Подсчитываем длительность
                test_duration = 0
                if lobby.get('created_at') and lobby.get('finished_at'):
                    start_time = lobby['created_at']
                    end_time = lobby['finished_at']
                    if isinstance(start_time, str):
                        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    if isinstance(end_time, str):
                        end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    test_duration = int((end_time - start_time).total_seconds())
                
                percentage = round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0
                
                recent_tests.append({
                    "lobby_id": str(lobby_id),
                    "completed_at": lobby.get('finished_at') or lobby.get('created_at'),
                    "score": percentage,
                    "duration": test_duration,
                    "correct_answers": correct_count,
                    "total_questions": total_questions,
                    "type": "exam" if lobby.get("exam_mode", False) else "practice",
                    "categories": lobby.get('categories', []),
                    "sections": lobby.get('sections', []),
                    "answered_questions": answered_count,
                    "passed": percentage >= 70,
                    "completion_rate": round((answered_count / total_questions * 100), 2) if total_questions > 0 else 0
                })

        result_data = serialize_datetime(recent_tests)

        logger.info(
            section=LogSection.USER,
            subsection=LogSubsection.USER.PROFILE,
            message=f"Получены недавние тесты для пользователя {user_id}: {len(recent_tests)} тестов за последние 7 дней"
        )
        
        return success(
            data=result_data,
            message="Недавние тесты получены успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Критическая ошибка при получении недавних тестов пользователя {user_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка получения недавних тестов")

@router.get("/user/{user_id}/all-tests")
@rate_limit_ip("user_all_tests", max_requests=120, window_seconds=30)
async def get_user_all_tests(
    user_id: str,
    request: Request,
    current_user = Depends(get_current_actor)
):
    """Получить все тесты пользователя с вводной информацией"""
    try:
        # Проверяем доступ
        current_user_id = str(current_user.get('id'))
        user_role = current_user.get('role', 'user')
        
        if user_role != 'admin' and current_user_id != user_id:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                message=f"Попытка доступа ко всем тестам пользователя {user_id} от пользователя {current_user_id} (роль: {user_role})"
            )
            raise HTTPException(status_code=403, detail="Нет доступа к статистике другого пользователя")

        # Получаем только завершенные лобби пользователя
        all_lobbies = await db.lobbies.find({
            "host_id": user_id,
            "status": "finished",  # Только завершенные тесты
            "participants": user_id,  # Пользователь должен быть участником
            "finished_at": {"$exists": True}  # Убедимся, что тест действительно завершен
        }).sort("created_at", -1).to_list(None)

        all_tests = []

        for lobby in all_lobbies:
            lobby_id = lobby["_id"]
            
            # Получаем ответы из обоих полей
            user_raw_answers = lobby.get("participants_raw_answers", {}).get(user_id, {})
            user_answers = lobby.get("participants_answers", {}).get(user_id, {})
            
            if user_raw_answers and user_answers:  # Проверяем наличие ответов
                total_questions = len(lobby.get("question_ids", []))
                answered_count = len(user_raw_answers)
                correct_count = sum(1 for is_correct in user_answers.values() if is_correct)
                
                # Подсчитываем длительность
                test_duration = 0
                if lobby.get('created_at') and lobby.get('finished_at'):
                    start_time = lobby['created_at']
                    end_time = lobby['finished_at']
                    if isinstance(start_time, str):
                        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    if isinstance(end_time, str):
                        end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    test_duration = int((end_time - start_time).total_seconds())
                
                percentage = round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0
                
                test_info = {
                    "lobby_id": str(lobby_id),
                    "date": lobby.get('created_at'),
                    "finished_at": lobby.get('finished_at'),
                    "type": "exam" if lobby.get("exam_mode", False) else "practice",
                    "categories": lobby.get('categories', []),
                    "sections": lobby.get('sections', []),
                    "total_questions": total_questions,
                    "answered_questions": answered_count,
                    "correct_answers": correct_count,
                    "percentage": percentage,
                    "passed": percentage >= 70,
                    "duration_seconds": test_duration,
                    "completion_rate": round((answered_count / total_questions * 100), 2) if total_questions > 0 else 0
                }
                
                all_tests.append(test_info)

        result_data = {
            "all_tests": serialize_datetime(all_tests),
            "total_count": len(all_tests),
            "completed_count": len(all_tests)  # Все тесты завершены
        }

        logger.info(
            section=LogSection.USER,
            subsection=LogSubsection.USER.PROFILE,
            message=f"Получен полный список завершенных тестов для пользователя {user_id}: {len(all_tests)} тестов"
        )
        
        return success(
            data=result_data,
            message="Все завершенные тесты получены успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Критическая ошибка при получении всех тестов пользователя {user_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка получения всех тестов")

@router.get("/{lobby_id}/secure/results")
@rate_limit_ip("test_results_secure", max_requests=20, window_seconds=60)
async def get_secure_test_results(
    lobby_id: str,
    request: Request,
    current_user: dict = Depends(get_current_actor)
):
    """Получить детальные результаты теста (перенесено из solo_lobby_router)"""
    try:
        user_id = str(current_user.get('id'))
        
        # Get lobby data
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.RESULTS,
                message=f"Попытка получить результаты несуществующего лобби {lobby_id} пользователем {user_id}"
            )
            raise HTTPException(status_code=404, detail="Lobby not found")
        
        # Проверяем, завершен ли тест
        if lobby.get('status') != 'finished':
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Попытка получить результаты незавершенного теста: лобби {lobby_id}, пользователь {user_id}, статус {lobby.get('status')}"
            )
            raise HTTPException(status_code=403, detail="Test is not finished yet")
        
        # Проверяем, является ли пользователь участником лобби
        if user_id not in lobby.get('participants', []):
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                message=f"Попытка получить результаты теста пользователем {user_id}, не являющимся участником лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Access denied - user is not a participant")

        # Get question IDs from lobby
        question_ids = lobby.get("question_ids", [])
        if not question_ids:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.VALIDATION,
                message=f"В лобби {lobby_id} отсутствуют вопросы"
            )
            raise HTTPException(status_code=500, detail="No questions found in lobby")
        
        # Get correct answers from lobby (already converted to indices)
        correct_answers = lobby.get("correct_answers", {})
        user_raw_answers = lobby.get("participants_raw_answers", {}).get(user_id, {})
        user_answers = lobby.get("participants_answers", {}).get(user_id, {})

        # Debug log for answers data
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Начало проверки ответов для лобби {lobby_id}. Всего вопросов: {len(question_ids)}, Отвечено: {len(user_raw_answers)}"
        )

        answered_count = len(user_raw_answers)  # Используем raw_answers для подсчета отвеченных вопросов

        # Detailed answer analysis
        detailed_answers = []
        correct_count = 0
        category_stats = {}

        for i, question_id in enumerate(question_ids):
            question_id_str = str(question_id)
            
            # Get correct answer from lobby
            correct_answer_index = correct_answers.get(question_id_str)
            
            # Get question details
            question = await db.questions.find_one({"_id": question_id})
            if not question:
                try:
                    question = await db.questions.find_one({"_id": ObjectId(question_id)})
                except:
                    pass
            
            # Get user's answer from raw_answers
            user_answer = user_raw_answers.get(question_id_str)
            is_answered = user_answer is not None
            
            # Compare answers only if question was answered
            is_correct = False
            if is_answered and correct_answer_index is not None:
                try:
                    # Convert both values to integers for comparison
                    user_answer_int = int(user_answer)
                    correct_answer_int = int(correct_answer_index)
                    is_correct = user_answer_int == correct_answer_int
                    
                    if is_correct:
                        correct_count += 1
                        
                    # Log comparison result
                    logger.info(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.VALIDATION,
                        message=f"Сравнение ответов: вопрос {i+1}, правильный={correct_answer_int}, ответ пользователя={user_answer_int}, результат={'верно' if is_correct else 'неверно'}"
                    )
                    
                except (ValueError, TypeError) as e:
                    logger.warning(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.VALIDATION,
                        message=f"Ошибка сравнения ответов для вопроса {question_id_str}: {str(e)}"
                    )
            
            if question:
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
                    "correct_answer_index": correct_answer_index,  # Use correct answer from lobby
                    "user_answer_index": user_answer,
                    "is_answered": is_answered,
                    "is_correct": is_correct,
                    "categories": question_categories,
                    "explanation": question.get('explanation', {}),
                    "has_media": question.get('has_media', False),
                    "has_after_answer_media": question.get('has_after_answer_media', False)
                }
                detailed_answers.append(question_detail)

        # Log final results
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.VALIDATION,
            message=f"Итоговый результат: правильно {correct_count} из {answered_count} отвеченных вопросов (всего вопросов: {len(question_ids)})"
        )
        
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
        
        if not user_raw_answers or not user_answers:
            # Log warning and return zero-answer result
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.RESULTS,
                message=f"Отсутствуют ответы пользователя {user_id} в participants_raw_answers или participants_answers для лобби {lobby_id}"
            )
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
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.RESULTS,
            message=f"Получены детальные результаты теста для лобби {lobby_id} пользователем {user_id}: {percentage}% ({correct_count}/{total_questions})"
        )
        
        return success(
            data=result_data,
            message="Enhanced test results retrieved successfully"
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Критическая ошибка при получении результатов теста для лобби {lobby_id} пользователем {user_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/user/{user_id}/stats")
@rate_limit_ip("user_stats_full", max_requests=120, window_seconds=30)
async def get_user_test_stats(
    user_id: str,
    request: Request,
    days: Optional[int] = Query(30, description="Количество дней для анализа"),
    current_user = Depends(get_current_actor)
):
    """Получить расширенную статистику тестов пользователя"""
    try:
        # Проверяем доступ
        current_user_id = str(current_user.get('id'))
        user_role = current_user.get('role', 'user')
        
        if user_role != 'admin' and current_user_id != user_id:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                message=f"Попытка доступа к расширенной статистике пользователя {user_id} от пользователя {current_user_id} (роль: {user_role})"
            )
            raise HTTPException(status_code=403, detail="Нет доступа к статистике другого пользователя")

        # Получаем пользователя
        try:
            user_oid = ObjectId(user_id)
        except:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Неверный формат ID пользователя при запросе расширенной статистики: {user_id}"
            )
            raise HTTPException(status_code=400, detail="Неверный ID пользователя")
            
        user = await db.users.find_one({"_id": user_oid})
        if not user:
            user = await db.guests.find_one({"_id": user_oid})
        if not user:
            logger.warning(
                section=LogSection.USER,
                subsection=LogSubsection.USER.PROFILE,
                message=f"Пользователь {user_id} не найден при запросе расширенной статистики"
            )
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Временной диапазон
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Получаем только завершенные лобби пользователя
        user_lobbies = await db.lobbies.find({
            "host_id": user_id,
            "status": "finished",  # Только завершенные тесты
            "participants": user_id,  # Пользователь должен быть участником
            "created_at": {"$gte": start_date, "$lte": end_date}
        }).sort("created_at", -1).to_list(None)

        # Инициализация статистики
        total_tests = len(user_lobbies)
        completed_tests = total_tests  # Все тесты завершены
        total_score = 0
        total_questions_answered = 0
        total_questions_total = 0
        exam_tests = 0
        practice_tests = 0
        passed_tests = 0
        
        # Статистика по категориям
        category_stats = {}
        
        # Недавние тесты (последние 10)
        recent_tests = []
        
        # Статистика по дням
        daily_stats = {}

        # Обрабатываем каждое лобби
        for lobby in user_lobbies:
            lobby_id = lobby["_id"]
            is_exam = lobby.get("exam_mode", False)
            
            if is_exam:
                exam_tests += 1
            else:
                practice_tests += 1
                
            # Получаем ответы из обоих полей
            user_raw_answers = lobby.get("participants_raw_answers", {}).get(user_id, {})
            user_answers = lobby.get("participants_answers", {}).get(user_id, {})
            
            if user_raw_answers and user_answers:
                # Получаем вопросы лобби
                total_questions = len(lobby.get("question_ids", []))
                answered_count = len(user_raw_answers)
                correct_count = sum(1 for is_correct in user_answers.values() if is_correct)
                
                total_questions_answered += answered_count
                total_questions_total += total_questions
                
                # Подсчитываем процент
                percentage = round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0
                total_score += percentage
                
                if percentage >= 70:
                    passed_tests += 1
                
                # Добавляем в недавние тесты
                if len(recent_tests) < 10:
                    test_duration = 0
                    if lobby.get('created_at') and lobby.get('finished_at'):
                        start_time = lobby['created_at']
                        end_time = lobby['finished_at']
                        if isinstance(start_time, str):
                            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        if isinstance(end_time, str):
                            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                        test_duration = int((end_time - start_time).total_seconds())
                    
                    recent_tests.append({
                        "lobby_id": str(lobby_id),
                        "date": lobby.get('created_at'),
                        "finished_at": lobby.get('finished_at'),
                        "type": "exam" if is_exam else "practice",
                        "categories": lobby.get('categories', []),
                        "sections": lobby.get('sections', []),
                        "total_questions": total_questions,
                        "answered_questions": answered_count,
                        "correct_answers": correct_count,
                        "percentage": percentage,
                        "passed": percentage >= 70,
                        "duration_seconds": test_duration,
                        "completion_rate": round((answered_count / total_questions * 100), 2) if total_questions > 0 else 0
                    })
                
                # Статистика по дням
                test_date = lobby.get('created_at')
                if test_date:
                    if isinstance(test_date, str):
                        test_date = datetime.fromisoformat(test_date.replace('Z', '+00:00'))
                    date_key = test_date.strftime('%Y-%m-%d')
                    
                    if date_key not in daily_stats:
                        daily_stats[date_key] = {
                            "tests_count": 0,
                            "total_score": 0,
                            "completed_tests": 0,
                            "passed_tests": 0
                        }
                    
                    daily_stats[date_key]["tests_count"] += 1
                    daily_stats[date_key]["total_score"] += percentage
                    daily_stats[date_key]["completed_tests"] += 1
                    if percentage >= 70:
                        daily_stats[date_key]["passed_tests"] += 1

        # Финализируем статистику по категориям
        for cat in category_stats:
            if category_stats[cat]["total_questions"] > 0:
                category_stats[cat]["percentage"] = round(
                    (category_stats[cat]["correct_answers"] / category_stats[cat]["total_questions"] * 100), 2
                )
            else:
                category_stats[cat]["percentage"] = 0

        # Средний балл за все тесты
        average_score = round(total_score / completed_tests, 2) if completed_tests > 0 else 0
        
        # Общий процент правильных ответов
        overall_accuracy = 0
        if total_questions_answered > 0:
            total_correct = sum(test["correct_answers"] for test in recent_tests)
            overall_accuracy = round((total_correct / total_questions_answered * 100), 2)

        # Статистика прогресса
        progress_stats = await calculate_progress_stats(user_id, end_date)

        # Формируем результат
        result_data = {
            "user_info": {
                "user_id": user_id,
                "full_name": user.get('full_name', ''),
                "username": user.get('username', ''),
                "email": user.get('email', '')
            },
            "period_info": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "overall_stats": {
                "total_tests": total_tests,
                "completed_tests": completed_tests,
                "passed_tests": passed_tests,
                "completion_rate": 100,  # Все тесты завершены
                "pass_rate": round((passed_tests / completed_tests * 100), 2) if completed_tests > 0 else 0,
                "average_score": average_score,
                "overall_accuracy": overall_accuracy,
                "exam_tests": exam_tests,
                "practice_tests": practice_tests,
                "total_questions_answered": total_questions_answered,
                "total_questions_available": total_questions_total
            },
            "category_performance": [
                {
                    "category": cat,
                    "total_questions": stats["total_questions"],
                    "correct_answers": stats["correct_answers"],
                    "percentage": stats["percentage"]
                }
                for cat, stats in sorted(category_stats.items(), key=lambda x: x[1]["percentage"], reverse=True)
            ],
            "recent_tests": serialize_datetime(recent_tests),
            "daily_stats": [
                {
                    "date": date,
                    "tests_count": stats["tests_count"],
                    "average_score": round(stats["total_score"] / stats["completed_tests"], 2) if stats["completed_tests"] > 0 else 0,
                    "completed_tests": stats["completed_tests"],
                    "passed_tests": stats["passed_tests"],
                    "pass_rate": round((stats["passed_tests"] / stats["completed_tests"] * 100), 2) if stats["completed_tests"] > 0 else 0
                }
                for date, stats in sorted(daily_stats.items(), reverse=True)
            ],
            "progress": progress_stats
        }

        logger.info(
            section=LogSection.USER,
            subsection=LogSubsection.USER.PROFILE,
            message=f"Получена расширенная статистика для пользователя {user_id}: {completed_tests} завершённых тестов, средний балл {average_score}%, {passed_tests} пройдено"
        )
        
        return success(
            data=result_data,
            message="Расширенная статистика тестов получена успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Критическая ошибка при получении расширенной статистики пользователя {user_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")

async def calculate_progress_stats(user_id: str, current_date: datetime) -> Dict[str, Any]:
    """Подсчет статистики прогресса пользователя за последние 2 недели"""
    try:
        # Последние 7 дней
        recent_start = current_date - timedelta(days=7)
        recent_end = current_date
        
        # Предыдущие 7 дней
        previous_start = current_date - timedelta(days=14)
        previous_end = recent_start

        # Получаем лобби за оба периода
        recent_lobbies = await db.lobbies.find({
            "creator_id": user_id,
            "created_at": {"$gte": recent_start, "$lte": recent_end}
        }).to_list(None)

        previous_lobbies = await db.lobbies.find({
            "creator_id": user_id,
            "created_at": {"$gte": previous_start, "$lte": previous_end}
        }).to_list(None)

        # Подсчитываем статистику для каждого периода
        recent_stats = await calculate_period_stats(user_id, recent_lobbies)
        previous_stats = await calculate_period_stats(user_id, previous_lobbies)

        # Подсчитываем изменения в процентах
        def calculate_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 2)

        return {
            "recent_period": {
                "tests_completed": recent_stats["completed"],
                "average_score": recent_stats["avg_score"],
                "total_questions": recent_stats["total_questions"],
                "passed_tests": recent_stats["passed"]
            },
            "previous_period": {
                "tests_completed": previous_stats["completed"],
                "average_score": previous_stats["avg_score"],
                "total_questions": previous_stats["total_questions"],
                "passed_tests": previous_stats["passed"]
            },
            "changes": {
                "tests_completed_change": calculate_change(recent_stats["completed"], previous_stats["completed"]),
                "average_score_change": calculate_change(recent_stats["avg_score"], previous_stats["avg_score"]),
                "questions_answered_change": calculate_change(recent_stats["total_questions"], previous_stats["total_questions"]),
                "passed_tests_change": calculate_change(recent_stats["passed"], previous_stats["passed"])
            }
        }

    except Exception as e:
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Ошибка при подсчёте статистики прогресса пользователя {user_id}: {str(e)}"
        )
        return {
            "recent_period": {"tests_completed": 0, "average_score": 0, "total_questions": 0, "passed_tests": 0},
            "previous_period": {"tests_completed": 0, "average_score": 0, "total_questions": 0, "passed_tests": 0},
            "changes": {"tests_completed_change": 0, "average_score_change": 0, "questions_answered_change": 0, "passed_tests_change": 0}
        }

async def calculate_period_stats(user_id: str, lobbies: List[Dict]) -> Dict[str, float]:
    """Подсчет статистики за определенный период"""
    if not lobbies:
        return {"completed": 0, "avg_score": 0, "total_questions": 0, "passed": 0}

    # Получаем ответы пользователя для этих лобби
    lobby_ids = [lobby["_id"] for lobby in lobbies]
    user_answers = await db.user_answers.find({
        "user_id": user_id,
        "lobby_id": {"$in": lobby_ids}
    }).to_list(None)

    answers_by_lobby = {ans["lobby_id"]: ans for ans in user_answers}

    completed_tests = 0
    total_score = 0
    total_questions = 0
    passed_tests = 0

    for lobby in lobbies:
        lobby_id = lobby["_id"]
        lobby_answers = answers_by_lobby.get(lobby_id)
        
        if lobby_answers:
            completed_tests += 1
            
            question_ids = lobby.get("question_ids", [])
            answers = lobby_answers.get("answers", {})
            total_questions += len(answers)
            
            correct_count = 0
            
            for question_id in question_ids:
                question_id_str = str(question_id)
                
                question = await db.questions.find_one({"_id": question_id})
                if not question:
                    try:
                        question = await db.questions.find_one({"_id": ObjectId(question_id)})
                    except:
                        continue
                
                if question:
                    correct_answer_index = convert_answer_to_index(question.get('correct_answer', 'A'))
                    user_answer = answers.get(question_id_str)
                    
                    if user_answer == correct_answer_index:
                        correct_count += 1
            
            percentage = round((correct_count / len(question_ids) * 100), 2) if question_ids else 0
            total_score += percentage
            
            if percentage >= 70:
                passed_tests += 1

    avg_score = round(total_score / completed_tests, 2) if completed_tests > 0 else 0

    return {
        "completed": completed_tests,
        "avg_score": avg_score,
        "total_questions": total_questions,
        "passed": passed_tests
    }

@router.get("/admin/global-stats")
@rate_limit_ip("admin_global_stats", max_requests=20, window_seconds=60)
async def get_global_test_stats(
    request: Request,
    days: Optional[int] = Query(30, description="Количество дней для анализа"),
    current_admin = Depends(get_current_admin_user)
):
    """Получить глобальную статистику тестов (только для админов)"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Общая статистика лобби
        total_lobbies = await db.lobbies.count_documents({
            "created_at": {"$gte": start_date, "$lte": end_date}
        })
        
        exam_lobbies = await db.lobbies.count_documents({
            "exam_mode": True,
            "created_at": {"$gte": start_date, "$lte": end_date}
        })
        
        practice_lobbies = total_lobbies - exam_lobbies

        # Статистика завершенных тестов
        completed_tests = await db.user_answers.count_documents({})

        # Топ категорий
        category_pipeline = [
            {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}}},
            {"$unwind": "$categories"},
            {"$group": {"_id": "$categories", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        top_categories = await db.lobbies.aggregate(category_pipeline).to_list(10)

        # Активность по дням
        daily_pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at"
                        }
                    },
                    "tests_count": {"$sum": 1},
                    "exam_count": {
                        "$sum": {"$cond": [{"$eq": ["$exam_mode", True]}, 1, 0]}
                    }
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        daily_activity = await db.lobbies.aggregate(daily_pipeline).to_list(None)

        # Статистика активных пользователей (используем host_id, а не creator_id)
        active_users = await db.lobbies.distinct("host_id", {
            "created_at": {"$gte": start_date, "$lte": end_date}
        })

        result_data = {
            "period_info": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "global_stats": {
                "total_tests": total_lobbies,
                "exam_tests": exam_lobbies,
                "practice_tests": practice_lobbies,
                "completed_tests": completed_tests,
                "active_users": len(active_users),
                "completion_rate": round((completed_tests / total_lobbies * 100), 2) if total_lobbies > 0 else 0
            },
            "top_categories": [
                {"category": cat["_id"], "count": cat["count"]}
                for cat in top_categories
            ],
            "daily_activity": [
                {
                    "date": day["_id"],
                    "total_tests": day["tests_count"],
                    "exam_tests": day["exam_count"],
                    "practice_tests": day["tests_count"] - day["exam_count"]
                }
                for day in daily_activity
            ]
        }

        logger.info(
            section=LogSection.ADMIN,
            subsection=LogSubsection.ADMIN.LIST_ACCESS,
            message=f"Получена глобальная статистика администратором: {total_lobbies} тестов, {len(active_users)} активных пользователей, {completed_tests} завершённых тестов"
        )
        
        return success(
            data=result_data,
            message="Глобальная статистика получена успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.API,
            subsection=LogSubsection.API.ERROR,
            message=f"Критическая ошибка при получении глобальной статистики: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка получения глобальной статистики") 