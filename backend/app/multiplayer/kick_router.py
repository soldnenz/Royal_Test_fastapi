from fastapi import APIRouter, Depends, HTTPException, Request
from bson import ObjectId

from app.core.response import success
from app.core.security import get_current_actor
from app.db.database import db
from app.logging import get_logger, LogSection, LogSubsection
from app.multiplayer.lobby_utils import get_user_id
from app.rate_limit import rate_limit_ip
from app.schemas.lobby_schemas import KickParticipantRequest
from app.multiplayer.ws_utils import clear_ws_token


router = APIRouter()
logger = get_logger(__name__)

@router.post("/lobbies/{lobby_id}/kick", summary="Исключить участника из лобби")
@rate_limit_ip("lobby_kick_participant", max_requests=15, window_seconds=300)
async def kick_participant(
    lobby_id: str,
    request_data: KickParticipantRequest,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Исключает участника из лобби, добавляет в черный список и отзывает его WS токен.
    Только хост может исключать участников.
    """
    user_id = get_user_id(current_user)
    target_user_id = request_data.target_user_id
    
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.SECURITY,
        message=f"Запрос на исключение участника {target_user_id} из лобби {lobby_id}. Инициатор: хост {user_id}."
    )
    
    try:
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            raise HTTPException(status_code=404, detail="Лобби не найдено")
        
        if str(lobby.get("host_id")) != user_id:
            raise HTTPException(status_code=403, detail="Только хост может исключать участников")
        
        if target_user_id not in lobby.get("participants", []):
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Хост {user_id} попытался исключить пользователя {target_user_id}, который не является участником лобби {lobby_id}."
            )
            return success(data={"message": "Пользователь уже не в лобби."})

        if target_user_id == user_id:
            raise HTTPException(status_code=400, detail="Хост не может исключить самого себя")
        
        await db.lobbies.update_one(
            {"_id": lobby_id},
            {
                "$pull": {"participants": target_user_id},
                "$addToSet": {"blacklisted_users": target_user_id},
                "$unset": {f"participants_answers.{target_user_id}": ""}
            }
        )
        
        try:
            await clear_ws_token(target_user_id)
        except Exception as e:
            logger.error(
                section=LogSection.WEBSOCKET,
                subsection=LogSubsection.WEBSOCKET.ERROR,
                message=f"Не удалось отозвать WS токен для исключенного пользователя {target_user_id} из лобби {lobby_id}. Ошибка: {e}"
            )
        
        return success(data={
            "message": "Участник успешно исключен",
            "kicked_user_id": target_user_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Критическая ошибка при исключении участника {target_user_id} из лобби {lobby_id} хостом {user_id}. Ошибка: {e}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при исключении участника") 