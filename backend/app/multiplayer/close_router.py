from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime
import asyncio

from app.core.response import success
from app.core.security import get_current_actor
from app.db.database import db
from app.logging import get_logger, LogSection, LogSubsection
from app.multiplayer.lobby_utils import get_user_id
from app.rate_limit import rate_limit_ip
from app.multiplayer.ws_utils import clear_ws_token


router = APIRouter()
logger = get_logger(__name__)


@router.post("/lobbies/{lobby_id}/close", summary="Закрыть лобби")
@rate_limit_ip("lobby_close", max_requests=10, window_seconds=300)
async def close_lobby(lobby_id: str, request: Request = None, current_user: dict = Depends(get_current_actor)):
    """
    Финализирует закрытие лобби и отзывает все WS токены участников.
    Только хост может закрыть лобби.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.LIFECYCLE,
        message=f"Запрос на закрытие лобби {lobby_id} от хоста {user_id}."
    )
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if str(lobby.get("host_id")) != user_id:
            raise HTTPException(status_code=403, detail="Только хост может закрыть лобби")
        
        if lobby.get("status") in ["finished", "closed"]:
            return success(data={"message": "Лобби уже было завершено или закрыто."})
        
        participants_to_clear = lobby.get("participants", [])
        if user_id not in participants_to_clear:
             participants_to_clear.append(user_id)

        logger.info(
            section=LogSection.WEBSOCKET,
            subsection=LogSubsection.WEBSOCKET.TOKEN_REVOKE,
            message=f"Начинаем отзыв WS токенов для {len(participants_to_clear)} участников в закрываемом лобби {lobby_id}."
        )
        for participant_id in participants_to_clear:
            try:
                await clear_ws_token(participant_id)
            except Exception as e:
                logger.error(
                    section=LogSection.WEBSOCKET,
                    subsection=LogSubsection.WEBSOCKET.ERROR,
                    message=f"Не удалось отозвать WS токен для участника {participant_id} при закрытии лобби {lobby_id}. Ошибка: {e}"
                )

        await db.lobbies.update_one(
            {"_id": lobby_id},
            {
                "$set": {
                    "status": "closed",
                    "closed_at": datetime.utcnow(),
                    "closed_by": user_id,
                    "participants": [] 
                }
            }
        )
        
        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.LIFECYCLE,
            message=f"Лобби {lobby_id} успешно закрыто хостом {user_id}."
        )
        return success(data={"message": "Лобби успешно закрыто"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Критическая ошибка при закрытии лобби {lobby_id} хостом {user_id}. Ошибка: {e}"
        )
        raise HTTPException(status_code=500, detail="Ошибка при закрытии лобби") 