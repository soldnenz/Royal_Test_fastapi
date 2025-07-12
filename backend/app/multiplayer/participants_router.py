from fastapi import APIRouter, Depends, HTTPException, Request
from bson import ObjectId

from app.db.database import db
from app.core.security import get_current_actor
from app.core.response import success
from app.multiplayer.lobby_utils import get_user_id
from app.logging import get_logger, LogSection, LogSubsection

router = APIRouter()
logger = get_logger(__name__)

@router.get("/lobbies/{lobby_id}/participants", summary="Получить список участников лобби")
async def get_lobby_participants(
    lobby_id: str,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """
    Получает список всех участников лобби с их именами.
    Не использует кеш, данные всегда запрашиваются из БД.
    """
    user_id = get_user_id(current_user)
    logger.info(
        section=LogSection.LOBBY,
        subsection=LogSubsection.LOBBY.ACCESS,
        message=f"Запрос участников лобби: пользователь {user_id} запрашивает участников лобби {lobby_id}"
    )

    try:
        # Получаем лобби напрямую из базы данных, без кеша
        lobby = await db.lobbies.find_one({"_id": lobby_id})
        if not lobby:
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.ACCESS,
                message=f"Доступ запрещен: лобби {lobby_id} не найдено для пользователя {user_id}"
            )
            raise HTTPException(status_code=404, detail="Лобби не найдено")

        # Новая проверка: если пользователь в blacklisted_users, отказать
        if user_id in lobby.get("blacklisted_users", []):
            raise HTTPException(status_code=403, detail="Вы были исключены из лобби")

        # Проверяем, что запрашивающий пользователь является участником
        if user_id not in lobby.get("participants", []):
            logger.warning(
                section=LogSection.LOBBY,
                subsection=LogSubsection.LOBBY.SECURITY,
                message=f"Доступ запрещен: пользователь {user_id} не является участником лобби {lobby_id}"
            )
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого лобби")

        participant_ids = lobby.get("participants", [])
        
        # Получаем информацию о пользователях
        participants_details = []
        user_ids_to_fetch = [ObjectId(p_id) for p_id in participant_ids if not p_id.startswith("guest_")]
        
        # Запрашиваем данные для всех зарегистрированных пользователей одним запросом
        if user_ids_to_fetch:
            users_cursor = db.users.find({"_id": {"$in": user_ids_to_fetch}})
            users_data = {str(u["_id"]): u for u in await users_cursor.to_list(length=None)}
        else:
            users_data = {}

        for p_id in participant_ids:
            is_guest = p_id.startswith("guest_")
            user_info = {
                "user_id": p_id,
                "is_host": p_id == lobby.get("host_id"),
                "is_guest": is_guest,
                "name": "Unknown"
            }
            if is_guest:
                user_info["name"] = f"Гость {p_id[-8:]}"
            elif p_id in users_data:
                user_info["name"] = users_data[p_id].get("full_name", "Unknown User")
            
            participants_details.append(user_info)

        logger.info(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ACCESS,
            message=f"Список участников возвращен: {len(participants_details)} участников для лобби {lobby_id}"
        )
        
        return success(data={
            "lobby_id": lobby_id,
            "participants": participants_details,
            "total_participants": len(participants_details)
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.LOBBY,
            subsection=LogSubsection.LOBBY.ERROR,
            message=f"Ошибка получения участников лобби: лобби {lobby_id}, ошибка {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при получении участников") 