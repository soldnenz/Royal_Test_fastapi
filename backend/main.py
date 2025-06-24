# app/main.py

import logging
import asyncio
from app.core.validation_translator import translate_error_ru
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
import json

from app.core.logging_config import setup_logging
from app.core.security import security_background_tasks
from app.core.response import error
from app.routers import authentication, user, reset_password, admin_router, test_router, subscription_router, referrals_router, transaction_router, admin_router
from app.admin.telegram_2fa import bot, router as telegram_routers
from app.routers import lobby_router
from app.routers.lobby_router import start_background_tasks
from app.routers import files_router
from app.routers import solo_lobby_router
from app.routers import solo_files_router
from app.routers import websocket_router
from app.websocket.lobby_ws import lobby_ws_endpoint, ws_manager
from app.websocket.ping_task import ping_task
from app.db.database import db

# Инициализация логирования
setup_logging()
logger = logging.getLogger(__name__)

# Создаём приложение
app = FastAPI(
    title="Royal_api!",
    description="TI KTO VAHE1?",
    version="1.0.1",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost",
        "https://royal-test.duckdns.org",
        "*"  # Временно разрешаем все источники для тестирования WebSocket
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(authentication.router, prefix="/auth", tags=["authentication"])
app.include_router(user.router, prefix="/users", tags=["users"])
app.include_router(reset_password.router, prefix="/reset", tags=["reset-password"])
app.include_router(test_router.router, prefix="/tests", tags=["tests"])
app.include_router(subscription_router.router, prefix="/subscriptions")
app.include_router(referrals_router.router, prefix="/referrals")
app.include_router(transaction_router.router, prefix="/transactions")
app.include_router(lobby_router.router, prefix="/lobbies", tags=["lobbies"])
app.include_router(files_router.router, prefix="/files", tags=["files"])
app.include_router(solo_lobby_router.router, prefix="/lobby_solo", tags=["solo-lobbies"])
app.include_router(solo_files_router.router, prefix="/files_solo", tags=["solo-files"])
app.include_router(websocket_router.router, prefix="/websocket_token", tags=["websocket"])
app.include_router(admin_router.router, prefix="/admin_function", tags=["admin_function"])
# WebSocket endpoint для лобби
@app.websocket("/ws/lobby/{lobby_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    lobby_id: str, 
    token: str = Query(None)
):
    await lobby_ws_endpoint(websocket, lobby_id, token)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    path = request.url.path
    code = exc.status_code

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

    # Форматируем каждую ошибку в строку и объединяем через "; "
    formatted_error_details = "; ".join(
        [f"Поле «{item['field']}»: {item['message']}" for item in error_list]
    )
    return error(
        code=HTTP_422_UNPROCESSABLE_ENTITY,
        details="Ошибка валидации данных",
        message=formatted_error_details
    )

# Запуск Telegram-бота через polling
async def start_bot():
    dp = Dispatcher()
    dp.include_router(telegram_routers)
    await dp.start_polling(bot)

async def check_stalled_lobbies():
    """Автоматически завершает зависшие тесты"""
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
                    await ws_manager.broadcast_to_lobby(lobby_id, finish_payload)
                except Exception as ws_err:
                    logger.error(f"WS broadcast error for stalled lobby {lobby_id}: {ws_err}")

                # Закрываем все WS-соединения для этого лобби
                if lobby_id in ws_manager.connections:
                    for conn in list(ws_manager.connections[lobby_id]):
                        try:
                            await conn["websocket"].close(code=1000, reason="Lobby auto-finished")
                        except Exception:
                            pass
                    ws_manager.connections.pop(lobby_id, None)

        except Exception as e:
            logger.error(f"Ошибка при проверке зависших лобби: {e}")
        
        # Проверяем раз в 30 минут
        await asyncio.sleep(1800)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_bot())
    asyncio.create_task(check_stalled_lobbies())  # Запускаем проверку зависших лобби
    # Запуск фоновых задач безопасности
    asyncio.create_task(security_background_tasks())
    asyncio.create_task(start_background_tasks())  # Запускаем задачи фоновой обработки
    await ping_task.start()  # Запускаем задачу пинга WebSocket соединений

@app.on_event("shutdown")
async def shutdown_event():
    await ping_task.stop()  # Останавливаем задачу пинга при завершении
