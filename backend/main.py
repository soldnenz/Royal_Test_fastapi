# app/main.py

import asyncio
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from aiogram import Dispatcher
from datetime import datetime, timedelta

from app.logging import setup_application_logging, get_logger, LogSection, LogSubsection, close_all_rabbitmq_connections
from app.core.security import security_background_tasks
from app.core.response import error
from app.routers import (
    user,
    authentication,
    test_router,
    media_router,
    subscription_router,
    test_stats_router,
    admin_router,
    reset_password,
    solo_lobby_router,
    solo_files_router,
    referrals_router,
    question_report_router,
    global_lobby_router,
    transaction_router
)
from app.multiplayer import (
    create_lobby_router,
    join_router,
    lobby_info_router,
    participants_router,
    kick_router,
    close_router,
    start_router,
    question_router,
    answer_router,
    media_router as multiplayer_media_router,
    after_answer_media_router,
    next_question_router,
    leave_router
)
from app.db.database import db, create_database_indexes

# Инициализация новой структурированной системы логирования
setup_application_logging()
logger = get_logger("main")

# Создаём приложение
app = FastAPI(
    title="Royal_api!",
    description="TI KTO VAHE1?",
    version="1.0.1",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# CORS middleware - БЕЗОПАСНАЯ КОНФИГУРАЦИЯ
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://royal-test.duckdns.org",
        "https://localhost:5173",  # Frontend dev server
        "https://localhost:3000",  # Alternative dev port
        # НЕ ИСПОЛЬЗУЕМ "*" в продакшене!
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Убираем OPTIONS из явного списка
    allow_headers=[
        "Content-Type",
        "Authorization", 
        "X-Requested-With",
        "Accept",
        "X-CSRF-Token"  # Для будущей CSRF защиты
    ],
)

# Подключаем роутеры
app.include_router(authentication.router, prefix="/auth", tags=["Authentication"])
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(reset_password.router, prefix="/reset", tags=["reset-password"])
app.include_router(test_router.router, prefix="/tests", tags=["Tests"])
app.include_router(subscription_router.router, prefix="/subscriptions")
app.include_router(referrals_router.router, prefix="/referrals")
app.include_router(transaction_router.router, prefix="/transactions")
app.include_router(global_lobby_router.router, prefix="/global-lobby", tags=["Global Lobby"])
app.include_router(solo_lobby_router.router, prefix="/lobby_solo", tags=["solo-lobbies"])
app.include_router(solo_files_router.router, prefix="/files_solo", tags=["solo-files"])
app.include_router(admin_router.router, prefix="/admin_function", tags=["admin_function"])
app.include_router(test_stats_router.router, prefix="/test-stats", tags=["test-stats"])
app.include_router(media_router.router, prefix="/media", tags=["media"])
app.include_router(question_report_router.router, prefix="/report", tags=["reports"])

# Multiplayer Routers
app.include_router(create_lobby_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(join_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(lobby_info_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(participants_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(kick_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(close_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(start_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(question_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(answer_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(multiplayer_media_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(after_answer_media_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(next_question_router, prefix="/multiplayer", tags=["Multiplayer"])
app.include_router(leave_router, prefix="/multiplayer", tags=["Multiplayer"])


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    path = request.url.path
    code = exc.status_code
    
    logger.warning(
        section=LogSection.API,
        subsection=LogSubsection.API.ERROR,
        message=f"HTTP исключение {code} для пути {path} (метод: {request.method}) - {exc.detail}"
    )

    # Если detail — это просто строка
    if isinstance(exc.detail, str):
        return error(code=code, message=exc.detail, details={"path": path})

    # Если detail — словарь (с кастомным message)
    if isinstance(exc.detail, dict):
        details = exc.detail.copy()
        if "path" not in details:
            details["path"] = path
        return error(
            code=code,
            message=details.get("message", "Ошибка запроса"),
            details=details
        )

    # Стандартные коды
    if code == HTTP_405_METHOD_NOT_ALLOWED:
        return error(code, "Метод не разрешён", details={"method": request.method, "path": path})
    if code == HTTP_404_NOT_FOUND:
        return error(code, "Страница не найдена", details={"path": path})
    if code == HTTP_401_UNAUTHORIZED:
        return error(code, "Требуется авторизация", details={"path": path})
    if code == HTTP_403_FORBIDDEN:
        return error(code, "Доступ запрещён", details={"path": path})
    if code == HTTP_429_TOO_MANY_REQUESTS:
        return error(code, "Слишком много запросов", details={"hint": "Попробуйте позже", "path": path})

    # На всякий случай
    return error(code=code, message="Ошибка запроса", details={"path": path})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    error_list = []
    for err in exc.errors():
        field = err.get("loc", ["неизвестное поле"])[-1]
        message = err.get("msg", "Некорректное значение")
        # Удаляем префикс "Value error, " если он присутствует
        prefix = "Value error, "
        if message.startswith(prefix):
            message = message[len(prefix):]
        error_list.append({"field": field, "message": message})
    
    logger.warning(
        section=LogSection.API,
        subsection=LogSubsection.API.VALIDATION,
        message=f"Ошибка валидации запроса для пути {request.url.path} (метод: {request.method})"
    )

    # Форматируем каждую ошибку в строку и объединяем через "; "
    formatted_error_details = "; ".join(
        [f"Поле «{item['field']}»: {item['message']}" for item in error_list]
    )
    return error(
        code=HTTP_422_UNPROCESSABLE_ENTITY,
        details="Ошибка валидации данных",
        message=formatted_error_details
    )

async def check_stalled_lobbies():
    """Автоматически завершает зависшие тесты"""
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.MAINTENANCE,
        message="Запуск задачи проверки зависших лобби"
    )
    while True:
        try:
            # Ищем лобби, которые в статусе in_progress более 2 часов
            two_hours_ago = datetime.utcnow() - timedelta(hours=2)
            
            stalled_lobbies = await db.lobbies.find({
                "status": "in_progress",
                "created_at": {"$lt": two_hours_ago}
            }).to_list(length=100)
            
            for lobby in stalled_lobbies:
                lobby_id = lobby["_id"]
                
                logger.info(
                    section=LogSection.SYSTEM,
                    subsection=LogSubsection.SYSTEM.CLEANUP,
                    message=f"Автоматическое завершение зависшего лобби {lobby_id}"
                )
                
                # Подсчитываем результаты
                results = {}
                total_questions = len(lobby.get("question_ids", []))
                for participant_id, answers in lobby.get("participants_answers", {}).items():
                    correct_count = sum(1 for is_corr in answers.values() if is_corr)
                    results[participant_id] = {"correct": correct_count, "total": total_questions}
                    
                    # Сохраняем историю
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
                        "auto_finished": True
                    }
                    await db.history.insert_one(history_record)
                
                # Отмечаем лобби как завершенное
                await db.lobbies.update_one(
                    {"_id": lobby_id},
                    {"$set": {
                        "status": "finished",
                        "finished_at": datetime.utcnow(),
                        "auto_finished": True
                    }}
                )
                
                logger.info(
                    section=LogSection.SYSTEM,
                    subsection=LogSubsection.SYSTEM.CLEANUP,
                    message=f"Лобби {lobby_id} отмечено как автоматически завершенное"
                )

                # Формируем JSON-сообщение о завершении
                finish_payload = {
                    "type": "test_finished",
                    "data": {
                        "results": results,
                        "auto_finished": True,
                        "reason": "stalled_lobby_timeout"
                    }
                }

                # Рассылаем JSON всем участникам (любой режим)
                try:
                    # The original code had ws_manager.broadcast_to_lobby(lobby_id, finish_payload)
                    # ws_manager is no longer imported, so this line is removed.
                    # If WebSocket communication is still needed, it must be re-implemented.
                    pass # Placeholder for future WebSocket communication
                except Exception as ws_err:
                    logger.error(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.ERROR,
                        message=f"Ошибка WebSocket рассылки для зависшего лобби {lobby_id}: {str(ws_err)}"
                    )

        except Exception as e:
            logger.error(
                section=LogSection.SYSTEM,
                subsection=LogSubsection.SYSTEM.CLEANUP,
                message=f"Ошибка проверки зависших лобби: {str(e)}"
            )
        
        # Проверяем раз в 30 минут
        await asyncio.sleep(1800)

@app.on_event("startup")
async def startup_event():
    """Запускается при старте приложения"""
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSubsection.SYSTEM.STARTUP,
        message="Запуск приложения"
    )
    
    # Создаем индексы базы данных
    try:
        await create_database_indexes(db)
        logger.info(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.STARTUP,
            message="Индексы базы данных успешно созданы"
        )
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.STARTUP,
            message=f"Ошибка при создании индексов базы данных: {str(e)}"
        )
    
    # Инициализируем rate limiter
    from app.rate_limit.rate_limiter import get_rate_limiter
    rate_limiter = get_rate_limiter()
    try:
        redis = await rate_limiter._get_redis_connection()
        if redis:
            logger.info(
                section=LogSection.SYSTEM,
                subsection=LogSubsection.SYSTEM.STARTUP,
                message="Rate limiter успешно подключен к Redis"
            )
        else:
            logger.error(
                section=LogSection.SYSTEM,
                subsection=LogSubsection.SYSTEM.STARTUP,
                message="Не удалось подключиться к Redis для rate limiter"
            )
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSubsection.SYSTEM.STARTUP,
            message=f"Ошибка при инициализации rate limiter: {str(e)}"
        )
    
    # Запускаем фоновые задачи
    asyncio.create_task(security_background_tasks())
    asyncio.create_task(check_stalled_lobbies())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSection.SYSTEM.SHUTDOWN,
        message="Завершение работы приложения Royal API"
    )
    
    # Закрываем RabbitMQ соединения
    try:
        await close_all_rabbitmq_connections()
        logger.info(
            section=LogSection.SYSTEM,
            subsection=LogSection.SYSTEM.SHUTDOWN,
            message="RabbitMQ соединения закрыты"
        )
    except Exception as e:
        logger.error(
            section=LogSection.SYSTEM,
            subsection=LogSection.SYSTEM.SHUTDOWN,
            message=f"Ошибка закрытия RabbitMQ соединений: {str(e)}"
        )
    
    # The original code had await ping_task.stop()
    # ping_task is no longer imported, so this line is removed.
    # If WebSocket ping is still needed, it must be re-implemented.
    logger.info(
        section=LogSection.SYSTEM,
        subsection=LogSection.SYSTEM.SHUTDOWN,
        message="Приложение Royal API успешно завершено"
    )
