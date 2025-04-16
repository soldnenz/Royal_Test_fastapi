from fastapi import WebSocket, WebSocketDisconnect, HTTPException, Request, Depends, Query
from typing import Dict, List
from app.db.database import db
from datetime import datetime
import jwt
from app.core.config import settings
from bson import ObjectId
import json
import logging

# Настройка логгера
logger = logging.getLogger(__name__)

class LobbyConnectionManager:
    def __init__(self):
        # Словарь активных соединений: ключ - lobby_id, значение - список соединений
        self.connections: Dict[str, List[dict]] = {}
        logger.info("LobbyConnectionManager initialized")

    async def connect(self, lobby_id: str, user_id: str, websocket: WebSocket):
        logger.info(f"New connection attempt to lobby {lobby_id} from user {user_id}")
        await websocket.accept()
        if lobby_id not in self.connections:
            self.connections[lobby_id] = []
        self.connections[lobby_id].append({"websocket": websocket, "user_id": user_id})
        logger.info(f"Connection accepted. Active connections in lobby {lobby_id}: {len(self.connections[lobby_id])}")

    def disconnect(self, lobby_id: str, websocket: WebSocket):
        logger.info(f"Disconnection from lobby {lobby_id}")
        if lobby_id in self.connections:
            try:
                for i, conn in enumerate(self.connections[lobby_id]):
                    if conn["websocket"] == websocket:
                        self.connections[lobby_id].pop(i)
                        logger.info(f"User {conn['user_id']} disconnected from lobby {lobby_id}")
                        break
            except Exception as e:
                logger.error(f"Error during disconnect: {str(e)}")
            if not self.connections[lobby_id]:
                del self.connections[lobby_id]
                logger.info(f"Lobby {lobby_id} has no more connections")

    async def send_message(self, lobby_id: str, message: str):
        if lobby_id in self.connections:
            logger.debug(f"Sending message to lobby {lobby_id}: {message}")
            for conn in list(self.connections[lobby_id]):
                try:
                    await conn["websocket"].send_text(message)
                except Exception as e:
                    logger.error(f"Error sending message to user {conn['user_id']}: {str(e)}")

    async def send_json(self, lobby_id: str, data: dict):
        if lobby_id in self.connections:
            json_str = json.dumps(data)
            logger.debug(f"Sending JSON to lobby {lobby_id}: {data}")
            await self.send_message(lobby_id, json_str)

    async def broadcast_to_lobby(self, lobby_id: str, data: dict):
        logger.info(f"Broadcasting to lobby {lobby_id}: {data}")
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
        logger.info(f"Broadcasting answer status for user {user_id} in lobby {lobby_id}")
        await self.broadcast_to_lobby(lobby_id, message)

    async def broadcast_question_results(self, lobby_id: str, question_id: int, results: List[dict]):
        message = {
            "type": "question_results",
            "data": {
                "question_id": question_id,
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        logger.info(f"Broadcasting question results for question {question_id} in lobby {lobby_id}")
        await self.broadcast_to_lobby(lobby_id, message)

    async def broadcast_final_results(self, lobby_id: str, results: List[dict]):
        message = {
            "type": "final_results",
            "data": {
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        logger.info(f"Broadcasting final results for lobby {lobby_id}")
        await self.broadcast_to_lobby(lobby_id, message)


ws_manager = LobbyConnectionManager()


async def verify_token(token: str):
    """Верифицирует JWT токен и возвращает информацию о пользователе."""
    logger.info("Verifying token")
    try:
        try:
            ws_token = await db.ws_tokens.find_one({"token": token, "used": False})
            if ws_token and ws_token.get("expires_at") > datetime.utcnow():
                logger.info(f"Found valid WS token for user {ws_token.get('user_id')}")
                await db.ws_tokens.update_one(
                    {"_id": ws_token["_id"]},
                    {"$set": {"used": True, "used_at": datetime.utcnow()}}
                )
                user_id = ws_token.get("user_id")
                user = await db.users.find_one({"_id": ObjectId(user_id)})
                if user:
                    logger.info(f"User {user_id} verified successfully")
                    return {
                        "id": str(user["_id"]),
                        "full_name": user.get("full_name"),
                        "email": user.get("email")
                    }
            logger.warning("WS token not found or expired, falling back to regular token verification")
        except Exception as e:
            logger.error(f"Error verifying WS token: {str(e)}")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id or not ObjectId.is_valid(user_id):
            logger.error("Invalid user ID in token")
            return None
        token_doc = await db.tokens.find_one({"token": token})
        if not token_doc or token_doc.get("revoked") or token_doc.get("expires_at") < datetime.utcnow():
            logger.error("Token not found, revoked or expired")
            return None
        await db.tokens.update_one(
            {"_id": token_doc["_id"]},
            {"$set": {"last_activity": datetime.utcnow()}}
        )
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"User {user_id} not found")
            return None
        logger.info(f"User {user_id} verified successfully with regular token")
        return {
            "id": str(user["_id"]),
            "full_name": user.get("full_name"),
            "email": user.get("email")
        }
    except Exception as e:
        logger.error(f"Error verifying token: {str(e)}")
        return None


async def lobby_ws_endpoint(websocket: WebSocket, lobby_id: str, token: str = Query(...)):
    logger.info(f"New WebSocket connection request for lobby {lobby_id}")
    if not token:
        logger.error("No token provided")
        await websocket.close(code=1008, reason="Unauthorized: No token provided")
        return

    user_data = await verify_token(token)
    if not user_data:
        logger.error("Invalid token")
        await websocket.close(code=1008, reason="Unauthorized: Invalid token")
        return

    user_id = str(user_data["id"])
    logger.info(f"User {user_id} ({user_data.get('full_name', 'Unknown')}) connecting to lobby {lobby_id}")

    lobby = await db.lobbies.find_one({"_id": lobby_id})
    if not lobby:
        logger.error(f"Lobby {lobby_id} not found")
        await websocket.close(code=1008, reason="Lobby not found")
        return

    if user_id != lobby["host_id"]:
        other_lobbies = await db.lobbies.find_one({
            "participants": user_id,
            "_id": {"$ne": lobby_id},
            "status": {"$ne": "finished"}
        })
        if other_lobbies:
            logger.warning(f"User {user_id} already in another active lobby")
            await websocket.close(code=1008,
                                  reason="У вас уже есть активное лобби. Завершите его перед подключением к новому.")
            return

    if user_id not in lobby["participants"]:
        if lobby["status"] == "waiting":
            logger.info(f"Adding user {user_id} to lobby {lobby_id}")
            await db.lobbies.update_one({"_id": lobby_id}, {
                "$push": {"participants": user_id},
                "$set": {f"participants_answers.{user_id}": {}}
            })
        else:
            logger.error(f"Cannot join lobby {lobby_id}: test already started or finished")
            await websocket.close(code=1008, reason="Невозможно присоединиться: тест уже начат или завершен")
            return

    await ws_manager.connect(lobby_id, user_id, websocket)
    await ws_manager.send_json(lobby_id, {
        "type": "user_joined",
        "data": {
            "user_id": user_id,
            "is_host": user_id == lobby["host_id"],
            "user_name": user_data.get("full_name", "Unknown User")
        }
    })

    if lobby["status"] == "in_progress":
        current_index = lobby.get("current_index", 0)
        if 0 <= current_index < len(lobby["question_ids"]):
            current_question_id = lobby["question_ids"][current_index]
            logger.info(f"Sending current question {current_question_id} to user {user_id}")
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
            logger.debug(f"Received message from user {user_id}: {data}")

            if data.startswith("ANSWER:"):
                _, qid, answer_idx = data.split(":")
                answer_idx = int(answer_idx)
                logger.info(f"Processing answer from user {user_id} for question {qid}")

                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if not lobby or lobby["status"] != "in_progress":
                    logger.error(f"Test not active or finished for lobby {lobby_id}")
                    await websocket.send_json({"type": "error", "data": {"message": "Тест не активен или завершен"}})
                    continue

                correct_idx = lobby["correct_answers"].get(qid)
                if correct_idx is None:
                    logger.error(f"Question {qid} not found in lobby {lobby_id}")
                    await websocket.send_json({"type": "error", "data": {"message": f"Вопрос {qid} не найден"}})
                    continue

                is_correct = (answer_idx == correct_idx)
                logger.info(f"Answer from user {user_id} is {'correct' if is_correct else 'incorrect'}")

                if qid in lobby.get("participants_answers", {}).get(user_id, {}):
                    logger.warning(f"User {user_id} already answered question {qid}")
                    await websocket.send_json({"type": "error", "data": {"message": "Вы уже ответили на этот вопрос"}})
                    continue

                answer_doc = {
                    "user_id": user_id,
                    "lobby_id": lobby_id,
                    "question_id": qid,
                    "answer": answer_idx,
                    "is_correct": is_correct,
                    "timestamp": datetime.utcnow()
                }
                await db.user_answers.insert_one(answer_doc)
                logger.info(f"Saved answer from user {user_id} for question {qid}")

                await db.lobbies.update_one(
                    {"_id": lobby_id},
                    {"$set": {f"participants_answers.{user_id}.{qid}": is_correct}}
                )

                await websocket.send_json(
                    {"type": "answer_confirmed", "data": {"question_id": qid, "is_correct": is_correct}})

                # Отправляем уведомление всем участникам
                await ws_manager.send_json(lobby_id, {"type": "answer_received",
                                                      "data": {"user_id": user_id, "question_id": qid,
                                                               "is_correct": is_correct,
                                                               "user_name": user_data.get("full_name", "Unknown User")}})

                lobby = await db.lobbies.find_one({"_id": lobby_id})
                current_index = lobby.get("current_index", 0)
                current_question_id = lobby["question_ids"][current_index]

                host_id = lobby["host_id"]
                answered_users = []
                for participant_id in lobby["participants"]:
                    if current_question_id in lobby.get("participants_answers", {}).get(participant_id, {}):
                        answer_correct = lobby["participants_answers"][participant_id][current_question_id]
                        
                        # Get user information for better display
                        user_info = await db.users.find_one({"_id": ObjectId(participant_id)}) if ObjectId.is_valid(participant_id) else None
                        user_name = user_info.get("full_name", "Unknown") if user_info else "Unknown"
                        
                        answered_users.append({
                            "user_id": participant_id, 
                            "is_correct": answer_correct,
                            "user_name": user_name
                        })

                if lobby_id in ws_manager.connections:
                    for conn in ws_manager.connections[lobby_id]:
                        if conn["user_id"] == host_id:
                            try:
                                await conn["websocket"].send_json({"type": "answered_users", "data": answered_users})
                            except Exception as e:
                                logger.error(f"Error sending answered users to host: {str(e)}")

                all_answered = True
                for participant_id in lobby["participants"]:
                    if current_question_id not in lobby.get("participants_answers", {}).get(participant_id, {}):
                        all_answered = False
                        break

                if all_answered and host_id:
                    logger.info(f"All users answered question {current_question_id} in lobby {lobby_id}")
                    if lobby_id in ws_manager.connections:
                        for conn in ws_manager.connections[lobby_id]:
                            if conn["user_id"] == host_id:
                                try:
                                    await conn["websocket"].send_json({"type": "all_answered", "data": {}})
                                except Exception as e:
                                    logger.error(f"Error sending all_answered to host: {str(e)}")

            elif data.startswith("NEXT_QUESTION"):
                logger.info(f"Processing next question request from user {user_id}")
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if not lobby:
                    logger.error(f"Lobby {lobby_id} not found")
                    await websocket.send_json({"type": "error", "data": {"message": "Лобби не найдено"}})
                    continue

                if lobby["host_id"] != user_id:
                    logger.warning(f"Non-host user {user_id} tried to move to next question")
                    await websocket.send_json(
                        {"type": "error", "data": {"message": "Только хост может перейти к следующему вопросу"}})
                    continue

                if lobby["status"] != "in_progress":
                    logger.error(f"Test not active in lobby {lobby_id}")
                    await websocket.send_json({"type": "error", "data": {"message": "Тест не активен"}})
                    continue

                current_index = lobby.get("current_index", 0)
                total_questions = len(lobby.get("question_ids", []))

                if current_index < total_questions - 1 and current_index < 39:
                    new_index = current_index + 1
                    logger.info(f"Moving to next question {new_index} in lobby {lobby_id}")
                    await db.lobbies.update_one({"_id": lobby_id}, {"$set": {"current_index": new_index}})
                    next_question_id = lobby["question_ids"][new_index]
                    await ws_manager.send_json(lobby_id,
                                               {"type": "next_question", "data": {"question_id": next_question_id}})
                else:
                    logger.info(f"Test finished in lobby {lobby_id}")
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
                        logger.info(f"Saved history record for user {participant_id}")

                    await ws_manager.send_json(lobby_id, {"type": "test_finished", "data": results})

            elif data.startswith("GET_ANSWERED_USERS"):
                logger.info(f"Processing answered users request from user {user_id}")
                lobby = await db.lobbies.find_one({"_id": lobby_id})
                if not lobby or lobby["status"] != "in_progress":
                    logger.error(f"Test not active in lobby {lobby_id}")
                    await websocket.send_json({"type": "error", "data": {"message": "Тест не активен"}})
                    continue

                if lobby["host_id"] != user_id:
                    logger.warning(f"Non-host user {user_id} tried to get answered users")
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
                    logger.info(f"Sending answered users for question {current_question_id}")
                    await websocket.send_json({"type": "answered_users", "data": answered_users})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id} in lobby {lobby_id}")
        ws_manager.disconnect(lobby_id, websocket)
        await ws_manager.send_json(lobby_id, {"type": "user_left", "data": {"user_id": user_id}})
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id} in lobby {lobby_id}: {str(e)}")
        try:
            ws_manager.disconnect(lobby_id, websocket)
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
