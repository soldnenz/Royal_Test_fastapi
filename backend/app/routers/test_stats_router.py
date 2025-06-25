from fastapi import APIRouter, HTTPException, Depends, Request, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.db.database import db
from app.core.security import get_current_actor
from app.core.response import success
from app.admin.permissions import get_current_admin_user

router = APIRouter()
logger = logging.getLogger(__name__)

def serialize_datetime(obj):
    """Сериализация datetime объектов для JSON"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    return obj

@router.get("/user/{user_id}/simple-stats")
async def get_user_simple_stats(
    user_id: str,
    request: Request,
    current_user = Depends(get_current_actor)
):
    """Получить простую статистику пользователя: завершенные тесты и средний балл"""
    start_time = datetime.utcnow()
    logger.info(f"[SIMPLE_STATS] Starting request for user {user_id}")
    
    try:
        # Проверяем доступ
        auth_start = datetime.utcnow()
        current_user_id = str(current_user.get('id'))
        user_role = current_user.get('role', 'user')
        
        if user_role != 'admin' and current_user_id != user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к статистике другого пользователя")
        
        logger.info(f"[SIMPLE_STATS] Auth check took {(datetime.utcnow() - auth_start).total_seconds():.3f}s")

        # Получаем пользователя
        user_lookup_start = datetime.utcnow()
        try:
            user_oid = ObjectId(user_id)
        except:
            raise HTTPException(status_code=400, detail="Неверный ID пользователя")
            
        user = await db.users.find_one({"_id": user_oid})
        if not user:
            user = await db.guests.find_one({"_id": user_oid})
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
            
        logger.info(f"[SIMPLE_STATS] User lookup took {(datetime.utcnow() - user_lookup_start).total_seconds():.3f}s")

        # Получаем все лобби пользователя (используем host_id, а не creator_id)
        lobbies_start = datetime.utcnow()
        user_lobbies = await db.lobbies.find({
            "host_id": user_id
        }).sort("created_at", -1).to_list(None)
        
        logger.info(f"[SIMPLE_STATS] Lobbies query took {(datetime.utcnow() - lobbies_start).total_seconds():.3f}s")
        
        logger.info(f"[SIMPLE_STATS] Found {len(user_lobbies)} lobbies for user {user_id}")

        # Получаем ответы пользователя
        answers_start = datetime.utcnow()
        user_answers = await db.user_answers.find({
            "user_id": user_id
        }).to_list(None)
        
        logger.info(f"[SIMPLE_STATS] Answers query took {(datetime.utcnow() - answers_start).total_seconds():.3f}s")
        logger.info(f"[SIMPLE_STATS] Found {len(user_answers)} answer documents for user {user_id}")

        # Создаем словарь ответов по lobby_id
        dict_start = datetime.utcnow()
        answers_by_lobby = {ans["lobby_id"]: ans for ans in user_answers}
        logger.info(f"[SIMPLE_STATS] Dictionary creation took {(datetime.utcnow() - dict_start).total_seconds():.3f}s")

        # Подсчитываем завершенные тесты и средний балл
        calc_start = datetime.utcnow()
        completed_tests = 0
        total_score = 0
        questions_processed = 0

        # Собираем все уникальные question_ids для одного запроса
        all_question_ids = set()
        for lobby in user_lobbies:
            lobby_answers = answers_by_lobby.get(lobby["_id"])
            if lobby_answers:
                question_ids = lobby.get("question_ids", [])
                all_question_ids.update(question_ids)
        
        # Получаем все вопросы одним запросом
        questions_fetch_start = datetime.utcnow()
        
        # Преобразуем все ID в ObjectId для поиска
        search_ids = []
        for qid in all_question_ids:
            if isinstance(qid, str):
                try:
                    search_ids.append(ObjectId(qid))
                except:
                    search_ids.append(qid)
            else:
                search_ids.append(qid)
        
        all_questions = await db.questions.find({
            "_id": {"$in": search_ids}
        }).to_list(None)
        logger.info(f"[SIMPLE_STATS] Questions fetch took {(datetime.utcnow() - questions_fetch_start).total_seconds():.3f}s for {len(all_question_ids)} unique IDs, found {len(all_questions)} questions")
        logger.info(f"[SIMPLE_STATS] Sample question IDs from collection: {list(all_question_ids)[:3]}")
        logger.info(f"[SIMPLE_STATS] Sample question IDs found: {[str(q['_id']) for q in all_questions[:3]]}")
        
        # Создаем словарь вопросов для быстрого доступа (ключи и как ObjectId, и как строки)
        questions_dict = {}
        for q in all_questions:
            questions_dict[q["_id"]] = q  # ObjectId ключ
            questions_dict[str(q["_id"])] = q  # String ключ

        for lobby in user_lobbies:
            lobby_id = lobby["_id"]
            lobby_answers = answers_by_lobby.get(lobby_id)
            
            if lobby_answers:
                completed_tests += 1
                
                # Получаем вопросы лобби
                question_ids = lobby.get("question_ids", [])
                answers = lobby_answers.get("answers", {})
                
                correct_count = 0
                total_questions = len(question_ids)
                
                # Подсчитываем правильные ответы
                for question_id in question_ids:
                    questions_processed += 1
                    question_id_str = str(question_id)
                    
                    # Получаем вопрос из словаря (быстро!)
                    question = questions_dict.get(question_id)
                    if not question:
                        question = questions_dict.get(str(question_id))
                    
                    # Логируем первые несколько вопросов для отладки
                    if questions_processed <= 3:
                        logger.info(f"[SIMPLE_STATS] Debug Q{questions_processed}: ID={question_id} (type={type(question_id)}), found_question={question is not None}")
                        if question:
                            logger.info(f"[SIMPLE_STATS] Debug Q{questions_processed}: correct_answer={question.get('correct_answer')}, user_answer={answers.get(question_id_str)}")
                    
                    if question:
                        correct_answer_index = question.get('correct_answer', 0)
                        user_answer = answers.get(question_id_str)
                        
                        if user_answer == correct_answer_index:
                            correct_count += 1
                
                # Подсчитываем процент
                percentage = round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0
                total_score += percentage

        # Средний балл за все тесты
        average_score = round(total_score / completed_tests, 2) if completed_tests > 0 else 0
        
        logger.info(f"[SIMPLE_STATS] Calculations took {(datetime.utcnow() - calc_start).total_seconds():.3f}s")
        logger.info(f"[SIMPLE_STATS] Processed {questions_processed} questions across {len(user_lobbies)} lobbies")

        result_data = {
            "completed_tests": completed_tests,  # Завершено тестов в общем у юзера (цифры)
            "average_score": average_score       # Средний балл в общем за все тесты (процент)
        }

        total_time = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"[SIMPLE_STATS] Total request time: {total_time:.3f}s for user {user_id}")
        
        return success(
            data=result_data,
            message="Простая статистика получена успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SIMPLE_STATS] Error getting simple stats: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")

@router.get("/user/{user_id}/recent-tests")
async def get_user_recent_tests(
    user_id: str,
    request: Request,
    current_user = Depends(get_current_actor)
):
    """Получить недавние тесты пользователя за неделю"""
    request_start_time = datetime.utcnow()
    logger.info(f"[RECENT_TESTS] Starting request for user {user_id}")
    
    try:
        # Проверяем доступ
        auth_start = datetime.utcnow()
        current_user_id = str(current_user.get('id'))
        user_role = current_user.get('role', 'user')
        
        if user_role != 'admin' and current_user_id != user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к статистике другого пользователя")
        
        logger.info(f"[RECENT_TESTS] Auth check took {(datetime.utcnow() - auth_start).total_seconds():.3f}s")

        # Временной диапазон - последняя неделя
        date_calc_start = datetime.utcnow()
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        logger.info(f"[RECENT_TESTS] Date calculation took {(datetime.utcnow() - date_calc_start).total_seconds():.3f}s")

        # Получаем недавние лобби пользователя (используем host_id, а не creator_id)
        lobbies_start = datetime.utcnow()
        recent_lobbies = await db.lobbies.find({
            "host_id": user_id,
            "created_at": {"$gte": start_date, "$lte": end_date}
        }).sort("created_at", -1).to_list(None)
        
        logger.info(f"[RECENT_TESTS] Recent lobbies query took {(datetime.utcnow() - lobbies_start).total_seconds():.3f}s")
        logger.info(f"[RECENT_TESTS] Found {len(recent_lobbies)} recent lobbies")

        # Получаем ответы пользователя
        answers_start = datetime.utcnow()
        user_answers = await db.user_answers.find({
            "user_id": user_id
        }).to_list(None)
        
        logger.info(f"[RECENT_TESTS] Answers query took {(datetime.utcnow() - answers_start).total_seconds():.3f}s")
        logger.info(f"[RECENT_TESTS] Found {len(user_answers)} answer documents")

        dict_start = datetime.utcnow()
        answers_by_lobby = {ans["lobby_id"]: ans for ans in user_answers}
        logger.info(f"[RECENT_TESTS] Dictionary creation took {(datetime.utcnow() - dict_start).total_seconds():.3f}s")

        processing_start = datetime.utcnow()
        recent_tests = []
        questions_processed = 0

        # Собираем все уникальные question_ids для одного запроса
        all_question_ids = set()
        for lobby in recent_lobbies:
            lobby_answers = answers_by_lobby.get(lobby["_id"])
            if lobby_answers:
                question_ids = lobby.get("question_ids", [])
                all_question_ids.update(question_ids)
        
        # Получаем все вопросы одним запросом
        questions_fetch_start = datetime.utcnow()
        
        # Преобразуем все ID в ObjectId для поиска
        search_ids = []
        for qid in all_question_ids:
            if isinstance(qid, str):
                try:
                    search_ids.append(ObjectId(qid))
                except:
                    search_ids.append(qid)
            else:
                search_ids.append(qid)
        
        all_questions = await db.questions.find({
            "_id": {"$in": search_ids}
        }).to_list(None)
        logger.info(f"[RECENT_TESTS] Questions fetch took {(datetime.utcnow() - questions_fetch_start).total_seconds():.3f}s for {len(all_question_ids)} unique IDs, found {len(all_questions)} questions")
        logger.info(f"[RECENT_TESTS] Sample question IDs from collection: {list(all_question_ids)[:3]}")
        logger.info(f"[RECENT_TESTS] Sample question IDs found: {[str(q['_id']) for q in all_questions[:3]]}")
        
        # Создаем словарь вопросов для быстрого доступа (ключи и как ObjectId, и как строки)
        questions_dict = {}
        for q in all_questions:
            questions_dict[q["_id"]] = q  # ObjectId ключ
            questions_dict[str(q["_id"])] = q  # String ключ

        for lobby in recent_lobbies:
            lobby_id = lobby["_id"]
            lobby_answers = answers_by_lobby.get(lobby_id)
            
            if lobby_answers:
                # Получаем вопросы лобби
                question_ids = lobby.get("question_ids", [])
                answers = lobby_answers.get("answers", {})
                
                correct_count = 0
                answered_count = len(answers)
                total_questions = len(question_ids)
                
                # Подсчитываем правильные ответы
                for question_id in question_ids:
                    questions_processed += 1
                    question_id_str = str(question_id)
                    
                    # Получаем вопрос из словаря (быстро!)
                    question = questions_dict.get(question_id)
                    if not question:
                        question = questions_dict.get(str(question_id))
                    
                    if question:
                        correct_answer_index = question.get('correct_answer', 0)
                        user_answer = answers.get(question_id_str)
                        
                        if user_answer == correct_answer_index:
                            correct_count += 1
                
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
                    "completed_at": lobby.get('finished_at') or lobby.get('created_at'),  # Используем finished_at если есть
                    "score": percentage,  # Изменено: используем score для фронтенда
                    "duration": test_duration,  # Изменено: duration в секундах
                    "correct_answers": correct_count,
                    "total_questions": total_questions,
                    "type": "exam" if lobby.get("exam_mode", False) else "practice",
                    "categories": lobby.get('categories', []),
                    "sections": lobby.get('sections', []),
                    "answered_questions": answered_count,
                    "passed": percentage >= 70,
                    "completion_rate": round((answered_count / total_questions * 100), 2) if total_questions > 0 else 0
                })

        logger.info(f"[RECENT_TESTS] Processing took {(datetime.utcnow() - processing_start).total_seconds():.3f}s")
        logger.info(f"[RECENT_TESTS] Processed {questions_processed} questions across {len(recent_lobbies)} lobbies")
        
        serialization_start = datetime.utcnow()
        result_data = serialize_datetime(recent_tests)
        logger.info(f"[RECENT_TESTS] Serialization took {(datetime.utcnow() - serialization_start).total_seconds():.3f}s")

        total_time = (datetime.utcnow() - request_start_time).total_seconds()
        logger.info(f"[RECENT_TESTS] Total request time: {total_time:.3f}s for user {user_id}")
        
        return success(
            data=result_data,
            message="Недавние тесты получены успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RECENT_TESTS] Error getting recent tests: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения недавних тестов")

@router.get("/user/{user_id}/all-tests")
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
            raise HTTPException(status_code=403, detail="Нет доступа к статистике другого пользователя")

        # Получаем все лобби пользователя (используем host_id, а не creator_id)
        all_lobbies = await db.lobbies.find({
            "host_id": user_id
        }).sort("created_at", -1).to_list(None)

        # Получаем ответы пользователя
        user_answers = await db.user_answers.find({
            "user_id": user_id
        }).to_list(None)

        answers_by_lobby = {ans["lobby_id"]: ans for ans in user_answers}

        all_tests = []

        for lobby in all_lobbies:
            lobby_id = lobby["_id"]
            lobby_answers = answers_by_lobby.get(lobby_id)
            
            # Базовая информация о тесте
            test_info = {
                "lobby_id": str(lobby_id),
                "date": lobby.get('created_at'),
                "type": "exam" if lobby.get("exam_mode", False) else "practice",
                "categories": lobby.get('categories', []),
                "sections": lobby.get('sections', []),
                "total_questions": len(lobby.get("question_ids", [])),
                "status": "completed" if lobby_answers else "not_completed"
            }
            
            if lobby_answers:
                # Получаем вопросы лобби
                question_ids = lobby.get("question_ids", [])
                answers = lobby_answers.get("answers", {})
                
                correct_count = 0
                answered_count = len(answers)
                total_questions = len(question_ids)
                
                # Подсчитываем правильные ответы
                for question_id in question_ids:
                    question_id_str = str(question_id)
                    
                    question = await db.questions.find_one({"_id": question_id})
                    if not question:
                        try:
                            question = await db.questions.find_one({"_id": ObjectId(question_id)})
                        except:
                            continue
                    
                    if question:
                        correct_answer_index = question.get('correct_answer', 0)
                        user_answer = answers.get(question_id_str)
                        
                        if user_answer == correct_answer_index:
                            correct_count += 1
                
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
                
                # Дополняем информацию результатами
                test_info.update({
                    "answered_questions": answered_count,
                    "correct_answers": correct_count,
                    "percentage": percentage,
                    "passed": percentage >= 70,
                    "duration_seconds": test_duration,
                    "completion_rate": round((answered_count / total_questions * 100), 2) if total_questions > 0 else 0,
                    "finished_at": lobby.get('finished_at')
                })
            else:
                # Тест не завершен
                test_info.update({
                    "answered_questions": 0,
                    "correct_answers": 0,
                    "percentage": 0,
                    "passed": False,
                    "duration_seconds": 0,
                    "completion_rate": 0,
                    "finished_at": None
                })
            
            all_tests.append(test_info)

        result_data = {
            "all_tests": serialize_datetime(all_tests),
            "total_count": len(all_tests),
            "completed_count": len([t for t in all_tests if t["status"] == "completed"])
        }

        logger.info(f"[ALL_TESTS] Retrieved all tests for user {user_id} from {request.client.host}")
        
        return success(
            data=result_data,
            message="Все тесты получены успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ALL_TESTS] Error getting all tests: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения всех тестов")

@router.get("/{lobby_id}/secure/results")
async def get_secure_test_results(
    lobby_id: str,
    current_user: dict = Depends(get_current_actor)
):
    """Получить детальные результаты теста (перенесено из solo_lobby_router)"""
    try:
        user_id = str(current_user.get('id'))
        
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
        
        logger.info(f"[SECURE_RESULTS] Retrieved results for lobby {lobby_id} user {user_id}")
        
        return success(
            data=result_data,
            message="Enhanced test results retrieved successfully"
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_secure_test_results: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/user/{user_id}/stats")
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
            raise HTTPException(status_code=403, detail="Нет доступа к статистике другого пользователя")

        # Получаем пользователя
        try:
            user_oid = ObjectId(user_id)
        except:
            raise HTTPException(status_code=400, detail="Неверный ID пользователя")
            
        user = await db.users.find_one({"_id": user_oid})
        if not user:
            user = await db.guests.find_one({"_id": user_oid})
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Временной диапазон
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Получаем все лобби пользователя (используем host_id, а не creator_id)
        user_lobbies = await db.lobbies.find({
            "host_id": user_id,
            "created_at": {"$gte": start_date, "$lte": end_date}
        }).sort("created_at", -1).to_list(None)

        # Получаем ответы пользователя
        user_answers = await db.user_answers.find({
            "user_id": user_id
        }).to_list(None)

        # Создаем словарь ответов по lobby_id
        answers_by_lobby = {ans["lobby_id"]: ans for ans in user_answers}

        # Инициализация статистики
        total_tests = len(user_lobbies)
        completed_tests = 0
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
                
            # Получаем ответы для этого лобби
            lobby_answers = answers_by_lobby.get(lobby_id)
            
            if lobby_answers:
                completed_tests += 1
                
                # Получаем вопросы лобби
                question_ids = lobby.get("question_ids", [])
                answers = lobby_answers.get("answers", {})
                
                correct_count = 0
                answered_count = len(answers)
                total_questions = len(question_ids)
                
                total_questions_answered += answered_count
                total_questions_total += total_questions
                
                # Подсчитываем правильные ответы и статистику по категориям
                for i, question_id in enumerate(question_ids):
                    question_id_str = str(question_id)
                    
                    # Получаем вопрос
                    question = await db.questions.find_one({"_id": question_id})
                    if not question:
                        try:
                            question = await db.questions.find_one({"_id": ObjectId(question_id)})
                        except:
                            continue
                    
                    if question:
                        correct_answer_index = question.get('correct_answer', 0)
                        user_answer = answers.get(question_id_str)
                        is_correct = user_answer == correct_answer_index
                        
                        if is_correct:
                            correct_count += 1
                        
                        # Статистика по категориям
                        question_categories = question.get('categories', [])
                        for cat in question_categories:
                            if cat not in category_stats:
                                category_stats[cat] = {
                                    "total_questions": 0,
                                    "correct_answers": 0,
                                    "tests_count": 0
                                }
                            category_stats[cat]["total_questions"] += 1
                            if is_correct:
                                category_stats[cat]["correct_answers"] += 1
                
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
                "total_tests_started": total_tests,
                "completed_tests": completed_tests,  # Новая метрика: завершено тестов
                "passed_tests": passed_tests,
                "completion_rate": round((completed_tests / total_tests * 100), 2) if total_tests > 0 else 0,
                "pass_rate": round((passed_tests / completed_tests * 100), 2) if completed_tests > 0 else 0,
                "average_score": average_score,  # Новая метрика: средний балл за все тесты
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
            "recent_tests": serialize_datetime(recent_tests),  # Новая секция: недавние тесты
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

        logger.info(f"[TEST_STATS] Retrieved stats for user {user_id} from {request.client.host}")
        
        return success(
            data=result_data,
            message="Расширенная статистика тестов получена успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TEST_STATS] Error getting user stats: {e}")
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
        logger.error(f"Error calculating progress stats: {e}")
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
                    correct_answer_index = question.get('correct_answer', 0)
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

        logger.info(f"[ADMIN_TEST_STATS] Retrieved global stats from {request.client.host}")
        
        return success(
            data=result_data,
            message="Глобальная статистика получена успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ADMIN_TEST_STATS] Error getting global stats: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения глобальной статистики") 