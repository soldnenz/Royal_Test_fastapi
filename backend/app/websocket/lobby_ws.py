from fastapi import WebSocket, WebSocketDisconnect, HTTPException, Request, Depends, Query
from typing import Dict, List
from app.db.database import db
from datetime import datetime, timedelta
import jwt
from app.core.config import settings
from bson import ObjectId
import json
import asyncio
import re
from app.logging import get_logger, LogSection, LogSubsection

# Настройка логгера
logger = get_logger(__name__)

def safe_log_message(data: str, max_length: int = 100) -> str:
    """Безопасное логирование сообщений без чувствительных данных"""
    if len(data) > max_length:
        data = f"{data[:max_length]}... (truncated)"
    # Удаляем токены и другие чувствительные данные
    safe_data = re.sub(r'"token":\s*"[^"]*"', '"token": "***"', data)
    safe_data = re.sub(r'"password":\s*"[^"]*"', '"password": "***"', safe_data)
    return safe_data

class LobbyConnectionManager:
    def __init__(self):
        # Словарь активных соединений: ключ - lobby_id, значение - список соединений
        self.connections: Dict[str, List[dict]] = {}
        # Кэш пользователей для оптимизации
        self.user_cache: Dict[str, dict] = {}
        # Максимальные лимиты для стабильности
        self.max_connections_per_lobby = 35
        self.max_total_connections = 2000
        # Интервал проверки соединений (без пинг/понг)
        self.heartbeat_interval = 15  # секунд
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.CONNECTION,
            message="LobbyConnectionManager инициализирован с оптимизациями производительности и ping/pong"
        )

    async def _send_to_connection(self, websocket: WebSocket, message: str, user_id: str):
        """Безопасная отправка сообщения в одно WebSocket соединение"""
        try:
            # Проверяем состояние WebSocket перед отправкой
            if websocket is None:
                logger.warning(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.ERROR,
                    message=f"WebSocket равен None для пользователя {user_id}"
                )
                return False
            
            # Проверяем состояние соединения
            try:
                client_state = getattr(websocket, 'client_state', None)
                if client_state and hasattr(client_state, 'name') and client_state.name in ['DISCONNECTED', 'CLOSED']:
                    logger.warning(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
                        message=f"WebSocket уже закрыт для пользователя {user_id}"
                    )
                    return False
            except Exception:
                # Если не можем проверить состояние, пробуем отправить
                pass
            
            await websocket.send_text(message)
            return True
        except Exception as e:
            error_str = str(e)
            # Логируем только если это не ожидаемые ошибки закрытия соединения
            if "1005" not in error_str and "1006" not in error_str and "closed" not in error_str.lower():
                logger.error(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.ERROR,
                    message=f"Не удалось отправить сообщение пользователю {user_id}: {error_str}"
                )
            else:
                logger.debug(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
                    message=f"Соединение закрыто для пользователя {user_id}: {error_str}"
                )
            return False

    async def get_user_info(self, user_id: str):
        """Получение информации о пользователе или госте с кэшированием"""
        # Проверяем кэш (время жизни 5 минут)
        if user_id in self.user_cache:
            cached_data = self.user_cache[user_id]
            if (datetime.utcnow() - cached_data.get("cached_at", datetime.min)).total_seconds() < 300:
                return cached_data
        
        # Загружаем из базы и кэшируем
        try:
            # Проверяем, это гость или обычный пользователь
            if isinstance(user_id, str) and user_id.startswith("guest_"):
                guest = await db.guests.find_one({"_id": user_id})
                user_info = {
                    "full_name": guest.get("full_name", "Guest") if guest else "Guest",
                    "email": guest.get("email", "") if guest else "",
                    "is_guest": True,
                    "cached_at": datetime.utcnow()
                }
                self.user_cache[user_id] = user_info
                return user_info
            elif ObjectId.is_valid(user_id):
                user = await db.users.find_one({"_id": ObjectId(user_id)})
                user_info = {
                    "full_name": user.get("full_name", "Unknown") if user else "Unknown",
                    "email": user.get("email", "") if user else "",
                    "is_guest": False,
                    "cached_at": datetime.utcnow()
                }
                self.user_cache[user_id] = user_info
                return user_info
            else:
                # Неизвестный формат user_id
                logger.warning(
                    section=LogSection.SECURITY,
                    subsection=LogSubsection.SECURITY.VALIDATION,
                    message=f"Неизвестный формат user_id: {user_id}"
                )
                return {"full_name": "Unknown", "email": "", "is_guest": False, "cached_at": datetime.utcnow()}
        except Exception as e:
            logger.error(
                section=LogSection.API,
                subsection=LogSubsection.API.ERROR,
                message=f"Ошибка загрузки пользователя {user_id}: {str(e)}"
            )
            
        # Fallback
        return {"full_name": "Unknown", "email": "", "is_guest": False, "cached_at": datetime.utcnow()}

    async def connect(self, lobby_id: str, user_id: str, websocket: WebSocket):
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.CONNECTION,
            message=f"Новая попытка подключения к лобби {lobby_id} от пользователя {user_id}"
        )
        
        # Проверяем лимиты
        current_lobby_connections = len(self.connections.get(lobby_id, []))
        if current_lobby_connections >= self.max_connections_per_lobby:
            logger.warning(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.CONNECTION,
                message=f"Лобби {lobby_id} переполнено ({current_lobby_connections} соединений)"
            )
            await websocket.close(code=1008, reason="Lobby is full")
            return False
            
        total_connections = sum(len(conns) for conns in self.connections.values())
        if total_connections >= self.max_total_connections:
            logger.warning(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.CONNECTION,
                message=f"Сервер достиг максимальной нагрузки ({total_connections} общих соединений)"
            )
            await websocket.close(code=1008, reason="Server capacity reached")
            return False
        
        await websocket.accept()
        if lobby_id not in self.connections:
            self.connections[lobby_id] = []
        
        connection_info = {
            "websocket": websocket, 
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "is_alive": True
        }
        self.connections[lobby_id].append(connection_info)
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.CONNECTION,
            message=f"Соединение принято. Активные соединения в лобби {lobby_id}: {len(self.connections[lobby_id])}"
        )
        
        return True

    async def disconnect(self, lobby_id: str, websocket: WebSocket):
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
            message=f"Отключение от лобби {lobby_id}"
        )
        if lobby_id in self.connections:
            try:
                for i, conn in enumerate(self.connections[lobby_id]):
                    if conn["websocket"] == websocket:
                        user_id = conn['user_id']
                        self.connections[lobby_id].pop(i)
                        logger.info(
                            section=LogSection.WEBSOCKET,
                            subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
                            message=f"Пользователь {user_id} отключился от лобби {lobby_id}"
                        )
                        break
            except Exception as e:
                logger.error(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.ERROR,
                    message=f"Ошибка при отключении: {str(e)}"
                )
            if not self.connections[lobby_id]:
                del self.connections[lobby_id]
                logger.info(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
                    message=f"Лобби {lobby_id} больше не имеет соединений"
                )

    async def send_message(self, lobby_id: str, message: str):
        """Отправка текстового сообщения всем участникам лобби (старый метод - оставляем для совместимости)"""
        if lobby_id in self.connections:
            logger.debug(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
                message=f"Отправка сообщения в лобби {lobby_id}: {message}"
            )
            for conn in list(self.connections[lobby_id]):
                try:
                    await conn["websocket"].send_text(message)
                except Exception as e:
                    logger.error(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.ERROR,
                        message=f"Ошибка отправки сообщения пользователю {conn['user_id']}: {str(e)}"
                    )

    async def send_message_parallel(self, lobby_id: str, message: str):
        """Оптимизированная параллельная отправка сообщения всем участникам лобби"""
        if lobby_id not in self.connections:
            return
            
        connections = list(self.connections[lobby_id])  # Копируем список для безопасности
        if not connections:
            return
            
        logger.debug(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
            message=f"Параллельная отправка сообщения {len(connections)} пользователям в лобби {lobby_id}"
        )
        
        # Создаем задачи для параллельной отправки
        tasks = []
        for conn in connections:
            task = self._send_to_connection(conn["websocket"], message, conn["user_id"])
            tasks.append(task)
        
        # Выполняем все отправки параллельно
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for result in results if result is True)
            logger.debug(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
                message=f"Параллельная рассылка завершена: {success_count}/{len(tasks)} успешно"
            )

    async def send_json(self, lobby_id: str, data: dict):
        """Отправка JSON данных (старый метод - оставляем для совместимости)"""
        if lobby_id in self.connections:
            json_str = json.dumps(data)
            logger.debug(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
                message=f"Отправка JSON в лобби {lobby_id}: {data}"
            )
            await self.send_message(lobby_id, json_str)

    async def send_json_parallel(self, lobby_id: str, data: dict):
        """Оптимизированная параллельная отправка JSON данных"""
        if lobby_id not in self.connections:
            return
            
        # Сериализуем JSON один раз для всех получателей
        json_str = json.dumps(data)
        logger.debug(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
            message=f"Параллельная отправка JSON в лобби {lobby_id}: {data}"
        )
        await self.send_message_parallel(lobby_id, json_str)

    async def broadcast_to_lobby(self, lobby_id: str, data: dict):
        """Broadcast с автоматическим выбором оптимального метода"""
        connections_count = len(self.connections.get(lobby_id, []))
        
        # Используем параллельный метод для лобби с более чем 3 участниками
        if connections_count > 3:
            await self.send_json_parallel(lobby_id, data)
        else:
            await self.send_json(lobby_id, data)

    def get_user_id_by_websocket(self, lobby_id: str, websocket: WebSocket):
        if lobby_id in self.connections:
            for conn in self.connections[lobby_id]:
                if conn["websocket"] == websocket:
                    return conn["user_id"]
        return None

    async def broadcast_answer_status(self, lobby_id: str, user_id: int, is_correct: bool, question_id: int):
        message = {
            "type": "answer_status",
            "data": {
                "user_id": user_id,
                "is_correct": is_correct,
                "question_id": question_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.LOBBY_EVENTS,
            message=f"Рассылка статуса ответа для пользователя {user_id} в лобби {lobby_id}"
        )
        await self.broadcast_to_lobby(lobby_id, message)

    async def broadcast_user_status_update(self, lobby_id: str, user_id: str, status: str):
        """Уведомление об изменении статуса пользователя (подключение/отключение)"""
        user_info = await self.get_user_info(user_id)
        message = {
            "type": "user_status_update",
            "data": {
                "user_id": user_id,
                "status": status,  # "joined", "left", "online", "offline"
                "user_name": user_info.get("full_name", "Unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.LOBBY_EVENTS,
            message=f"Рассылка обновления статуса пользователя: {user_id} {status} в лобби {lobby_id}"
        )
        await self.broadcast_to_lobby(lobby_id, message)

    async def check_connections(self, lobby_id: str):
        """Проверка состояния WebSocket соединений"""
        if lobby_id not in self.connections:
            return
            
        current_time = datetime.utcnow()
        connections_to_remove = []
        
        for i, conn in enumerate(self.connections[lobby_id]):
            try:
                # Проверяем состояние WebSocket соединения
                websocket = conn["websocket"]
                
                # Проверяем, что websocket и его состояние не None
                if websocket is None:
                    logger.warning(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.ERROR,
                        message=f"WebSocket равен None для пользователя {conn['user_id']} в лобби {lobby_id}"
                    )
                    conn["is_alive"] = False
                    connections_to_remove.append(i)
                    continue
                
                # Безопасная проверка состояния клиента
                try:
                    client_state = getattr(websocket, 'client_state', None)
                    if client_state is None:
                        logger.warning(
                            section=LogSection.WEBSOCKET,
                            subsection=LogSubsection.WEBSOCKET.ERROR,
                            message=f"WebSocket client_state равен None для пользователя {conn['user_id']} в лобби {lobby_id}"
                        )
                        conn["is_alive"] = False
                        connections_to_remove.append(i)
                        continue
                    
                    # Если соединение закрыто, помечаем для удаления
                    if hasattr(client_state, 'name') and client_state.name in ['DISCONNECTED', 'CLOSED']:
                        logger.warning(
                            section=LogSection.WEBSOCKET,
                            subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
                            message=f"WebSocket отключен для пользователя {conn['user_id']} в лобби {lobby_id}"
                        )
                        conn["is_alive"] = False
                        connections_to_remove.append(i)
                        continue
                except Exception as state_error:
                    logger.warning(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.ERROR,
                        message=f"Ошибка проверки состояния WebSocket для пользователя {conn['user_id']}: {str(state_error)}"
                    )
                    conn["is_alive"] = False
                    connections_to_remove.append(i)
                    continue
                
                # Проверяем активность (если нет активности более 5 минут, считаем неактивным)
                time_since_activity = (current_time - conn.get("last_activity", current_time)).total_seconds()
                if time_since_activity > 300:  # 5 минут
                    logger.warning(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
                        message=f"Пользователь {conn['user_id']} неактивен {time_since_activity}с в лобби {lobby_id}"
                    )
                    # Пытаемся отправить тестовое сообщение
                    try:
                        test_message = json.dumps({"type": "heartbeat", "timestamp": current_time.isoformat()})
                        await websocket.send_text(test_message)
                        conn["last_activity"] = current_time
                    except Exception:
                        # Если не удалось отправить, соединение мертво
                        conn["is_alive"] = False
                        connections_to_remove.append(i)
                
            except Exception as e:
                logger.error(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.ERROR,
                    message=f"Ошибка проверки соединения для пользователя {conn['user_id']}: {str(e)}"
                )
                conn["is_alive"] = False
                connections_to_remove.append(i)
        
        # Удаляем мертвые соединения и оповещаем о статусе
        for i in reversed(connections_to_remove):
            if i < len(self.connections[lobby_id]):
                removed_conn = self.connections[lobby_id].pop(i)
                logger.info(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
                    message=f"Удалено мертвое соединение для пользователя {removed_conn['user_id']}"
                )
                try:
                    await self.broadcast_user_status_update(lobby_id, removed_conn["user_id"], "left")
                except Exception as broadcast_error:
                    logger.error(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.ERROR,
                        message=f"Ошибка рассылки статуса выхода пользователя: {str(broadcast_error)}"
                    )

    def update_user_activity(self, lobby_id: str, websocket: WebSocket):
        """Обновление времени последней активности пользователя"""
        if lobby_id in self.connections:
            for conn in self.connections[lobby_id]:
                if conn["websocket"] == websocket:
                    conn["last_activity"] = datetime.utcnow()
                    break

    def get_online_users(self, lobby_id: str) -> List[str]:
        """Получение списка онлайн пользователей в лобби"""
        if lobby_id not in self.connections:
            return []
        
        current_time = datetime.utcnow()
        online_users = []
        
        for conn in self.connections[lobby_id]:
            try:
                # Проверяем состояние WebSocket и активность
                websocket = conn["websocket"]
                
                # Проверяем, что websocket не None
                if websocket is None:
                    continue
                
                # Безопасная проверка состояния клиента
                is_connected = True
                try:
                    client_state = getattr(websocket, 'client_state', None)
                    if client_state and hasattr(client_state, 'name'):
                        is_connected = client_state.name not in ['DISCONNECTED', 'CLOSED']
                except Exception:
                    # Если не можем проверить состояние, считаем отключенным
                    is_connected = False
                
                time_since_activity = (current_time - conn.get("last_activity", current_time)).total_seconds()
                
                if conn.get("is_alive", True) and is_connected and time_since_activity <= 300:  # 5 минут
                    online_users.append(conn["user_id"])
            except Exception as e:
                logger.error(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.ERROR,
                    message=f"Ошибка проверки онлайн статуса для пользователя {conn.get('user_id', 'unknown')}: {str(e)}"
                )
                continue
        
        return online_users

    async def broadcast_question_results(self, lobby_id: str, question_id: int, results: List[dict]):
        message = {
            "type": "question_results",
            "data": {
                "question_id": question_id,
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.LOBBY_EVENTS,
            message=f"Рассылка результатов вопроса {question_id} в лобби {lobby_id}"
        )
        await self.broadcast_to_lobby(lobby_id, message)

    async def broadcast_final_results(self, lobby_id: str, results: List[dict]):
        message = {
            "type": "final_results",
            "data": {
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.LOBBY_EVENTS,
            message=f"Рассылка финальных результатов для лобби {lobby_id}"
        )
        await self.broadcast_to_lobby(lobby_id, message)

    async def send_to_user(self, lobby_id: str, user_id: str, data: dict):
        """Отправка сообщения конкретному пользователю в лобби"""
        if lobby_id not in self.connections:
            return False
            
        json_str = json.dumps(data)
        for conn in self.connections[lobby_id]:
            if conn["user_id"] == user_id:
                success = await self._send_to_connection(conn["websocket"], json_str, user_id)
                return success
        return False

    async def handle_message(self, lobby_id: str, user_id: str, message_data: dict):
        """Обработка входящих WebSocket сообщений от клиентов"""
        message_type = message_data.get("type")
        data = message_data.get("data", {})
        
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.MESSAGE,
            message=f"Обработка WebSocket сообщения от пользователя {user_id} в лобби {lobby_id}: {message_type}"
        )
        
        try:
            if message_type == "ping":
                # Отвечаем на ping сообщения
                await self.send_to_user(lobby_id, user_id, {
                    "type": "pong",
                    "data": {"timestamp": datetime.utcnow().isoformat()}
                })
                
            elif message_type == "heartbeat":
                # Обновляем активность пользователя
                if lobby_id in self.connections:
                    for conn in self.connections[lobby_id]:
                        if conn["user_id"] == user_id:
                            conn["last_activity"] = datetime.utcnow()
                            break
                            
            elif message_type == "request_current_question":
                # Запрос текущего вопроса
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if lobby and lobby.get("status") == "in_progress":
                    current_index = lobby.get("current_index", 0)
                    question_ids = lobby.get("question_ids", [])
                    if current_index < len(question_ids):
                        await self.send_to_user(lobby_id, user_id, {
                            "type": "current_question",
                            "data": {
                                "question_id": question_ids[current_index],
                                "question_index": current_index
                            }
                        })
                        
            elif message_type == "request_sync":
                # Запрос синхронизации текущего вопроса
                logger.info(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.MESSAGE,
                    message=f"Пользователь {user_id} запросил синхронизацию для лобби {lobby_id}"
                )
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if lobby:
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
                                question = await db.questions.find_one({"_id": ObjectId(current_question_id)})
                                if question:
                                    correct_answer_index = question.get("correct_answer_index")
                                    explanation = question.get("explanation", "")
                            except Exception as e:
                                logger.error(
                                    section=LogSection.API,
                                    subsection=LogSubsection.API.ERROR,
                                    message=f"Ошибка получения правильного ответа для вопроса {current_question_id}: {str(e)}"
                                )
                    
                    sync_data = {
                        "current_question_index": current_index,
                        "current_question_id": current_question_id,
                        "lobby_status": lobby.get("status"),
                        "show_correct_answer": current_question_correct_shown,
                        "show_participant_answers": lobby.get("show_participant_answers", False),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    # Добавляем correct_answer_index и explanation если правильный ответ был показан
                    if correct_answer_index is not None:
                        sync_data["correct_answer_index"] = correct_answer_index
                        sync_data["explanation"] = explanation
                    
                    await self.send_to_user(lobby_id, user_id, {
                        "type": "sync_response",
                        "data": sync_data
                    })
                    logger.info(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
                        message=f"Отправлен ответ синхронизации пользователю {user_id}: индекс={current_index}, question_id={current_question_id}, правильный_показан={current_question_correct_shown}"
                    )
                        
            elif message_type == "request_lobby_status":
                # Запрос статуса лобби
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if lobby:
                    await self.send_to_user(lobby_id, user_id, {
                        "type": "lobby_status",
                        "data": {
                            "status": lobby.get("status"),
                            "current_index": lobby.get("current_index", 0),
                            "participants": lobby.get("participants", []),
                            "show_participant_answers": lobby.get("show_participant_answers", False)
                        }
                    })
                    
            elif message_type == "request_participants":
                # Запрос списка участников
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if lobby:
                    participants_info = []
                    for participant_id in lobby.get("participants", []):
                        try:
                            if isinstance(participant_id, str) and participant_id.startswith("guest_"):
                                # Гость
                                guest = await db.guests.find_one({"_id": participant_id})
                                if guest:
                                    participants_info.append({
                                        "id": guest["_id"],
                                        "name": guest.get("full_name", "Unknown Guest"),
                                        "is_host": participant_id == lobby.get("host_id"),
                                        "online": participant_id in self.get_online_users(lobby_id)
                                    })
                            else:
                                # Обычный пользователь
                                user = await db.users.find_one({"_id": ObjectId(participant_id)})
                                if user:
                                    participants_info.append({
                                        "id": str(user["_id"]),
                                        "name": user.get("full_name", "Unknown User"),
                                        "is_host": str(user["_id"]) == lobby.get("host_id"),
                                        "online": participant_id in self.get_online_users(lobby_id)
                                    })
                        except Exception as e:
                            logger.error(
                                section=LogSection.API,
                                subsection=LogSubsection.API.ERROR,
                                message=f"Ошибка получения информации об участнике {participant_id}: {str(e)}"
                            )
                            continue
                    
                    await self.send_to_user(lobby_id, user_id, {
                        "type": "participants_list",
                        "data": {
                            "participants": participants_info
                        }
                    })
                    
            elif message_type == "answer_submitted":
                # Участник отправил ответ - уведомляем других участников
                logger.info(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.LOBBY_EVENTS,
                    message=f"Рассылка отправки ответа от пользователя {user_id} в лобби {lobby_id}"
                )
                await self.broadcast_to_lobby(lobby_id, {
                    "type": "answer_submitted",
                    "data": data
                })
                
            elif message_type == "host_next_question":
                # Хост переходит к следующему вопросу - уведомляем участников
                logger.info(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.LOBBY_EVENTS,
                    message=f"Рассылка следующего вопроса от хоста {user_id} в лобби {lobby_id}"
                )
                await self.broadcast_to_lobby(lobby_id, {
                    "type": "host_next_question", 
                    "data": data
                })
                
            elif message_type == "host_finish_test":
                # Хост завершает тест - уведомляем участников
                logger.info(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.LOBBY_EVENTS,
                    message=f"Рассылка завершения теста от хоста {user_id} в лобби {lobby_id}"
                )
                await self.broadcast_to_lobby(lobby_id, {
                    "type": "host_finish_test",
                    "data": data
                })
                
            elif message_type == "show_correct_answer":
                # Хост показывает правильный ответ
                logger.info(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.LOBBY_EVENTS,
                    message=f"Рассылка показа правильного ответа от пользователя {user_id} в лобби {lobby_id}"
                )
                
                # Получаем информацию о лобби для контекста
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if lobby and lobby.get("host_id") == user_id:
                    # Сохраняем информацию о показанном правильном ответе
                    question_id = data.get("question_id")
                    if question_id:
                        await db.lobbies.update_one(
                            {"_id": lobby_id},
                            {
                                "$set": {
                                    f"shown_correct_answers.{question_id}": True
                                }
                            }
                        )
                        logger.info(
                            section=LogSection.LOBBY,
                            subsection=LogSubsection.LOBBY.QUESTIONS,
                            message=f"Отмечен правильный ответ как показанный для вопроса {question_id} в лобби {lobby_id}"
                        )
                    
                    # Пересылаем сообщение с дополнительным контекстом
                    await self.broadcast_to_lobby(lobby_id, {
                        "type": "show_correct_answer",
                        "data": {
                            **data,
                            "timestamp": datetime.utcnow().isoformat(),
                            "sent_by_host": True
                        }
                    })
                else:
                    logger.warning(
                        section=LogSection.SECURITY,
                        subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                        message=f"Не-хост пользователь {user_id} попытался показать правильный ответ в лобби {lobby_id}"
                    )
                    
            else:
                logger.warning(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.MESSAGE,
                    message=f"Неизвестный тип сообщения: {message_type} от пользователя {user_id} в лобби {lobby_id}"
                )
                
        except Exception as e:
            logger.error(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.ERROR,
                message=f"Ошибка обработки WebSocket сообщения: {str(e)}"
            )


ws_manager = LobbyConnectionManager()


async def verify_token(token: str):
    """Верифицирует JWT токен и возвращает информацию о пользователе или госте."""
    logger.info(
        section=LogSection.AUTH,
        subsection=LogSubsection.AUTH.TOKEN_VALIDATION,
        message="Верификация токена"
    )
    try:
        # Сначала пробуем WS токены
        try:
            ws_token = await db.ws_tokens.find_one({"token": token, "used": False})
            if ws_token and ws_token.get("expires_at") > datetime.utcnow():
                logger.info(
                    section=LogSection.AUTH,
                    subsection=LogSubsection.AUTH.TOKEN_VALIDATION,
                    message=f"Найден действительный WS токен для пользователя {ws_token.get('user_id')}"
                )
                await db.ws_tokens.update_one(
                    {"_id": ws_token["_id"]},
                    {"$set": {"used": True, "used_at": datetime.utcnow()}}
                )
                user_id = ws_token.get("user_id")
                
                # Проверяем, это гость или обычный пользователь
                if isinstance(user_id, str) and user_id.startswith("guest_"):
                    guest = await db.guests.find_one({"_id": user_id})
                    if guest:
                        logger.info(
                            section=LogSection.AUTH,
                            subsection=LogSubsection.AUTH.GUEST_VALIDATED,
                            message=f"Гость {user_id} успешно верифицирован"
                        )
                        return {
                            "id": guest["_id"],
                            "full_name": guest.get("full_name"),
                            "email": guest.get("email"),
                            "is_guest": True,
                            "lobby_id": guest.get("lobby_id")
                        }
                elif ObjectId.is_valid(user_id):
                    user = await db.users.find_one({"_id": ObjectId(user_id)})
                    if user:
                        logger.info(
                            section=LogSection.AUTH,
                            subsection=LogSubsection.AUTH.USER_VALIDATED,
                            message=f"Пользователь {user_id} успешно верифицирован"
                        )
                        return {
                            "id": str(user["_id"]),
                            "full_name": user.get("full_name"),
                            "email": user.get("email"),
                            "is_guest": False
                        }
            logger.warning(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TOKEN_VALIDATION,
                message="WS токен не найден или истек, переходим к обычной верификации токена"
            )
        except Exception as e:
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TOKEN_VALIDATION,
                message=f"Ошибка верификации WS токена: {str(e)}"
            )
            
        # Обычная проверка JWT токена
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
        
        # Проверяем гостевой токен
        if role == "guest" and isinstance(user_id, str) and user_id.startswith("guest_"):
            token_doc = await db.tokens.find_one({"token": token})
            if not token_doc or token_doc.get("revoked") or token_doc.get("expires_at") < datetime.utcnow():
                logger.error(
                    section=LogSection.AUTH,
                    subsection=LogSubsection.AUTH.TOKEN_INVALID,
                    message="Гостевой токен не найден, отозван или истек"
                )
                return None
                
            await db.tokens.update_one(
                {"_id": token_doc["_id"]},
                {"$set": {"last_activity": datetime.utcnow()}}
            )
            
            guest = await db.guests.find_one({"_id": user_id})
            if not guest:
                logger.error(
                    section=LogSection.AUTH,
                    subsection=LogSubsection.AUTH.USER_NOT_FOUND,
                    message=f"Гость {user_id} не найден"
                )
                return None
            logger.info(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.GUEST_VALIDATED,
                message=f"Гость {user_id} успешно верифицирован с обычным токеном"
            )
            return {
                "id": guest["_id"],
                "full_name": guest.get("full_name"),
                "email": guest.get("email"),
                "is_guest": True,
                "lobby_id": guest.get("lobby_id")
            }
        
        # Обычный пользователь
        if not user_id or not ObjectId.is_valid(user_id):
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TOKEN_INVALID,
                message="Неверный ID пользователя в токене"
            )
            return None
            
        token_doc = await db.tokens.find_one({"token": token})
        if not token_doc or token_doc.get("revoked") or token_doc.get("expires_at") < datetime.utcnow():
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TOKEN_INVALID,
                message="Токен не найден, отозван или истек"
            )
            return None
            
        await db.tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {"last_activity": datetime.utcnow()}}
        )
        
        # Проверяем, что это не гость
        if isinstance(user_id, str) and user_id.startswith("guest_"):
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.TOKEN_INVALID,
                message="ID гостя в обычной верификации пользователя"
            )
            return None
        
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(
                section=LogSection.AUTH,
                subsection=LogSubsection.AUTH.USER_NOT_FOUND,
                message=f"Пользователь {user_id} не найден"
            )
            return None
            
        logger.info(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.USER_VALIDATED,
            message=f"Пользователь {user_id} успешно верифицирован с обычным токеном"
        )
        return {
            "id": str(user["_id"]),
            "full_name": user.get("full_name"),
            "email": user.get("email"),
            "is_guest": False
        }
    except Exception as e:
        logger.error(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_VALIDATION,
            message=f"Ошибка верификации токена: {str(e)}"
        )
        return None


async def lobby_ws_endpoint(websocket: WebSocket, lobby_id: str, token: str = Query(...)):
    logger.info(
        section=LogSection.WEBSOCKET,
        subsection=LogSubsection.WEBSOCKET.CONNECTION,
        message=f"Новый запрос WebSocket соединения для лобби {lobby_id}"
    )
    if not token:
        logger.error(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_MISSING,
            message="Токен не предоставлен"
        )
        await websocket.close(code=1008, reason="Unauthorized: No token provided")
        return

    user_data = await verify_token(token)
    if not user_data:
        logger.error(
            section=LogSection.AUTH,
            subsection=LogSubsection.AUTH.TOKEN_INVALID,
            message="Неверный токен"
        )
        await websocket.close(code=1008, reason="Unauthorized: Invalid token")
        return

    user_id = str(user_data["id"])
    logger.info(
        section=LogSection.WEBSOCKET,
        subsection=LogSubsection.WEBSOCKET.CONNECTION,
        message=f"Пользователь {user_id} ({user_data.get('full_name', 'Unknown')}) подключается к лобби {lobby_id}"
    )

    lobby = await db.lobbies.find_one({"_id": lobby_id})
    if not lobby:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Лобби {lobby_id} не найдено"
        )
        await websocket.close(code=1008, reason="Lobby not found")
        return

    if user_id != lobby["host_id"]:
        other_lobbies = await db.lobbies.find_one({
            "participants": user_id,
            "_id": {"$ne": lobby_id},
            "status": {"$nin": ["finished", "closed"]}
        })
        if other_lobbies:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Пользователь {user_id} уже в другом активном лобби"
            )
            await websocket.close(code=1008,
                                  reason="У вас уже есть активное лобби. Завершите его перед подключением к новому.")
            return

    if user_id not in lobby["participants"]:
        if lobby["status"] == "waiting":
            logger.info(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.JOIN,
                message=f"Добавление пользователя {user_id} в лобби {lobby_id}"
            )
            await db.lobbies.update_one({"_id": lobby_id}, {
                "$push": {"participants": user_id},
                "$set": {f"participants_answers.{user_id}": {}}
            })
        else:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Невозможно присоединиться к лобби {lobby_id}: тест уже начат или завершен"
            )
            await websocket.close(code=1008, reason="Невозможно присоединиться: тест уже начат или завершен")
            return

    # Проверяем лимиты соединений
    connection_result = await ws_manager.connect(lobby_id, user_id, websocket)
    if not connection_result:
        # Соединение было отклонено из-за лимитов
        return
        
    # Даем паузу для стабилизации соединения
    await asyncio.sleep(0.5)
        
    # Получаем кэшированную информацию о пользователе
    user_info = await ws_manager.get_user_info(user_id)
    
    # Проверяем, что соединение все еще активно перед отправкой сообщений
    if lobby_id not in ws_manager.connections or not any(conn["user_id"] == user_id for conn in ws_manager.connections[lobby_id]):
        logger.warning(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
            message=f"Пользователь {user_id} отключился перед отправкой приветственных сообщений"
        )
        return
    
    # Уведомляем всех о подключении пользователя
    await ws_manager.broadcast_to_lobby(lobby_id, {
        "type": "user_joined",
        "data": {
            "user_id": user_id,
            "is_host": user_id == lobby["host_id"],
            "user_name": user_info.get("full_name", "Unknown User")
        }
    })
    
    # Пауза между сообщениями
    await asyncio.sleep(0.1)
    
    # Проверяем соединение еще раз
    if lobby_id not in ws_manager.connections or not any(conn["user_id"] == user_id for conn in ws_manager.connections[lobby_id]):
        logger.warning(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
            message=f"Пользователь {user_id} отключился во время приветственной последовательности"
        )
        return
    
    # Отправляем статус пользователя как "online"
    await ws_manager.broadcast_user_status_update(lobby_id, user_id, "online")
    
    # Пауза между сообщениями
    await asyncio.sleep(0.1)
    
    # Финальная проверка соединения
    if lobby_id not in ws_manager.connections or not any(conn["user_id"] == user_id for conn in ws_manager.connections[lobby_id]):
        logger.warning(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
            message=f"Пользователь {user_id} отключился перед отправкой обновления участников"
        )
        return
    
    # Также отправляем обновленный список участников
    updated_lobby = await db.lobbies.find_one({"_id": lobby_id})
    if updated_lobby:
        await ws_manager.broadcast_to_lobby(lobby_id, {
            "type": "participants_updated",
            "data": {
                "participants": updated_lobby.get("participants", []),
                "participant_count": len(updated_lobby.get("participants", []))
            }
        })

    if lobby["status"] == "in_progress":
        current_index = lobby.get("current_index", 0)
        if 0 <= current_index < len(lobby["question_ids"]):
            current_question_id = lobby["question_ids"][current_index]
            logger.info(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
                message=f"Отправка текущего вопроса {current_question_id} пользователю {user_id}"
            )
            await websocket.send_json({"type": "current_question", "data": {"question_id": current_question_id}})
            if user_id == lobby["host_id"]:
                answered_users = []
                for participant_id in lobby["participants"]:
                    if current_question_id in lobby.get("participants_answers", {}).get(participant_id, {}):
                        is_correct = lobby["participants_answers"][participant_id][current_question_id]
                        answered_users.append({"user_id": participant_id, "is_correct": is_correct})
                await websocket.send_json({"type": "answered_users", "data": answered_users})

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.MESSAGE,
                message=f"Получено сообщение от пользователя {user_id}: {safe_log_message(data)}"
            )

            # Обновляем активность пользователя при любом сообщении
            ws_manager.update_user_activity(lobby_id, websocket)

            # Пробуем парсить как JSON
            try:
                message_data = json.loads(data)
                await ws_manager.handle_message(lobby_id, user_id, message_data)
                continue
            except json.JSONDecodeError:
                # Если не JSON, обрабатываем как старый формат
                pass

            if data.startswith("ANSWER:"):
                _, qid, answer_idx = data.split(":")
                answer_idx = int(answer_idx)
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.ANSWERS,
                    message=f"Обработка ответа от пользователя {user_id} для вопроса {qid}"
                )

                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if not lobby or lobby["status"] != "in_progress":
                    continue

                question = await db.questions.find_one({"_id": ObjectId(qid)})
                if not question:
                    continue

                correct_answer = question.get("correct_answer", 0)
                is_correct = answer_idx == correct_answer

                await db.lobbies.update_one(
                    {"_id": lobby_id},
                    {"$set": {f"participants_answers.{user_id}.{qid}": is_correct}}
                )

                await ws_manager.broadcast_answer_status(lobby_id, user_id, is_correct, qid)

                if user_id == lobby["host_id"]:
                    answered_users = []
                    for participant_id in lobby["participants"]:
                        if qid in lobby.get("participants_answers", {}).get(participant_id, {}):
                            participant_is_correct = lobby["participants_answers"][participant_id][qid]
                            answered_users.append({"user_id": participant_id, "is_correct": participant_is_correct})
                    await websocket.send_json({"type": "answered_users", "data": answered_users})

            elif data.startswith("PING"):
                await websocket.send_text("PONG")

            elif data.startswith("HEARTBEAT"):
                # Обновляем время последней активности
                if lobby_id in ws_manager.connections:
                    for conn in ws_manager.connections[lobby_id]:
                        if conn["websocket"] == websocket:
                            conn["last_activity"] = datetime.utcnow()
                            break

            elif data.startswith("NEXT_QUESTION"):
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.QUESTIONS,
                    message=f"Обработка запроса следующего вопроса от пользователя {user_id}"
                )
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if not lobby:
                    logger.error(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.ACCESS,
                        message=f"Лобби {lobby_id} не найдено"
                    )
                    await websocket.send_json({"type": "error", "data": {"message": "Лобби не найдено"}})
                    continue

                if lobby["host_id"] != user_id:
                    logger.warning(
                        section=LogSection.SECURITY,
                        subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                        message=f"Не-хост пользователь {user_id} попытался перейти к следующему вопросу"
                    )
                    await websocket.send_json(
                        {"type": "error", "data": {"message": "Только хост может перейти к следующему вопросу"}})
                    continue

                if lobby["status"] != "in_progress":
                    logger.error(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.STATUS,
                        message=f"Тест не активен в лобби {lobby_id}"
                    )
                    await websocket.send_json({"type": "error", "data": {"message": "Тест не активен"}})
                    continue

                current_index = lobby.get("current_index", 0)
                total_questions = len(lobby.get("question_ids", []))

                if current_index < total_questions - 1 and current_index < 39:
                    new_index = current_index + 1
                    logger.info(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.QUESTIONS,
                        message=f"Переход к следующему вопросу {new_index} в лобби {lobby_id}"
                    )
                    await db.lobbies.update_one({"_id": lobby_id}, {"$set": {"current_index": new_index}})
                    next_question_id = lobby["question_ids"][new_index]
                    await ws_manager.broadcast_to_lobby(lobby_id, {
                        "type": "next_question", 
                        "data": {
                            "question_id": next_question_id,
                            "question_index": new_index
                        }
                    })
                else:
                    logger.info(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.STATUS,
                        message=f"Тест завершен в лобби {lobby_id}"
                    )
                    await db.lobbies.update_one(
                        {"_id": lobby_id},
                        {"$set": {"status": "finished", "finished_at": datetime.utcnow()}}
                    )

                    updated_lobby = await db.lobbies.find_one({"_id": lobby_id})
                    results = {}
                    total_questions = len(updated_lobby.get("question_ids", []))
                    for participant_id, answers in updated_lobby.get("participants_answers", {}).items():
                        correct_count = sum(1 for is_corr in answers.values() if is_corr)
                        results[participant_id] = {"correct": correct_count, "total": total_questions}

                        history_record = {
                            "user_id": participant_id,
                            "lobby_id": lobby_id,
                            "date": datetime.utcnow(),
                            "score": correct_count,
                            "total": total_questions,
                            "categories": updated_lobby.get("categories", []),
                            "sections": updated_lobby.get("sections", []),
                            "mode": updated_lobby.get("mode", "solo"),
                            "pass_percentage": (correct_count / total_questions * 100) if total_questions > 0 else 0
                        }
                        await db.history.insert_one(history_record)
                        logger.info(
                            section=LogSection.USER,
                            subsection=LogSubsection.USER.HISTORY,
                            message=f"Сохранена запись истории для пользователя {participant_id}"
                        )

                    await ws_manager.broadcast_to_lobby(lobby_id, {
                        "type": "test_finished", 
                        "data": results
                    })

            elif data.startswith("GET_ANSWERED_USERS"):
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.ANSWERS,
                    message=f"Обработка запроса ответивших пользователей от пользователя {user_id}"
                )
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if not lobby or lobby["status"] != "in_progress":
                    logger.error(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.STATUS,
                        message=f"Тест не активен в лобби {lobby_id}"
                    )
                    await websocket.send_json({"type": "error", "data": {"message": "Тест не активен"}})
                    continue

                if lobby["host_id"] != user_id:
                    logger.warning(
                        section=LogSection.SECURITY,
                        subsection=LogSubsection.SECURITY.ACCESS_DENIED,
                        message=f"Не-хост пользователь {user_id} попытался получить ответивших пользователей"
                    )
                    await websocket.send_json(
                        {"type": "error", "data": {"message": "У вас нет прав запрашивать статус ответов"}})
                    continue

                current_index = lobby.get("current_index", 0)
                if 0 <= current_index < len(lobby["question_ids"]):
                    current_question_id = lobby["question_ids"][current_index]
                    answered_users = []
                    for participant_id in lobby["participants"]:
                        if current_question_id in lobby.get("participants_answers", {}).get(participant_id, {}):
                            is_correct = lobby["participants_answers"][participant_id][current_question_id]
                            answered_users.append({"user_id": participant_id, "is_correct": is_correct})
                    logger.info(
                        section=LogSection.WEBSOCKET,
                        subsection=LogSubsection.WEBSOCKET.MESSAGE_SEND,
                        message=f"Отправка ответивших пользователей для вопроса {current_question_id}"
                    )
                    await websocket.send_json({"type": "answered_users", "data": answered_users})

    except WebSocketDisconnect:
        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.DISCONNECTION,
            message=f"WebSocket отключен для пользователя {user_id} в лобби {lobby_id}"
        )
        await ws_manager.disconnect(lobby_id, websocket)
        
        # Удаляем пользователя из лобби в базе данных при отключении
        # (но не если это хост - хост может только закрыть лобби)
        try:
            lobby = await db.lobbies.find_one({"_id": lobby_id})
            if lobby and user_id in lobby["participants"] and user_id != lobby["host_id"]:
                # Удаляем участника только если лобби не в процессе выполнения теста
                if lobby["status"] != "in_progress":
                    await db.lobbies.update_one(
                        {"_id": lobby_id},
                        {
                            "$pull": {"participants": user_id},
                            "$unset": {f"participants_answers.{user_id}": ""}
                        }
                    )
                    logger.info(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.LEAVE,
                        message=f"Пользователь {user_id} удален из лобби {lobby_id} в базе данных при отключении"
                    )
                    
                    # Отправляем обновленный список участников
                    updated_lobby = await db.lobbies.find_one({"_id": lobby_id})
                    if updated_lobby:
                        await ws_manager.broadcast_to_lobby(lobby_id, {
                            "type": "participants_updated",
                            "data": {
                                "participants": updated_lobby.get("participants", []),
                                "participant_count": len(updated_lobby.get("participants", []))
                            }
                        })
                else:
                    logger.info(
                        section=LogSection.LOBBY,
                        subsection=LogSubsection.LOBBY.LEAVE,
                        message=f"Пользователь {user_id} отключился во время теста в лобби {lobby_id}, остается в списке участников"
                    )
            
        except Exception as db_error:
            logger.error(
                section=LogSection.API,
                subsection=LogSubsection.API.ERROR,
                message=f"Ошибка удаления пользователя {user_id} из лобби {lobby_id} в базе данных: {str(db_error)}"
            )
        
        # Отправляем уведомление о выходе пользователя
        await ws_manager.broadcast_to_lobby(lobby_id, {
            "type": "user_left", 
            "data": {"user_id": user_id}
        })
    except Exception as e:
        logger.error(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.ERROR,
            message=f"WebSocket ошибка для пользователя {user_id} в лобби {lobby_id}: {str(e)}"
        )
        try:
            await ws_manager.disconnect(lobby_id, websocket)
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
