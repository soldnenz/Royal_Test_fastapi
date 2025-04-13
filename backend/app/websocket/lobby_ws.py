# app/websocket/lobby_ws.py
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, Request, Depends
from typing import Dict, List
from app.db.database import db
from datetime import datetime
import jwt
from app.core.config import settings
from bson import ObjectId
import json

class LobbyConnectionManager:
    def __init__(self):
        # Словарь активных соединений: ключ - lobby_id, значение - список (или словарь) подключений
        self.connections: Dict[str, List[dict]] = {}

    async def connect(self, lobby_id: str, user_id: str, websocket: WebSocket):
        await websocket.accept()
        # Добавляем соединение в список для данного лобби
        if lobby_id not in self.connections:
            self.connections[lobby_id] = []
        # Сохраняем связку websocket + user_id
        self.connections[lobby_id].append({"websocket": websocket, "user_id": user_id})

    def disconnect(self, lobby_id: str, websocket: WebSocket):
        # Удаляем соединение из списка
        if lobby_id in self.connections:
            try:
                # Находим элемент с нужным websocket
                for i, conn in enumerate(self.connections[lobby_id]):
                    if conn["websocket"] == websocket:
                        self.connections[lobby_id].pop(i)
                        break
            except Exception:
                pass  # соединение могло быть уже удалено
            # Если в лобби не осталось соединений, можно удалить ключ
            if not self.connections[lobby_id]:
                del self.connections[lobby_id]

    async def send_message(self, lobby_id: str, message: str):
        # Отправляет текстовое сообщение всем активным соединениям в заданном лобби
        if lobby_id in self.connections:
            for conn in list(self.connections[lobby_id]):
                try:
                    await conn["websocket"].send_text(message)
                except Exception:
                    # На случай, если отправка не удалась (например, соединение закрыто)
                    # Откладываем удаление на потом, чтобы не менять список во время итерации
                    pass

    async def send_json(self, lobby_id: str, data: dict):
        # Отправка JSON-данных (словаря) всем участникам
        if lobby_id in self.connections:
            json_str = json.dumps(data)
            await self.send_message(lobby_id, json_str)

    def get_user_id_by_websocket(self, lobby_id: str, websocket: WebSocket):
        # Находит user_id по объекту websocket
        if lobby_id in self.connections:
            for conn in self.connections[lobby_id]:
                if conn["websocket"] == websocket:
                    return conn["user_id"]
        return None

# Инициализируем глобальный менеджер, который можно импортировать
ws_manager = LobbyConnectionManager()

async def verify_token(token: str):
    """Верифицирует JWT токен и возвращает информацию о пользователе."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        
        if not user_id or not ObjectId.is_valid(user_id):
            return None
            
        # Проверяем, существует ли токен в базе данных
        token_doc = await db.tokens.find_one({"token": token})
        if not token_doc or token_doc.get("revoked") or token_doc.get("expires_at") < datetime.utcnow():
            return None
            
        # Обновляем информацию о последней активности
        await db.tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {"last_activity": datetime.utcnow()}}
        )
            
        # Получаем информацию о пользователе
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return None
            
        return {
            "id": str(user["_id"]),
            "full_name": user.get("full_name"),
            "email": user.get("email")
        }
    except Exception:
        return None

# WebSocket endpoint (его подключим в main.py)
async def lobby_ws_endpoint(websocket: WebSocket, lobby_id: str, token: str = None):
    # Проверяем авторизацию
    if not token:
        await websocket.close(code=1008, reason="Unauthorized: No token provided")
        return
        
    user_data = await verify_token(token)
    if not user_data:
        await websocket.close(code=1008, reason="Unauthorized: Invalid token")
        return
        
    user_id = str(user_data["id"])
    
    # Проверяем существование лобби и участие пользователя
    lobby = await db.lobbies.find_one({"_id": lobby_id})
    if not lobby:
        await websocket.close(code=1008, reason="Lobby not found")
        return
        
    # Проверяем, есть ли у пользователя уже активное лобби (чтобы избежать двойного участия)
    if user_id != lobby["host_id"]:  # Хост может подключиться к своему лобби
        other_lobbies = await db.lobbies.find_one({
            "participants": user_id,
            "_id": {"$ne": lobby_id},
            "status": {"$ne": "finished"}
        })
        if other_lobbies:
            await websocket.close(code=1008, reason="У вас уже есть активное лобби. Завершите его перед подключением к новому.")
            return
        
    if user_id not in lobby["participants"]:
        # Если пользователь не является участником, добавляем его (автоджоин)
        if lobby["status"] == "waiting":
            await db.lobbies.update_one({"_id": lobby_id}, {
                "$push": {"participants": user_id},
                "$set": {f"participants_answers.{user_id}": {}}
            })
        else:
            await websocket.close(code=1008, reason="Невозможно присоединиться: тест уже начат или завершен")
            return

    # При новом подключении регистрируем соединение
    await ws_manager.connect(lobby_id, user_id, websocket)
    # Оповещение остальных: новый пользователь подключился
    await ws_manager.send_message(lobby_id, f"USER_JOINED:{user_id}")
    
    # Если лобби уже в статусе 'in_progress', отправляем текущее состояние
    if lobby["status"] == "in_progress":
        current_index = lobby.get("current_index", 0)
        if 0 <= current_index < len(lobby["question_ids"]):
            current_question_id = lobby["question_ids"][current_index]
            await websocket.send_text(f"CURRENT_QUESTION:{current_question_id}")
            
            # Если пользователь - хост, отправляем информацию о том, кто уже ответил
            if user_id == lobby["host_id"]:
                answered_users = []
                for participant_id in lobby["participants"]:
                    if current_question_id in lobby.get("participants_answers", {}).get(participant_id, {}):
                        is_correct = lobby["participants_answers"][participant_id][current_question_id]
                        answered_users.append({"user_id": participant_id, "is_correct": is_correct})
                await websocket.send_text(f"ANSWERED_USERS:{json.dumps(answered_users)}")
    
    try:
        # Основной цикл ожидания сообщений от клиента
        while True:
            data = await websocket.receive_text()
            
            # Предполагается, что клиент отправляет ответы в формате "ANSWER:<question_id>:<answer_index>"
            if data.startswith("ANSWER:"):
                _, qid, answer_idx = data.split(":")
                answer_idx = int(answer_idx)
                
                # Обновляем информацию о лобби
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if not lobby or lobby["status"] != "in_progress":
                    # Если лобби не найдено или не активно, прекращаем обработку
                    await websocket.send_text(f"ERROR:Тест не активен или завершен")
                    continue
                    
                # Проверяем правильность ответа
                correct_idx = lobby["correct_answers"].get(qid)
                if correct_idx is None:
                    await websocket.send_text(f"ERROR:Вопрос {qid} не найден")
                    continue
                    
                is_correct = (answer_idx == correct_idx)
                
                # Проверяем, не отвечал ли пользователь на этот вопрос ранее
                if qid in lobby.get("participants_answers", {}).get(user_id, {}):
                    await websocket.send_text(f"ERROR:Вы уже ответили на этот вопрос")
                    continue
                
                # Сохраняем ответ в коллекцию user_answers
                answer_doc = {
                    "user_id": user_id,
                    "lobby_id": lobby_id,
                    "question_id": qid,
                    "answer": answer_idx,
                    "is_correct": is_correct,
                    "timestamp": datetime.utcnow()
                }
                await db.user_answers.insert_one(answer_doc)
                
                # Обновляем информацию в документе лобби
                await db.lobbies.update_one(
                    {"_id": lobby_id},
                    {"$set": {f"participants_answers.{user_id}.{qid}": is_correct}}
                )
                
                # Отправляем подтверждение обратно этому пользователю
                await websocket.send_text(f"ANSWER_CONFIRMED:{qid}:{is_correct}")
                
                # Оповещаем всех о полученном ответе
                await ws_manager.send_message(lobby_id, f"ANSWER_RECEIVED:{user_id}:{qid}:{is_correct}")
                
                # Если пользователь - хост, сразу обновляем список ответивших
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                current_index = lobby.get("current_index", 0)
                current_question_id = lobby["question_ids"][current_index]
                
                # Отправляем хосту обновленную информацию о том, кто ответил
                host_id = lobby["host_id"]
                answered_users = []
                for participant_id in lobby["participants"]:
                    if current_question_id in lobby.get("participants_answers", {}).get(participant_id, {}):
                        answer_correct = lobby["participants_answers"][participant_id][current_question_id]
                        answered_users.append({"user_id": participant_id, "is_correct": answer_correct})
                
                # Находим соединение хоста и отправляем только ему
                if lobby_id in ws_manager.connections:
                    for conn in ws_manager.connections[lobby_id]:
                        if conn["user_id"] == host_id:
                            try:
                                await conn["websocket"].send_text(f"ANSWERED_USERS:{json.dumps(answered_users)}")
                            except Exception:
                                pass
                
                # Проверяем, все ли пользователи ответили на текущий вопрос
                all_answered = True
                for participant_id in lobby["participants"]:
                    if current_question_id not in lobby.get("participants_answers", {}).get(participant_id, {}):
                        all_answered = False
                        break
                
                # Если все ответили, отправляем событие ALL_ANSWERED хосту
                if all_answered and host_id:
                    if lobby_id in ws_manager.connections:
                        for conn in ws_manager.connections[lobby_id]:
                            if conn["user_id"] == host_id:
                                try:
                                    await conn["websocket"].send_text(f"ALL_ANSWERED")
                                except Exception:
                                    pass
            
            # Для хоста: следующий вопрос
            elif data.startswith("NEXT_QUESTION"):
                # Проверяем, что это запрос от хоста
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if not lobby:
                    await websocket.send_text(f"ERROR:Лобби не найдено")
                    continue
                    
                if lobby["host_id"] != user_id:
                    await websocket.send_text(f"ERROR:Только хост может перейти к следующему вопросу")
                    continue
                    
                if lobby["status"] != "in_progress":
                    await websocket.send_text(f"ERROR:Тест не активен")
                    continue
                
                current_index = lobby.get("current_index", 0)
                total_questions = len(lobby.get("question_ids", []))
                
                if current_index < total_questions - 1 and current_index < 39:  # 0-based index, 39 = 40 вопросов
                    new_index = current_index + 1
                    await db.lobbies.update_one({"_id": lobby_id}, {"$set": {"current_index": new_index}})
                    next_question_id = lobby["question_ids"][new_index]
                    await ws_manager.send_message(lobby_id, f"NEXT_QUESTION:{next_question_id}")
                else:
                    # Если это был последний вопрос или достигли 40 вопросов, завершаем тест
                    await db.lobbies.update_one(
                        {"_id": lobby_id}, 
                        {"$set": {"status": "finished", "finished_at": datetime.utcnow()}}
                    )
                    
                    # Получаем финальные данные для подсчета результатов
                    updated_lobby = await db.lobbies.find_one({"_id": lobby_id})
                    results = {}
                    total_questions = len(updated_lobby.get("question_ids", []))
                    for participant_id, answers in updated_lobby.get("participants_answers", {}).items():
                        correct_count = sum(1 for is_corr in answers.values() if is_corr)
                        results[participant_id] = {"correct": correct_count, "total": total_questions}
                        
                        # Сохраняем запись об истории прохождения
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
                        
                    await ws_manager.send_message(lobby_id, f"TEST_FINISHED:{json.dumps(results)}")
            
            # Запрос от хоста на получение статуса ответов участников
            elif data.startswith("GET_ANSWERED_USERS"):
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if not lobby or lobby["status"] != "in_progress":
                    await websocket.send_text(f"ERROR:Тест не активен")
                    continue
                
                # Только хост может запрашивать эту информацию
                if lobby["host_id"] != user_id:
                    await websocket.send_text(f"ERROR:У вас нет прав запрашивать статус ответов")
                    continue
                
                current_index = lobby.get("current_index", 0)
                if 0 <= current_index < len(lobby["question_ids"]):
                    current_question_id = lobby["question_ids"][current_index]
                    answered_users = []
                    for participant_id in lobby["participants"]:
                        if current_question_id in lobby.get("participants_answers", {}).get(participant_id, {}):
                            is_correct = lobby["participants_answers"][participant_id][current_question_id]
                            answered_users.append({"user_id": participant_id, "is_correct": is_correct})
                    await websocket.send_text(f"ANSWERED_USERS:{json.dumps(answered_users)}")
            
            # Можно добавить обработку других типов сообщений
            
    except WebSocketDisconnect:
        # Если соединение разорвано
        ws_manager.disconnect(lobby_id, websocket)
        # Оповещаем остальных, что пользователь вышел
        await ws_manager.send_message(lobby_id, f"USER_LEFT:{user_id}")
    except Exception as e:
        # Логируем ошибку
        print(f"WebSocket error: {str(e)}")
        # Закрываем соединение при неожиданной ошибке
        try:
            ws_manager.disconnect(lobby_id, websocket)
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass