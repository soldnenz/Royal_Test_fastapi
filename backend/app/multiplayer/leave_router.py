from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional
import logging
from datetime import datetime

from app.core.security import get_current_actor
from app.db.database import get_database
from app.core.redis_client import multiplayer_redis_client
from app.core.response import success, error
from app.logging import LogSection, LogSubsection

from .lobby_utils import get_lobby_from_db, get_user_id

router = APIRouter(prefix="/multiplayer/lobbies", tags=["multiplayer"])

logger = logging.getLogger(__name__)

@router.post("/{lobby_id}/leave", summary="Выйти из лобби")
async def leave_lobby(
    lobby_id: str,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Позволяет пользователю выйти из лобби.
    Хост не может выйти из лобби (только закрыть его).
    """
    user_id = get_user_id(current_user)
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.LEAVE,
        message=f"Попытка выхода из лобби: пользователь {user_id} пытается выйти из лобби {lobby_id}"
    )
    
    try:
        db = get_database()
        
        # Получаем лобби
        lobby = await get_lobby_from_db(lobby_id)
        if not lobby:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.LEAVE,
                message=f"Лобби не найдено: пользователь {user_id} пытается выйти из несуществующего лобби {lobby_id}"
            )
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        # Проверяем, что пользователь является участником лобби
        participants = lobby.get("participants", [])
        if user_id not in participants:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.LEAVE,
                message=f"Попытка выхода не-участника: пользователь {user_id} пытается выйти из лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")
        
        # Проверяем, что пользователь не является хостом
        host_id = lobby.get("host_id")
        if str(user_id) == str(host_id):
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.LEAVE,
                message=f"Попытка выхода хоста: пользователь {user_id} (хост) пытается выйти из лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Хост не может выйти из лобби. Используйте 'Закрыть лобби'")
        
        # Проверяем статус лобби
        if lobby["status"] == "finished":
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.LEAVE,
                message=f"Попытка выхода из завершенного лобби: пользователь {user_id} пытается выйти из лобби {lobby_id}"
            )
            raise HTTPException(status_code=400, detail="Лобби уже завершено")
        
        # Определяем, является ли пользователь гостем
        is_guest = current_user.get("is_guest", False)
        
        # Удаляем пользователя из списка участников
        updated_participants = [p for p in participants if p != user_id]
        
        # Получаем список вышедших пользователей
        left_users = lobby.get("left_users", [])
        left_users.append({
            "user_id": user_id,
            "name": current_user.get("name", "Unknown"),
            "left_at": datetime.utcnow().isoformat(),
            "is_guest": is_guest
        })
        
        # Обновляем лобби
        update_data = {
            "participants": updated_participants,
            "left_users": left_users,
            "updated_at": datetime.utcnow()
        }
        
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {"$set": update_data}
        )
        
        # Удаляем токен из Redis
        try:
            redis_conn = await multiplayer_redis_client.get_connection()
            token_key = f"ws_token:{user_id}:{lobby_id}"
            await redis_conn.delete(token_key)
            
            # Если это гость, удаляем из коллекции гостей
            if is_guest:
                await db.guests.delete_one({"user_id": user_id})
                logger.info(
                    section=LogSection.LOBBY,
                    subsection=LogSubsection.LOBBY.LEAVE,
                    message=f"Гость {user_id} удален из коллекции гостей"
                )
        except Exception as e:
            logger.error(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.LEAVE,
                message=f"Ошибка при удалении токена из Redis: {str(e)}"
            )
            # Не прерываем выполнение, так как основная операция выполнена успешно
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.LEAVE,
            message=f"Пользователь {user_id} успешно вышел из лобби {lobby_id}. Участников осталось: {len(updated_participants)}"
        )
        
        return success(data={
            "message": "Вы успешно вышли из лобби",
            "lobby_id": lobby_id,
            "user_id": user_id,
            "remaining_participants": len(updated_participants)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка при выходе из лобби: лобби {lobby_id}, пользователь {user_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при выходе из лобби") 